"""comfy.model_patcher.ModelPatcher stood in for, as far as the package touches it.

Shared by every fixture that loads the ComfyUI package without a card
(test_local_llm_finite, test_text_probes): _card.GoneWhenTakenOff subclasses
comfy.model_patcher.ModelPatcher, so the stub has to be a class, and the two
fixtures have to stand in the same one.
"""


class ModelPatcher:
    """comfy.model_patcher.ModelPatcher as far as the package touches it:
    the attributes __init__ writes on the model, the sizes, and the
    unload path (detach -> unpatch_model moves the model to device_to
    and zeroes the counters), which _card.GoneWhenTakenOff overrides."""

    def __init__(self, model, load_device, offload_device, size=0, weight_inplace_update=False):
        import uuid
        self.model = model
        self.load_device = load_device
        self.offload_device = offload_device
        self.size = size
        self.patches_uuid = uuid.uuid4()
        self.backup = {}
        self.object_patches_backup = {}
        if not hasattr(model, "device"):
            model.device = offload_device
        for name in ("model_loaded_weight_memory", "lowvram_patch_counter"):
            if not hasattr(model, name):
                setattr(model, name, 0)
        if not hasattr(model, "model_lowvram"):
            model.model_lowvram = False

    def model_size(self):
        return sum(t.numel() * t.element_size() for t in self.model.state_dict().values())

    def loaded_size(self):
        return self.model.model_loaded_weight_memory

    def current_loaded_device(self):
        return self.model.device

    def eject_model(self):
        pass

    def unpatch_hooks(self):
        pass

    def unpin_all_weights(self):
        pass

    def partially_unload(self, device_to, memory_to_free=0, force_patch_weights=False):
        return memory_to_free

    def unpatch_model(self, device_to=None, unpatch_weights=True):
        if unpatch_weights and device_to is not None:
            self.model.to(device_to)
            self.model.device = device_to
            self.model.model_loaded_weight_memory = 0

    def detach(self, unpatch_all=True):
        self.unpatch_model(self.offload_device, unpatch_weights=unpatch_all)
        return self.model

    def load(self, device_to=None, lowvram_model_memory=0, force_patch_weights=False, full_load=False):
        if device_to is not None:
            self.model.to(device_to)
            self.model.device = device_to
        self.model.model_loaded_weight_memory = self.model_size()
        self.model.current_weight_patches_uuid = self.patches_uuid
