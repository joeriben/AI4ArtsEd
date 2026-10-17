"""A textured mesh from one picture with Hunyuan3D 2, as a ComfyUI node.

The DevServer's Hunyuan3D client (my_app/services/hunyuan3d_client.py)
queues one prompt of this node per mesh; the GLB comes back as a file the
node announces under "3d", the way ComfyUI's own SaveGLB announces one.
Everything that holds the models is in _hunyuan3d.py.
"""
from . import _hunyuan3d, _media_files


class ai4artsed_hunyuan3d:
    @classmethod
    def INPUT_TYPES(cls):
        dirs = _hunyuan3d.installed_dirs()
        return {
            "required": {
                "model_name": (dirs or ["(no checkpoint under models/hunyuan3d)"],),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "num_inference_steps": ("INT", {"default": 50, "min": 1, "max": 200}),
                "guidance_scale": ("FLOAT", {"default": 7.5, "min": 0.0, "max": 30.0, "step": 0.1}),
                "octree_resolution": ("INT", {"default": 256, "min": 64, "max": 512, "step": 32}),
            },
            "optional": {
                "image": ("IMAGE",),
                "image_base64": ("STRING", {"multiline": True, "default": ""}),
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "run"
    CATEGORY = "AI4ArtsEd"
    OUTPUT_NODE = True

    def run(self, model_name, seed, num_inference_steps, guidance_scale, octree_resolution,
            image=None, image_base64=""):
        pil = _media_files.pil_image(image_base64, image, mode="RGBA")
        if pil is None:
            raise ValueError("a picture is required: image_base64 or an IMAGE input")
        out = _hunyuan3d.generate(model_name, pil, seed=int(seed), num_inference_steps=int(num_inference_steps),
                                  guidance_scale=float(guidance_scale), octree_resolution=int(octree_resolution))
        announced = _media_files.announce(out["glb"], ".glb")
        return {
            "ui": {
                "3d": [announced],
                "size_bytes": [out["size_bytes"]],
                "seed": [out["seed"]],
                "generation_time_ms": [out["generation_time_ms"]],
            },
        }
