"""
AI4ArtsEd — Denoising Archaeology (ComfyUI custom node)

ComfyUI port of gpu_service/services/diffusers_backend.py::generate_image_with_archaeology.

Samples like a KSampler, but records the WORKING latent x_t at every step and turns
each into a JPEG frame. Returns the final LATENT so the graph continues into a normal
VAEDecode -> SaveImage.

x_t, and not the net's denoised prediction x0. The two are different pictures: x_t is
the image coming out of the noise, x0 is what the net currently predicts the finished
image to be. The Diffusers original decodes x_t -- callback_kwargs["latents"], see
gpu_service/services/diffusers_backend.py:5052-5074 -- and the instrument's pedagogy
and its surface were built on that, so this port shows x_t too. ComfyUI's callback
hands over both (comfy/samplers.py:749 passes i, x["denoised"], x["x"], total), and
its own live preview takes x0 (latent_preview.py:112-122) -- which is where a port
written along ComfyUI's own template picks up the other one.

Difference to the Diffusers original, deliberate:
  The Diffusers version VAE-decodes inside the step callback, which forces the VAE and
  the MMDiT to be GPU-resident at the same time. This node collects the latents on
  CPU (~1 MB each for SD3.5 at 1024x1024) and decodes them after sampling has finished,
  so ComfyUI can free the diffusion model first. That is the whole point of the port on
  24/32 GB cards.

Frames are written to ComfyUI's output directory and announced in the `ui` payload, so
they arrive at the DevServer through the existing /history + /view path.
"""

import os

import numpy as np
import torch
from PIL import Image

import comfy.model_management
import comfy.sample
import comfy.samplers
import comfy.utils
import folder_paths


