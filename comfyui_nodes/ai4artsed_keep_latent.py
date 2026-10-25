"""
AI4ArtsEd — Keep Latent (ComfyUI custom node)

Writes a run's final latent to ComfyUI's output directory and announces it, so the
DevServer can fetch it the same way it fetches a picture. The latent passes through
unchanged, so the node sits between the sampler and the VAE decode without altering
what is decoded.

Why the platform wants it: the Mean Images instrument averages a SET of pictures BEFORE
the decoder, for the reason its Diffusers counterpart records
(schemas/chunks/output_image_sd35_diffusers.py, at `latent_sink`). On that path a
`keep_latent` flag reaches the chunk and a sink writes the latent; this node is that
sink for ComfyUI.

TWO SPACES, ONE FILE. ComfyUI's sampler hands out its latent already de-scaled --
`comfy/samplers.py` returns `process_latent_out(...)`, which for SD 3.5 is
`(x / 1.5305) + 0.0609` (`comfy/latent_formats.py`). The Diffusers sink writes the
latent BEFORE that step, and the platform's decoder re-applies it. So a file written
here in ComfyUI's space would be de-scaled twice on the way back, and a set mixing both
backends would average two different spaces. The node therefore inverts the step through
the model's own latent format (`process_latent_in`) and writes what the Diffusers sink
writes. The MODEL input is there for that and for nothing else.

The file is a .npy of shape [C, h, w] in float16 -- the shape and dtype
devserver/my_app/services/mean_images.py::load_latent reads.

`enabled` is off by default, and off means no file is written at all: a workflow carries
this node permanently, and a run that was not asked for a latent must not pay for one.

THE WAY BACK. The second node here reads such a file (or the mean of several, which the
DevServer averages in that same space) out of ComfyUI's input directory and hands it to
the VAE decode as a LATENT. It applies the step the first node inverted, again through
the model's own latent format (`process_latent_out`), so the mean of a set is decoded by
the model that made the set, on this card, under a lease from the gate; the GPU service
computes nothing of it.
"""

import hashlib
import os

import numpy as np
import torch

import folder_paths


class AI4ArtsEdKeepLatent:
    """Passes a LATENT through, and writes it out when asked."""

    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL", {"tooltip": "Read for its latent format only."}),
                "samples": ("LATENT",),
                "enabled": ("BOOLEAN", {"default": False,
                                        "tooltip": "Off writes nothing at all."}),
                "filename_prefix": ("STRING", {"default": "ai4artsed_latent"}),
            },
        }

    RETURN_TYPES = ("LATENT",)
    FUNCTION = "keep"
    OUTPUT_NODE = True
    CATEGORY = "AI4ArtsEd/latent lab"

    def keep(self, model, samples, enabled, filename_prefix):
        if not enabled:
            return {"ui": {}, "result": (samples,)}

        tensor = samples["samples"]
        # One picture's latent, without the batch axis: [C, h, w], the shape
        # mean_images.load_latent requires. A batch keeps only its first member;
        # this instrument asks one run for one picture.
        if tensor.shape[0] > 1:
            print(f"[AI4ArtsEd] Keep Latent: batch of {tensor.shape[0]}, "
                  f"keeping the first")
        one = tensor[0:1].detach().to(device="cpu", dtype=torch.float32)

        inner = getattr(model, "model", model)
        fmt = inner.latent_format
        # Back into the space the platform's decoder expects. See the header.
        one = inner.process_latent_in(one)

        array = one[0].numpy().astype(np.float16)
        if not np.isfinite(array).all():
            # A diverged latent leaves NOTHING behind and the run keeps its
            # picture. Averaged in, one of these turns the mean of twenty into
            # a black square that answers 200; the set is then meaned pixel by
            # pixel instead, and says so.
            print("[AI4ArtsEd] Keep Latent: the latent diverged, none kept")
            return {"ui": {}, "result": (samples,)}

        full_folder, filename, counter, subfolder, _prefix = \
            folder_paths.get_save_image_path(filename_prefix, self.output_dir)
        name = f"{filename}_{counter:05}_.npy"
        path = os.path.join(full_folder, name)
        np.save(path, array)

        return {
            "ui": {
                # Its own key, so nothing that looks for pictures picks it up.
                # `meta` travels with the file: the DevServer records it beside
                # the latent, and the mean of a set is decoded from it.
                "latents": [{
                    "filename": name,
                    "subfolder": subfolder,
                    "type": "output",
                    "meta": {
                        "scaling_factor": float(fmt.scale_factor),
                        "shift_factor": float(getattr(fmt, "shift_factor", 0.0) or 0.0),
                        "shape": [int(n) for n in array.shape],
                        "dtype": str(array.dtype),
                    },
                }],
            },
            "result": (samples,),
        }


class AI4ArtsEdLoadKeptLatent:
    """Reads a kept latent (or the mean of several) back into a LATENT."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL", {"tooltip": "Read for its latent format only."}),
                "latent_file": ("STRING", {
                    "default": "",
                    "tooltip": "A .npy of shape [C, h, w] in ComfyUI's input directory, "
                               "in the space AI4ArtsEd Keep Latent writes."}),
            },
        }

    RETURN_TYPES = ("LATENT",)
    FUNCTION = "load"
    CATEGORY = "AI4ArtsEd/latent lab"

    @classmethod
    def VALIDATE_INPUTS(cls, latent_file):
        if not latent_file or not folder_paths.exists_annotated_filepath(latent_file):
            return f"no such latent file in the input directory: {latent_file!r}"
        return True

    @classmethod
    def IS_CHANGED(cls, model, latent_file):
        # The file's content, as ComfyUI's own loaders fingerprint theirs: a
        # name written again with another latent is another input.
        with open(folder_paths.get_annotated_filepath(latent_file), "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()

    def load(self, model, latent_file):
        path = folder_paths.get_annotated_filepath(latent_file)
        with open(path, "rb") as fh:
            magic = fh.read(6)
        if magic != b"\x93NUMPY":
            # np.load would call anything else pickled data, which names a
            # cause the file does not have.
            raise ValueError(f"{latent_file} is no .npy file")
        array = np.asarray(np.load(path, allow_pickle=False), dtype=np.float32)
        # [C, h, w] as the keep node writes it, or with the batch axis a
        # decoder wants; anything else is not a latent of one picture.
        if array.ndim == 3:
            array = array[None]
        if array.ndim != 4:
            raise ValueError(f"a latent of shape [C, h, w] is required, "
                             f"{latent_file} holds {tuple(array.shape)}")
        if not np.isfinite(array).all():
            raise ValueError(f"{latent_file} carries values that are not numbers")
        inner = getattr(model, "model", model)
        # The step the keep node inverted, applied again: into the space the
        # VAE decode reads. See the header.
        samples = inner.process_latent_out(torch.from_numpy(array))
        return ({"samples": samples},)


NODE_CLASS_MAPPINGS = {
    "AI4ArtsEdKeepLatent": AI4ArtsEdKeepLatent,
    "AI4ArtsEdLoadKeptLatent": AI4ArtsEdLoadKeptLatent,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AI4ArtsEdKeepLatent": "AI4ArtsEd Keep Latent",
    "AI4ArtsEdLoadKeptLatent": "AI4ArtsEd Load Kept Latent",
}