class AI4ArtsEdDenoisingArchaeology:
    """KSampler that keeps the working latent of every step as an image."""

    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
                "latent_image": ("LATENT",),
                "vae": ("VAE",),
                "seed": ("INT", {"default": 123456789, "min": 0, "max": 0xFFFFFFFFFFFFFFFF}),
                "steps": ("INT", {"default": 25, "min": 1, "max": 200}),
                "cfg": ("FLOAT", {"default": 4.5, "min": 0.0, "max": 100.0, "step": 0.1}),
                "sampler_name": (comfy.samplers.KSampler.SAMPLERS, {"default": "euler"}),
                "scheduler": (comfy.samplers.KSampler.SCHEDULERS, {"default": "normal"}),
                "denoise": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                "capture_every_n": ("INT", {"default": 1, "min": 1, "max": 50}),
                # 0 = keep the sampling resolution (matches the Diffusers original).
                "frame_max_size": ("INT", {"default": 0, "min": 0, "max": 4096, "step": 64}),
                "frame_quality": ("INT", {"default": 95, "min": 1, "max": 100}),
                "filename_prefix": ("STRING", {"default": "archaeology_step"}),
            }
        }

    RETURN_TYPES = ("LATENT",)
    RETURN_NAMES = ("latent",)
    FUNCTION = "sample"
    OUTPUT_NODE = True
    CATEGORY = "AI4ArtsEd/LatentLab"

    # ------------------------------------------------------------------ sampling

    def sample(self, model, positive, negative, latent_image, vae, seed, steps, cfg,
               sampler_name, scheduler, denoise, capture_every_n, frame_max_size,
               frame_quality, filename_prefix):

        latent = latent_image
        samples_in = comfy.sample.fix_empty_latent_channels(model, latent["samples"])
        noise = comfy.sample.prepare_noise(samples_in, seed, latent.get("batch_index"))
        noise_mask = latent.get("noise_mask")

        sigma_list = self._sigmas(model, steps, sampler_name, scheduler, denoise)

        # (step_index, x_t on CPU). One SD3.5 latent at 1024x1024 is 16*128*128*4 B ~ 1 MB,
        # so 25 of them cost ~25 MB of RAM and nothing on the GPU.
        captured = []
        pbar = comfy.utils.ProgressBar(steps)

        def callback(step, x0, x, total_steps):
            # x0 is the net's denoised prediction, x the working latent. This
            # instrument shows the second one -- see the module docstring.
            pbar.update_absolute(step + 1, total_steps, None)
            # Same skip rule as the Diffusers original.
            if capture_every_n > 1 and step % capture_every_n != 0:
                return
            captured.append((step, x.detach().to(device="cpu", dtype=torch.float32, copy=True)))

        out_samples = comfy.sample.sample(
            model, noise, steps, cfg, sampler_name, scheduler,
            positive, negative, samples_in,
            denoise=denoise,
            noise_mask=noise_mask,
            callback=callback,
            disable_pbar=True,
            seed=seed,
        )

        out = latent.copy()
        out["samples"] = out_samples

        # Sampling is done — let ComfyUI reclaim the diffusion model before the VAE runs.
        comfy.model_management.soft_empty_cache()

        frames = self._write_frames(
            model, vae, captured, sigma_list,
            frame_max_size, frame_quality, filename_prefix, steps,
        )

        return {
            "ui": {
                "images": [{"filename": f["filename"],
                            "subfolder": f["subfolder"],
                            "type": "output"} for f in frames],
                "archaeology": [{
                    "frames": frames,
                    "total_steps": steps,
                    "seed": seed,
                    "capture_every_n": capture_every_n,
                }],
            },
            "result": (out,),
        }

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _sigmas(model, steps, sampler_name, scheduler, denoise):
        """Sigma per step. Load-bearing, not decoration.

        The k-diffusion samplers call back with x as it stands at sigmas[i], before
        the step is applied (comfy/k_diffusion/sampling.py:272-288), and the wrapper
        at comfy/samplers.py:749 drops the sigma on the way. So it is recomputed
        here, from the same model and the same schedule the sampler walks, because
        without it x cannot be brought into the decoder's space at all -- see
        _to_decoder_space.

        A failure returns None and costs the FRAMES, not the run: the node still
        returns its latent and the graph still produces the final image.
        """
        try:
            ks = comfy.samplers.KSampler(
                model, steps=steps, device=model.load_device,
                sampler=sampler_name, scheduler=scheduler,
                denoise=denoise, model_options=model.model_options,
            )
            return [float(s) for s in ks.sigmas]
        except Exception:
            return None

    def _write_frames(self, model, vae, captured, sigma_list,
                      frame_max_size, frame_quality, filename_prefix, total_steps):
        if not captured:
            return []

        full_output_folder, filename, counter, subfolder, _ = folder_paths.get_save_image_path(
            filename_prefix, self.output_dir
        )

        frames = []
        for step, x_t in captured:
            try:
                sigma = sigma_list[step] if sigma_list and step < len(sigma_list) else None
                if sigma is None:
                    raise RuntimeError(
                        "no sigma for this step, so the working latent cannot be "
                        "brought into the decoder's space"
                    )
                latent_out = self._to_decoder_space(model, sigma, x_t)
                pixels = self._decode(vae, latent_out)

                image = self._to_pil(pixels[0])
                if frame_max_size > 0:
                    image.thumbnail((frame_max_size, frame_max_size), Image.LANCZOS)

                name = f"{filename}_{step:04d}_{counter:05d}_.jpg"
                image.save(os.path.join(full_output_folder, name),
                           format="JPEG", quality=frame_quality)

                frames.append({
                    "step": step,
                    "sigma": sigma,
                    "filename": name,
                    "subfolder": subfolder,
                })
            except Exception as exc:
                print(f"[AI4ARTSED-ARCHAEOLOGY] step {step} frame failed: {exc}")

        print(f"[AI4ARTSED-ARCHAEOLOGY] wrote {len(frames)}/{len(captured)} frames "
              f"of {total_steps} steps to {full_output_folder}")
        return frames

    @staticmethod
    def _to_decoder_space(model, sigma, x_t):
        """The working latent as the VAE has to read it.

        Two transforms, in this order, and both read off the model rather than
        written out here:

        1. calculate_input(sigma, x_t) -- what the sampler hands the net.
           For an eps/v-prediction model (SDXL, SD1.5) that is
           x_t / sqrt(sigma^2 + 1) (comfy/model_sampling.py:31-33, with
           sigma_data 1.0 at :134): the working latent grows with sigma, up to
           ~11.7 at 25 steps, and decoding it as it stands gives a washed-out,
           clipped frame. For flow matching (SD3.5, the CONST type at :62-64) it
           is the identity, because x_t = (1-s)*x0 + s*eps stays O(1). The
           Diffusers original branches on the scheduler's class name to decide
           this; asking the model is the same decision without the guess.

        2. process_latent_out -- the latent format's own scale and shift
           (comfy/latent_formats.py:16-17 with :31-32 for SDXL, / 0.13025;
           :143-147 for SD3, / 1.5305 + 0.0609). This is exactly what the
           Diffusers path applies by hand as vae.config.scaling_factor and
           shift_factor, so it must NOT be added a second time here.

        The sampling object is read through get_model_object, because
        ModelSamplingSD3 installs its shifted sampling as an object patch
        (comfy_extras/nodes_model_advanced.py:128-133) that model.model
        .model_sampling does not see.
        """
        try:
            model_sampling = model.get_model_object("model_sampling")
        except Exception:
            model_sampling = model.model.model_sampling
        sigma_t = torch.tensor([sigma], device=x_t.device, dtype=x_t.dtype)
        return model.model.process_latent_out(model_sampling.calculate_input(sigma_t, x_t))

    @staticmethod
    def _decode(vae, latent_out):
        try:
            return vae.decode(latent_out)
        except comfy.model_management.OOM_EXCEPTION:
            comfy.model_management.soft_empty_cache()
            return vae.decode_tiled(latent_out)

    @staticmethod
    def _to_pil(tensor):
        array = 255.0 * tensor.cpu().numpy()
        return Image.fromarray(np.clip(array, 0, 255).astype(np.uint8))


NODE_CLASS_MAPPINGS = {
    "AI4ArtsEdDenoisingArchaeology": AI4ArtsEdDenoisingArchaeology,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AI4ArtsEdDenoisingArchaeology": "AI4ArtsEd Denoising Archaeology",
}
