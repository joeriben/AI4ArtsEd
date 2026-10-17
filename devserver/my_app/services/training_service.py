import base64
import os
import secrets
import re
import signal
import shutil
import subprocess
import threading
import time
import toml
import gc
import requests
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging

# Optional torch import for VRAM management
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

from config import (
    KOHYA_DIR,
    LORA_OUTPUT_DIR,
    TRAINING_DATASET_DIR,
    TRAINING_LOG_DIR,
    SD35_LARGE_MODEL_PATH,
    CLIP_L_PATH,
    CLIP_G_PATH,
    T5XXL_PATH,
    CAPTION_VLM_MODEL,
    CAPTION_CLEANUP_MODEL,
    CAPTION_ENABLED,
)

from my_app.services.resona_hardware import (
    CO2_PER_KWH_GRAMS,
    TREE_G_CO2_PER_HOUR,
    read_gpu_power,
)
# The GPU service answers a refused model load with 503 and a sentence saying
# what was missing. An HTTPError stringifies to the status and the URL alone, so
# the sentence reached these logs as "503 Server Error" and the reason a whole
# set of images went undescribed was gone. One implementation for every direct
# consumer of those endpoints.
from my_app.services.llm_client import _body_reason

# The run-length range this place states to whoever stands in front of it
# (i18n training.info.limitationDuration). The estimate before a run spans
# it; the line after a run uses the time the run actually took.
EST_RUN_HOURS_MIN = 1.0
EST_RUN_HOURS_MAX = 3.0

# Logger Setup
logger = logging.getLogger(__name__)

# How often each image is shown per epoch. Lives here because the page states
# it and the folder name carries it: two places, one value.
DATASET_REPEATS = 40

# How long a stopped run is given to leave on its own before it is ended.
STOP_GRACE_SECONDS = 20

# The extension the captions are written under, and the one the trainer is
# told to look for. sd-scripts defaults to ".caption" (train_util.py,
# --caption_extension); writing ".txt" without saying so meant the trainer
# found no caption file for any image and fell back to the class token, so
# every image was learned under the trigger word alone. One name, both ends.
CAPTION_EXT = ".txt"

# The image types the caption step reads and the trainer buckets. The upload
# checks against the same list, so nothing gets stored that would be skipped
# later without a word.
CAPTION_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")

# The one instruction the describing model gets. Short on purpose: a longer
# one puts qwen3-vl into thinking mode and the answer arrives as reasoning.
CAPTION_VLM_PROMPT = (
    "Describe this photograph in one dense sentence for AI image training. "
    "Include subject, composition, tonal qualities, photographic technique, and lighting."
)

# Where images wait between being dropped and a run being started. They are
# described here, read back by whoever dropped them, and moved into the
# project when the run starts. Old ones are swept on every new drop, because
# they are somebody's photographs and nothing else deletes them.
STAGING_MAX_AGE_SECONDS = 6 * 3600

# How long to wait before asking the describing model again. Sized for a model
# that is still being loaded onto the card, which is what the first image of a
# set normally runs into.
CAPTION_RETRY_WAIT_SECONDS = 12

# The plant-wide GPU slot, taken for the length of a run. The kind is the one
# the gate knows as a long hold (gpu_service/services/gpu_admission.py,
# LONG_HOLD_KINDS): while it is held, every other heavy operation is turned
# away at once instead of queueing for hours behind it.
GPU_LEASE_KIND = "lora_training"

# How long a run waits for a picture that is already being drawn. Long enough
# for a generation in flight, far short of the gate's own budget: something
# that is about to take hours can wait two minutes, and a card still busy after
# that is busy with something this must not push aside without saying so.
GPU_LEASE_WAIT_SECONDS = 120

# What the run will hold. SD3.5 Large at batch 1 with gradient checkpointing
# peaks around 48 GB; the gate uses the figure to make room before admitting.
GPU_LEASE_REQUIRED_MB = 48 * 1024

# The name every adapter trained here carries. Written by the config below
# and read back by the listing — one place decides what belongs to this
# place, so a downloaded LoRA in the same directory stays out of it.
SD35_LORA_PREFIX = "sd35_"

# Where a project keeps the trigger it was trained under. Written since
# 2026-08-29; older projects are read back out of their captions.
TRIGGER_FILE = "trigger.txt"
_EPOCH_SUFFIX = re.compile(r"^(?P<stem>.+)-(?P<epoch>\d{6})$")

# Derived paths
KOHYA_VENV = KOHYA_DIR / "venv"
DATASET_BASE_DIR = TRAINING_DATASET_DIR
STAGING_DIR = DATASET_BASE_DIR / ".staging"
OUTPUT_DIR = LORA_OUTPUT_DIR
LOG_DIR = TRAINING_LOG_DIR

# Ensure directories exist
DATASET_BASE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

def _safe_project_name(project_name: str) -> str:
    """Der Projektname, wie er ein Verzeichnis heissen darf.

    Nur Buchstaben, Ziffern, Bindestrich und Unterstrich ueberleben — und es
    muss etwas uebrig bleiben. Ohne diese Pruefung ergibt ein Name wie "***"
    den leeren String, `DATASET_BASE_DIR / ""` zeigt auf das Wurzelverzeichnis,
    und ein Loeschen trifft die Bilder aller Projekte statt der eines.
    """
    safe = "".join([c for c in project_name if c.isalnum() or c in ('-', '_')])
    if not safe:
        raise ValueError("project_name needs at least one letter, digit, - or _")
    return safe


class TrainingService:
    def __init__(self):
        self._current_process: Optional[subprocess.Popen] = None
        self._training_status = {
            "is_training": False,
            "project_name": None,
            "progress": 0,
            "current_step": 0,
            "total_steps": 0,
            # Where the step counting started and when, so the pace is measured
            # over the steps this process actually watched, and when the last
            # one came, so a stalled trainer stops being quoted.
            "first_step_at": None,
            "first_step_no": 0,
            "last_step_at": None,
            "log_lines": [],
            "error": None
        }
        self._log_lock = threading.Lock()
        # Staged image sets, by token: what a model said about each image
        # before a run was started. Lives only as long as the process, like
        # the staging directory it points at.
        self._descriptions: Dict[str, Dict[str, Any]] = {}

    def get_gpu_vram(self) -> int:
        """Detects available VRAM in GB using nvidia-smi."""
        try:
            # Run nvidia-smi to get total memory (in MiB)
            # Query format: memory.total
            result = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                encoding="utf-8"
            )
            # Sum up memory of all GPUs (if multi-gpu) or take the first one
            # For simplicity in Kohya single-process, we usually target GPU 0
            # But let's assume we use the first GPU found.
            lines = result.strip().split('\n')
            if not lines:
                return 0
            
            total_mib = int(lines[0].strip())
            total_gb = total_mib / 1024
            logger.info(f"Detected GPU VRAM: {total_gb:.1f} GB")
            return int(total_gb)
        except Exception as e:
            logger.error(f"Failed to detect VRAM: {e}")
            return 24 # Fallback assumption (Consumer High-End)

    def _get_vram_status(self) -> Dict[str, Any]:
        """
        Query nvidia-smi for detailed VRAM status.
        Returns dict with total_gb, used_gb, free_gb, usage_percent.
        """
        try:
            result = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=memory.total,memory.used,memory.free",
                 "--format=csv,noheader,nounits"],
                encoding="utf-8"
            )

            lines = result.strip().split('\n')
            if not lines:
                return {"error": "No GPU detected", "total_gb": 0, "used_gb": 0, "free_gb": 0, "usage_percent": 0}

            # Parse first GPU
            parts = lines[0].strip().split(', ')
            total_mib = int(parts[0])
            used_mib = int(parts[1])
            free_mib = int(parts[2])

            total_gb = round(total_mib / 1024, 1)
            used_gb = round(used_mib / 1024, 1)
            free_gb = round(free_mib / 1024, 1)
            usage_percent = round((used_mib / total_mib) * 100, 1) if total_mib > 0 else 0

            return {
                "total_gb": total_gb,
                "used_gb": used_gb,
                "free_gb": free_gb,
                "usage_percent": usage_percent
            }
        except Exception as e:
            logger.error(f"Failed to get VRAM status: {e}")
            return {"error": str(e), "total_gb": 0, "used_gb": 0, "free_gb": 0, "usage_percent": 0}

    def clear_vram_thoroughly(self) -> Dict[str, Any]:
        """
        Thoroughly clears VRAM by:
        1. Python garbage collection
        2. torch.cuda.empty_cache() + synchronize
        3. Unload ComfyUI models via /free endpoint
        4. Unload LLM models
        5. Wait and do final cleanup pass

        Returns dict with cleanup results and before/after VRAM stats.
        """
        results = {
            "before": self._get_vram_status(),
            "actions": [],
            "errors": [],
            "after": None
        }

        # Step 1: Python garbage collection
        try:
            gc.collect()
            results["actions"].append("gc.collect() completed")
        except Exception as e:
            results["errors"].append(f"gc.collect failed: {e}")

        # Step 2: PyTorch CUDA cleanup
        if TORCH_AVAILABLE:
            try:
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()
                    results["actions"].append("torch.cuda.empty_cache() + synchronize() completed")
            except Exception as e:
                results["errors"].append(f"torch CUDA cleanup failed: {e}")
        else:
            results["actions"].append("torch not available, skipping CUDA cleanup")

        # Step 3: Unload ComfyUI models
        try:
            # Through the gate, with the card held (services/gpu_gate.free_comfyui).
            from my_app.services.gpu_gate import free_comfyui
            from my_app.services.gpu_lease_client import GpuBusyError
            response = free_comfyui("training: clear VRAM before a run", timeout=30)
            if response.status_code == 200:
                results["actions"].append("ComfyUI models unloaded")
            else:
                results["actions"].append(f"ComfyUI returned status {response.status_code}")
        except GpuBusyError as e:
            results["errors"].append(f"ComfyUI unload refused: the card is held ({e})")
        except requests.exceptions.ConnectionError:
            results["actions"].append("ComfyUI not running (OK)")
        except Exception as e:
            results["errors"].append(f"ComfyUI unload failed: {e}")

        # Step 4: the local language models are ComfyUI's since stage 3 of
        # the move (services/llm_client); step 3 took them off the card.
        results["actions"].append("LLM: held by ComfyUI, unloaded with its models")

        # Step 5: Wait for VRAM to actually free
        time.sleep(3)

        # Step 6: Final cleanup pass
        try:
            gc.collect()
            if TORCH_AVAILABLE and torch.cuda.is_available():
                torch.cuda.empty_cache()
            results["actions"].append("Final cleanup pass completed")
        except Exception as e:
            results["errors"].append(f"Final cleanup failed: {e}")

        # Get final VRAM status
        results["after"] = self._get_vram_status()

        # Calculate freed memory
        if results["before"].get("used_gb") and results["after"].get("used_gb"):
            freed_gb = results["before"]["used_gb"] - results["after"]["used_gb"]
            results["freed_gb"] = round(freed_gb, 1)
            logger.info(f"VRAM cleanup freed {freed_gb:.1f} GB")

        return results

    def calculate_training_params(self, vram_gb: int) -> Dict[str, Any]:
        """
        What the card changes about a run — and what it must not change.

        The batch size stays at 1 on every card. It used to rise with VRAM (8
        on 96 GB, 1 on 24 GB), and since the learning rate did not move with
        it, the same project reached 4000 optimizer steps on the production
        card and 500 on the development card. Same images, same epochs, a
        different LoRA. A card may decide how a run FITS; how far it learns is
        not its business.

        What is left to the card is memory and throughput only:
        - gradient checkpointing off where VRAM allows (~30-35 GB at batch 1)
        - the number of data loader workers

        SD3.5 Large at 1024x1024, batch 1: ~18-22 GB with checkpointing,
        ~30-35 GB without.
        """
        params = {
            "batch_size": 1,
            "gradient_checkpointing": True,
            "cache_latents_to_disk": True,
            "persistent_workers": True,
            "workers": 4
        }

        if vram_gb >= 80: # A100 80G, H100, RTX 6000 Ada 96GB
            params.update({
                "gradient_checkpointing": False, # fits without, so faster
                "workers": 16
            })
        elif vram_gb >= 40: # RTX 6000 Ada (48GB), A6000 (48GB), A40
            params.update({
                "gradient_checkpointing": False,
                "workers": 8
            })
        elif vram_gb >= 24: # RTX 3090/4090/5090 (24-32GB)
            params.update({
                "gradient_checkpointing": True, # needed to fit
                "workers": 8
            })
        else: # < 24GB (e.g. 16GB Cards) - might OOM for SD3.5 Large
            params.update({
                "gradient_checkpointing": True,
                "cache_latents_to_disk": True,
                "workers": 4
            })
            logger.warning("VRAM < 24GB. Training SD3.5 Large might fail or be extremely slow.")

        logger.info(f"Auto-Config for {vram_gb}GB VRAM: {params}")
        return params

    def stage_and_describe(self, images: List[Any], token: Optional[str] = None) -> Dict[str, Any]:
        """Take the dropped images and let a model say what it sees on each.

        The sentence written here is what the trainer learns the images AS, so
        it belongs in front of whoever dropped them, before a run starts and
        not in a file nobody opens. Describing runs in a thread; the caller
        reads the list as it fills.

        With a token, the images join a set that is already here and only the
        new ones are described — dropping a second handful must not cost the
        first handful's minutes on the card again.
        """
        suffixes = self._checked_suffixes(images)

        state = self._descriptions.get(token) if token else None
        if state is not None and (STAGING_DIR / token).is_dir():
            staged = STAGING_DIR / token
            start_at = len(state["items"])
        else:
            self._sweep_staging()
            token = secrets.token_hex(8)
            staged = STAGING_DIR / token
            staged.mkdir(parents=True, exist_ok=True)
            state = {"running": False, "items": []}
            self._descriptions[token] = state
            start_at = 0

        fresh = []
        for i, (img, suffix) in enumerate(zip(images, suffixes), start_at + 1):
            name = f"{i:03d}{suffix}"
            with open(staged / name, "wb") as buffer:
                shutil.copyfileobj(img.file, buffer)
            item = {"file": name, "caption": None, "failed": False}
            state["items"].append(item)
            fresh.append(item)

        state["running"] = True
        thread = threading.Thread(target=self._describe_staged, args=(token, fresh), daemon=True)
        thread.start()

        return {"token": token, "running": True, "items": state["items"]}

    def _describe_staged(self, token: str, items: List[Dict[str, Any]]):
        """Fill the given images with sentences, one at a time.

        An image the model could not answer for keeps a null caption and is
        marked: an empty field and a failed field mean different things to
        whoever is about to correct them.
        """
        state = self._descriptions.get(token)
        if not state:
            return
        staged = STAGING_DIR / token
        try:
            for item in items:
                if not CAPTION_ENABLED:
                    item["failed"] = True
                    continue
                try:
                    item["caption"] = self._describe_image(staged / item["file"])
                except Exception as e:
                    logger.warning(
                        "[TRAINING] describing %s failed: %s%s",
                        item["file"], e, _body_reason(getattr(e, "response", None)),
                    )
                    item["failed"] = True
        finally:
            state["running"] = False

    def description_status(self, token: str) -> Optional[Dict[str, Any]]:
        """How far the describing got, and what it said. None for a token this
        place does not know — a swept staging set among them."""
        state = self._descriptions.get(token)
        if not state:
            return None
        return {"running": state["running"], "items": state["items"]}

    def _checked_suffixes(self, images: List[Any]) -> List[str]:
        """The extension decides whether the describing model and the trainer
        read a file at all, so it is checked before anything is written."""
        suffixes = []
        for img in images:
            suffix = Path(img.filename or "").suffix.lower()
            if suffix not in CAPTION_IMAGE_EXTS:
                raise ValueError(
                    f"unsupported image type {suffix or '(none)'!r}; "
                    f"expected one of {', '.join(CAPTION_IMAGE_EXTS)}"
                )
            suffixes.append(suffix)
        return suffixes

    def _sweep_staging(self):
        """Staged images are somebody's photographs and nothing else removes
        them; a set that was never started goes after STAGING_MAX_AGE_SECONDS."""
        if not STAGING_DIR.exists():
            return
        cutoff = time.time() - STAGING_MAX_AGE_SECONDS
        for path in STAGING_DIR.iterdir():
            try:
                if path.is_dir() and path.stat().st_mtime < cutoff:
                    shutil.rmtree(path, ignore_errors=True)
                    self._descriptions.pop(path.name, None)
            except OSError:
                continue

    def create_project(self, project_name: str, images: List[Any], trigger_word: str,
                       staging_token: Optional[str] = None,
                       captions: Optional[List[str]] = None,
                       owner_id: Optional[int] = None,
                       course_id: Optional[int] = None):
        """Prepares dataset and config for a new training project.

        With a staging token the images are already here and already described;
        the sentences come from the caller, because they may have been
        corrected since. Without one, nothing was shown and the training thread
        describes as before.

        `owner_id` and `course_id` are who was logged in at this place and the
        course that was active; both go into the register row (issue #70).
        """
        if self._training_status["is_training"]:
            raise Exception("Training already in progress")

        # 1. Parse trigger words (comma-separated)
        # First trigger = primary (folder name), rest = additional tags
        triggers = [t.strip() for t in trigger_word.split(',') if t.strip()]
        primary_trigger = triggers[0] if triggers else "lora"
        all_tags = ", ".join(triggers) if triggers else ""

        logger.info(f"Triggers: primary='{primary_trigger}', all_tags='{all_tags}'")

        # 2. Setup Directories
        safe_name = _safe_project_name(project_name)
        project_dir = DATASET_BASE_DIR / safe_name
        image_dir = project_dir / "images"

        # The `N_` prefix is how sd-scripts reads the repeat count.
        # Primary trigger in folder name for DreamBooth compatibility. The word
        # stays as it was typed; only what would leave the directory is dropped,
        # because sd-scripts reads this folder name as the fallback token.
        safe_trigger = re.sub(r"[^\w\- ]", "", primary_trigger, flags=re.UNICODE).strip()
        img_folder_name = f"{DATASET_REPEATS}_{safe_trigger or 'lora'}"
        final_image_dir = image_dir / img_folder_name

        staged = STAGING_DIR / staging_token if staging_token else None
        if staged is not None and not staged.is_dir():
            raise ValueError("the dropped images are no longer here; drop them again")

        # The uploaded name never reaches the filesystem. Its extension decides
        # whether the caption step and the trainer read the file at all, and it
        # is checked here — before anything is deleted.
        suffixes = [] if staged is not None else self._checked_suffixes(images)

        if project_dir.exists():
            shutil.rmtree(project_dir)
        final_image_dir.mkdir(parents=True, exist_ok=True)

        trigger = all_tags if all_tags else primary_trigger

        if staged is not None:
            # 3a. The images are already here and already described. The
            #     sentences are the caller's, corrected or not; the trigger is
            #     put in front of them here, where it belongs.
            staged_files = sorted(
                p for p in staged.iterdir()
                if p.suffix.lower() in CAPTION_IMAGE_EXTS
            )
            texts = list(captions or [])
            for i, src in enumerate(staged_files):
                dest = final_image_dir / src.name
                shutil.move(str(src), str(dest))
                caption = (texts[i] if i < len(texts) else "") or ""
                caption = " ".join(caption.split())
                dest.with_suffix(CAPTION_EXT).write_text(
                    f"{trigger}, {caption}" if caption else trigger, encoding="utf-8"
                )
            image_count = len(staged_files)
            shutil.rmtree(staged, ignore_errors=True)
            self._descriptions.pop(staging_token, None)
            # Nothing left for the training thread to describe.
            self._pending_caption_info = None
        else:
            # 3b. Nothing was shown, so nothing was corrected: the training
            #     thread describes the images as it always did.
            for i, (img, suffix) in enumerate(zip(images, suffixes), 1):
                file_path = final_image_dir / f"{i:03d}{suffix}"
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(img.file, buffer)
            image_count = len(images)
            self._pending_caption_info = {
                "image_dir": final_image_dir,
                "trigger": trigger,
            }

        # 4. Detect Hardware & Optimize Config
        vram = self.get_gpu_vram()
        optim_params = self.calculate_training_params(vram)

        # 4. Create Config (prefix is determined by the model-specific method)
        config = self._generate_sd35_config(
            project_dir=project_dir,
            image_dir=image_dir,
            output_name=safe_name,
            params=optim_params
        )
        
        config_path = project_dir / "train_config.toml"
        with open(config_path, "w") as f:
            toml.dump(config, f)

        # The word every caption of this project was written under, kept where
        # the project is. Without it a later run can only guess what to put in
        # a prompt to call this adapter — the folder name holds the FIRST
        # trigger alone, and the captions hold all of them.
        (project_dir / TRIGGER_FILE).write_text(trigger, encoding="utf-8")

        # The register row (issue #70): the file the trainer will write, the
        # project name as its name, the trigger, the models this place trains
        # for, and who trained it — released to the course the training was
        # made in. A training outside a course writes no row: a personal
        # training (a face, most often) stands in no register and reaches no
        # workshop by being trained; the Settings register the file if it is
        # ever to be offered. A row that exists stands: this route needs no
        # login, and a project name typed twice must not rewrite a platform
        # row. A register that cannot be written must not stop a training
        # that can run.
        if course_id is not None:
            try:
                from my_app.services.lora_register import register_adapter
                register_adapter(
                    file=f"{SD35_LORA_PREFIX}{safe_name}.safetensors",
                    name=project_name,
                    trigger=trigger,
                    owner_id=owner_id,
                    course_id=course_id,
                    visibility="course",
                    keep_existing=True,
                )
            except Exception as e:
                logger.warning(f"[LORA-REGISTER] project '{safe_name}' not registered: {e}")

        return {
            "project_name": safe_name,
            "image_count": image_count,
            "config_path": str(config_path),
            "hardware_info": {
                "vram_gb": vram,
                "config_used": optim_params
            }
        }

    def _generate_sd35_config(self, project_dir: Path, image_dir: Path, output_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generates TOML config for SD 3.5 Large with dynamic hardware params"""
        # SD3.5 Large LoRAs get "sd35_" prefix automatically
        prefixed_name = f"{SD35_LORA_PREFIX}{output_name}"
        return {
            "model_arguments": {
                "pretrained_model_name_or_path": str(SD35_LARGE_MODEL_PATH),
                "vae": "" # Built-in VAE
            },
            "dataset_arguments": {
                "train_data_dir": str(image_dir),
                "caption_extension": CAPTION_EXT,
                "resolution": "1024,1024",
                "enable_bucket": True,
                "min_bucket_reso": 512,
                "max_bucket_reso": 2048,
                "batch_size": params["batch_size"]
            },
            "training_arguments": {
                "output_dir": str(OUTPUT_DIR),
                "output_name": prefixed_name,
                "save_precision": "bf16",
                "mixed_precision": "bf16",
                "max_train_epochs": 10,
                "save_every_n_epochs": 2,
                "learning_rate": 4e-4,
                "lr_scheduler": "cosine",
                "optimizer_type": "AdamW8bit",
                "gradient_checkpointing": params["gradient_checkpointing"],
                "gradient_accumulation_steps": 1,
                "cache_latents": True,
                "cache_latents_to_disk": params["cache_latents_to_disk"],
                # Text encoder output caching for memory efficiency
                "cache_text_encoder_outputs": True,
                "cache_text_encoder_outputs_to_disk": True,
                "logging_dir": str(LOG_DIR),
                "bf16": True,
                "persistent_data_loader_workers": params["persistent_workers"],
                "max_data_loader_n_workers": params["workers"]
            },
            "network_arguments": {
                "network_module": "networks.lora_sd3",
                "network_dim": 32,
                "network_alpha": 16,
                "network_train_unet_only": False 
            },
            "optimization_arguments": {
                "xformers": True # SD3 often prefers Flash Attention
            }
        }

    def _generate_captions(self):
        """Auto-caption training images using a VLM via GPU Service.

        Two-stage approach: qwen3-vl describes the image (may include chain-of-thought),
        then a fast text LLM extracts the clean descriptive sentence.
        """
        info = getattr(self, "_pending_caption_info", None)
        if not info or not CAPTION_ENABLED:
            return

        image_dir: Path = info["image_dir"]
        trigger: str = info["trigger"]
        images = sorted(
            p for p in image_dir.iterdir()
            if p.suffix.lower() in CAPTION_IMAGE_EXTS
        )

        if not images:
            return

        self._append_log(f"Auto-captioning {len(images)} images with {CAPTION_VLM_MODEL}...")

        for i, img_path in enumerate(images, 1):
            txt_path = img_path.with_suffix(CAPTION_EXT)
            try:
                caption = self._describe_image(img_path)

                if caption:
                    txt_path.write_text(f"{trigger}, {caption}", encoding="utf-8")
                    self._append_log(f"  [{i}/{len(images)}] {img_path.name} — OK")
                else:
                    txt_path.write_text(trigger, encoding="utf-8")
                    self._append_log(f"  [{i}/{len(images)}] {img_path.name} — empty response, trigger only")

            except Exception as e:
                # Graceful degradation: write trigger only. The service's own
                # sentence comes along: this log is what somebody reads while a
                # run is going, and a whole set that came back uncaptioned for
                # want of VRAM said only "503 Server Error" here.
                txt_path.write_text(trigger, encoding="utf-8")
                self._append_log(
                    f"  [{i}/{len(images)}] {img_path.name} — FAILED ({e})"
                    f"{_body_reason(getattr(e, 'response', None))}, trigger only"
                )

        self._append_log("Captioning complete.")
        self._pending_caption_info = None

    def _describe_image(self, img_path: Path, attempts: int = 3) -> str:
        """One image, one sentence. Raises when the model cannot be reached —
        callers decide what an unanswered image means for them.

        A cold model is the normal first case: the GPU service answers with an
        error while it loads, and without a second try the first image of every
        set would carry a description it never got. Retried against the SAME
        model — this is waiting for a load, not reaching for a substitute.

        A 503 ends the attempts on the spot. The GPU service sends it once it
        has read the card and refused the load, so it reports a measurement
        rather than a model still arriving. The waits of
        CAPTION_RETRY_WAIT_SECONDS fall inside the window in which the
        coordinator leaves ComfyUI alone after a fruitless ask, so a repeat
        meets the same shortfall and only delays the report of it. The
        service's own sentence travels out with the error instead.
        """
        last_error: Optional[Exception] = None
        for attempt in range(1, attempts + 1):
            try:
                return self._request_description(img_path)
            except Exception as e:
                last_error = e
                reason = _body_reason(getattr(e, "response", None))
                logger.info(
                    "[TRAINING] describing %s: attempt %d/%d failed (%s)%s",
                    img_path.name, attempt, attempts, e, reason,
                )
                refused = (
                    isinstance(e, requests.exceptions.HTTPError)
                    and getattr(e.response, "status_code", None) == 503
                )
                if refused:
                    logger.warning(
                        "[TRAINING] describing %s: the GPU service refused the load "
                        "(%s)%s — no further attempt is made",
                        img_path.name, e, reason,
                    )
                    raise
                if attempt < attempts:
                    time.sleep(CAPTION_RETRY_WAIT_SECONDS)
        raise last_error  # type: ignore[misc]

    def _request_description(self, img_path: Path) -> str:
        """The call itself, once, through the local backend (run by ComfyUI).
        The client logs the cause of a failed call and answers None; that is
        raised here, so the attempts above see it."""
        from my_app.services.llm_backend import get_llm_backend
        img_b64 = base64.b64encode(img_path.read_bytes()).decode()
        result = get_llm_backend().chat(
            model=CAPTION_VLM_MODEL,
            messages=[{"role": "user", "content": CAPTION_VLM_PROMPT}],
            images=[img_b64],
            temperature=0.3,
        )
        if result is None:
            raise RuntimeError(f"{CAPTION_VLM_MODEL} answered nothing for {img_path.name}")
        raw = (result.get("content") or "").strip()
        return self._cleanup_caption(raw) if raw else ""

    def _cleanup_caption(self, raw_text: str) -> str:
        """Extract a clean caption from VLM output that may contain chain-of-thought reasoning."""
        raw_text = raw_text.strip().strip('"\'')

        # If it already looks like a clean description, return as-is
        reasoning_prefixes = ("We are", "Okay,", "Let me", "The user", "I need", "First,", "Got it", "So,", "Alright")
        if not raw_text.startswith(reasoning_prefixes):
            return raw_text

        # Chain-of-thought detected — use a non-thinking LLM to extract the caption
        try:
            from my_app.services.llm_backend import get_llm_backend
            result = get_llm_backend().chat(
                model=CAPTION_CLEANUP_MODEL,
                messages=[{
                    "role": "user",
                    "content": (
                        "The following text contains reasoning AND a final image description sentence. "
                        "Extract ONLY the final descriptive sentence. Output nothing else, no quotes.\n\n"
                        + raw_text[:3000]
                    ),
                }],
                temperature=0.1,
                enable_thinking=False,
            )
            if result is None:
                raise RuntimeError(f"{CAPTION_CLEANUP_MODEL} answered nothing")
            cleaned = (result.get("content") or "").strip().strip('"\'')
            return cleaned if cleaned and len(cleaned) > 30 else raw_text
        except Exception as e:
            logger.warning(f"Caption cleanup failed: {e}")
            return raw_text

    def start_training_process(self, project_name: str, auto_clear_vram: bool = True, min_free_gb: float = 50.0):
        """
        Starts the training subprocess.

        Args:
            project_name: Name of the project to train
            auto_clear_vram: If True, automatically clears VRAM before training
            min_free_gb: Minimum free VRAM in GB required to start training

        Returns:
            True if training started, False if already training

        Raises:
            FileNotFoundError: If config not found
            RuntimeError: If insufficient VRAM after clearing
        """
        if self._training_status["is_training"]:
            return False

        from my_app.services.gpu_lease_client import gpu_lease_sync, GpuBusyError

        safe_name = _safe_project_name(project_name)
        config_path = DATASET_BASE_DIR / safe_name / "train_config.toml"

        if not config_path.exists():
            raise FileNotFoundError(f"Config not found for project {safe_name}")

        self._reset_status(safe_name)

        # Auto-clear VRAM if enabled
        if auto_clear_vram:
            self._append_log("Checking VRAM status...")
            vram_status = self._get_vram_status()

            if vram_status.get("free_gb", 0) < min_free_gb:
                self._append_log(f"Free VRAM: {vram_status.get('free_gb', 0):.1f} GB (need {min_free_gb:.1f} GB)")
                self._append_log("Clearing VRAM... (unloading ComfyUI, LLM)")

                cleanup_result = self.clear_vram_thoroughly()

                for action in cleanup_result.get("actions", []):
                    self._append_log(f"  • {action}")

                if cleanup_result.get("freed_gb"):
                    self._append_log(f"Freed {cleanup_result['freed_gb']:.1f} GB VRAM")

                # Check if we have enough now
                final_status = cleanup_result.get("after", {})
                if final_status.get("free_gb", 0) < min_free_gb:
                    error_msg = (
                        f"Insufficient VRAM after cleanup: {final_status.get('free_gb', 0):.1f} GB free "
                        f"(need {min_free_gb:.1f} GB). Close other GPU applications and try again."
                    )
                    self._append_log(f"ERROR: {error_msg}")
                    self._training_status["error"] = error_msg
                    raise RuntimeError(error_msg)

                self._append_log(f"VRAM ready: {final_status.get('free_gb', 0):.1f} GB free")
            else:
                self._append_log(f"VRAM OK: {vram_status.get('free_gb', 0):.1f} GB free")

        self._training_status["is_training"] = True

        # The trainer is started by the interpreter of its own environment,
        # not through `source venv/bin/activate`. That script carries the
        # absolute path the environment was created under, and this tree has
        # moved since; activation then put a directory that does not exist in
        # front of PATH, `python` fell through to the pyenv shim, and the
        # trainer ran without its packages. `bin/python` finds its
        # site-packages from where it lies, whatever `activate` claims.
        # Text encoders are passed explicitly (paths from config.py).
        cmd = [
            str(KOHYA_VENV / "bin" / "python"),
            str(KOHYA_DIR / "sd-scripts" / "sd3_train_network.py"),
            "--config_file", str(config_path),
            f"--clip_l={CLIP_L_PATH}",
            f"--clip_g={CLIP_G_PATH}",
            f"--t5xxl={T5XXL_PATH}",
        ]

        def run_proc():
            started_at = time.time()
            watts = (read_gpu_power() or {}).get("limit_watts")
            # Whether the card was ever touched. A run turned away at the gate
            # waited, it did not train, and the energy line must not report the
            # waiting as consumption.
            ran_on_card = False
            try:
                # Auto-caption images before training starts. OUTSIDE the GPU
                # lease on purpose: describing runs on the gpu_service, which
                # takes the same slot, so asking for it while holding it would
                # be waiting for oneself. Nothing to do when the images were
                # described and corrected before the start.
                self._generate_captions()

                # From here the card belongs to this run. The gate turns every
                # other heavy operation away for as long as the lease is held,
                # and takes it back by itself if this process dies without
                # releasing: the lease lives on a heartbeat and is reaped when
                # that stops. An unreachable gate does not stop a run - a
                # missing route must not cost a workshop its training - but it
                # is said out loud, because then nothing is held back.
                with gpu_lease_sync(
                    kind=GPU_LEASE_KIND,
                    model_id="sd35_large",
                    required_mb=GPU_LEASE_REQUIRED_MB,
                    label=f"LoRA training: {safe_name}",
                    timeout_s=GPU_LEASE_WAIT_SECONDS,
                ) as lease_token:
                    if lease_token is None:
                        self._append_log(
                            "GPU slot not reachable - this run holds nothing back; "
                            "image generation may take the memory it needs."
                        )
                    else:
                        self._append_log(
                            "GPU slot held - image generation is turned away until this run ends."
                        )

                    ran_on_card = True
                    self._current_process = subprocess.Popen(
                        cmd,
                        cwd=str(KOHYA_DIR),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, # Merge stderr into stdout
                        text=True,
                        bufsize=1,
                        # Its own process group. The trainer forks sixteen data
                        # loader workers, and a signal to the parent alone left
                        # them holding the whole model on the card.
                        start_new_session=True,
                    )

                    # Stream logs
                    if self._current_process.stdout:
                        for line in iter(self._current_process.stdout.readline, ''):
                            self._append_log(line)
                            if "steps:" in line.lower():
                                self._note_progress(line)

                        self._current_process.stdout.close()
                    return_code = self._current_process.wait()

                    if return_code == 0:
                        self._append_log("TRAINING SUCCESSFUL! LoRA saved to ComfyUI.")
                    else:
                        self._append_log(f"TRAINING FAILED with code {return_code}")
                        self._training_status["error"] = f"Process exited with {return_code}"

            except GpuBusyError as e:
                # The card is drawing something else and did not come free
                # within the wait. Nothing was started, so nothing is half done.
                self._append_log(f"NOT STARTED: the card is in use - {e}")
                self._training_status["error"] = f"The card is in use: {e}"
            except Exception as e:
                self._append_log(f"CRITICAL ERROR: {str(e)}")
                self._training_status["error"] = str(e)
            finally:
                # Post-training cleanup
                self._post_training_cleanup()
                if ran_on_card:
                    self._log_energy_estimate(started_at, watts)
                self._training_status["is_training"] = False
                self._current_process = None

        # Run in separate thread to not block API
        t = threading.Thread(target=run_proc, daemon=True)
        t.start()

        return True

    def _post_training_cleanup(self):
        """Clean up VRAM after training completes."""
        try:
            self._append_log("Running post-training cleanup...")
            gc.collect()
            if TORCH_AVAILABLE and torch.cuda.is_available():
                torch.cuda.empty_cache()
            self._append_log("Cleanup complete.")
        except Exception as e:
            logger.error(f"Post-training cleanup failed: {e}")

    def training_setup(self) -> Dict[str, Any]:
        """What a run will be, read from the configuration a run gets.

        Built by the same two functions that produce the trainer's config, so
        the page cannot state a value the run does not use. The one figure not
        in that config is the repeat count, which sd-scripts reads out of the
        dataset folder name; it comes from the constant both places share.
        """
        params = self.calculate_training_params(self.get_gpu_vram())
        cfg = self._generate_sd35_config(Path("/"), Path("/"), "setup", params)
        dataset = cfg["dataset_arguments"]
        training = cfg["training_arguments"]
        network = cfg["network_arguments"]
        return {
            "repeats": DATASET_REPEATS,
            "epochs": training["max_train_epochs"],
            "save_every_n_epochs": training["save_every_n_epochs"],
            "learning_rate": training["learning_rate"],
            "lr_scheduler": training["lr_scheduler"],
            "optimizer": training["optimizer_type"],
            "network_dim": network["network_dim"],
            "network_alpha": network["network_alpha"],
            "train_text_encoder": not network["network_train_unet_only"],
            "resolution": dataset["resolution"],
            "bucket_min": dataset["min_bucket_reso"],
            "bucket_max": dataset["max_bucket_reso"],
            "batch_size": dataset["batch_size"],
        }

    def energy_estimate(self) -> Optional[Dict[str, Any]]:
        """What a run costs, before anybody starts one.

        The same upper-bound arithmetic the log closes a run with, applied to
        the run-length range this place states instead of a measured runtime.
        None when the power limit is unreadable - the page then says nothing
        rather than an invented number.
        """
        watts = (read_gpu_power() or {}).get("limit_watts")
        if not watts:
            return None

        def at(hours: float):
            wh = watts * hours
            co2 = (wh / 1000.0) * CO2_PER_KWH_GRAMS
            return wh, co2, co2 / TREE_G_CO2_PER_HOUR / 24.0

        wh_lo, co2_lo, days_lo = at(EST_RUN_HOURS_MIN)
        wh_hi, co2_hi, days_hi = at(EST_RUN_HOURS_MAX)
        return {
            "watts": round(watts),
            "hours_min": round(EST_RUN_HOURS_MIN),
            "hours_max": round(EST_RUN_HOURS_MAX),
            "kwh_min": round(wh_lo / 1000.0, 1),
            "kwh_max": round(wh_hi / 1000.0, 1),
            "co2_g_min": round(co2_lo),
            "co2_g_max": round(co2_hi),
            "tree_days_min": round(days_lo),
            "tree_days_max": round(days_hi),
            "co2_factor": CO2_PER_KWH_GRAMS,
        }

    def _log_energy_estimate(self, started_at: float, watts: Optional[float]):
        """Close the run with what it cost, estimated.

        Hours of a fully loaded GPU with generation blocked throughout is the
        most expensive thing this platform does, so the log says so in the same
        terms as the rest of the platform (resona_hardware). Estimated at the
        card's power limit — an upper bound, not a meter reading, and it says
        which it is. The tree is the platform's established comparison; a
        second one would mean a factor nobody here has a source for.
        """
        minutes = (time.time() - started_at) / 60.0
        if not watts or minutes <= 0:
            self._append_log(
                f"Run took {minutes:.0f} min. Energy: GPU power not readable."
            )
            return
        wh = watts * (minutes / 60.0)
        co2 = (wh / 1000.0) * CO2_PER_KWH_GRAMS
        tree_hours = co2 / TREE_G_CO2_PER_HOUR
        tree = (f"~{tree_hours / 24.0:.0f} days" if tree_hours >= 48
                else f"~{tree_hours:.0f} hours")
        self._append_log(
            f"Run took {minutes:.0f} min. Estimated at the card's {watts:.0f} W "
            f"limit: ~{wh:.0f} Wh, ~{co2:.0f} g CO2 "
            f"(factor {CO2_PER_KWH_GRAMS} g/kWh, German grid). "
            f"A tree reabsorbs that in {tree}."
        )

    def stop_training(self):
        """End the run — including the workers it started.

        `terminate()` reached the trainer alone. Its sixteen data loader
        workers stayed, orphaned at PID 1, with the whole model on the card:
        the page said "stopped", the run kept the card, and every image
        generation ran into a refusal. The signal goes to the process group
        now, and what still stands after the grace period is ended.
        """
        proc = self._current_process
        if not proc:
            return False

        self._append_log("Training manually stopped by user.")

        def signal_group(sig) -> None:
            try:
                os.killpg(os.getpgid(proc.pid), sig)
            except (ProcessLookupError, PermissionError):
                # No group to reach — the process itself is all that is left.
                (proc.terminate if sig == signal.SIGTERM else proc.kill)()

        signal_group(signal.SIGTERM)
        try:
            proc.wait(timeout=STOP_GRACE_SECONDS)
            return True
        except subprocess.TimeoutExpired:
            pass

        self._append_log(
            f"Trainer still there after {STOP_GRACE_SECONDS}s — ending it."
        )
        signal_group(signal.SIGKILL)
        try:
            proc.wait(timeout=STOP_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            self._append_log("Trainer survived the end signal; check by hand.")
        return True
        
    def project_trigger(self, project: str) -> str:
        """The word a project's images were captioned under.

        Three sources, in falling order of exactness:
        1. `trigger.txt`, written when the project was created.
        2. What every caption of the project begins with. The trigger stands in
           front of each one, the descriptions differ, so the longest prefix
           they all share IS the trigger — cut back to its last comma, in case
           two descriptions happen to open with the same word.
        3. The image folder, `40_<trigger>`. It holds the FIRST trigger only,
           which is why it comes last.

        An empty string where a project has been deleted; the surface then
        leaves the field to be written by hand rather than inventing a word.
        """
        project_dir = DATASET_BASE_DIR / project
        recorded = project_dir / TRIGGER_FILE
        # UnicodeDecodeError is a ValueError, not an OSError, and it would
        # travel out of list_trained_loras — which resolve_loras also calls, so
        # one unreadable file would take down every run that carries a LoRA.
        try:
            if recorded.is_file():
                held = recorded.read_text(encoding="utf-8").strip()
                if held:
                    return held
        except (OSError, ValueError):
            pass

        image_dir = project_dir / "images"
        try:
            folders = sorted(d for d in image_dir.iterdir() if d.is_dir())
        except OSError:
            return ""
        if not folders:
            return ""
        folder = folders[0]

        captions = sorted(folder.glob(f"*{CAPTION_EXT}"))
        texts = []
        for path in captions[:12]:
            try:
                texts.append(path.read_text(encoding="utf-8").strip())
            except (OSError, ValueError):
                continue
        if len(texts) >= 2:
            prefix = texts[0]
            for other in texts[1:]:
                cut = 0
                while cut < len(prefix) and cut < len(other) and prefix[cut] == other[cut]:
                    cut += 1
                prefix = prefix[:cut]
                if not prefix:
                    break
            if prefix:
                # Where every caption is the SAME string, the captions ARE the
                # trigger and nothing may be cut off it. That is the ordinary
                # state of a project whose describer was unreachable: the
                # trigger was written alone into every file. Cutting at the last
                # comma there would drop the last tag —
                # `19th_century_photography, landscape, historic photograph`
                # would come back one tag short and go into the prompts that
                # way.
                if all(t == prefix for t in texts):
                    return prefix.strip()
                # Otherwise the shared prefix runs into a description, and the
                # trigger ends at the last comma before it.
                cut = prefix.rfind(",")
                if cut > 0:
                    return prefix[:cut].strip()

        name = folder.name
        head = f"{DATASET_REPEATS}_"
        return name[len(head):].strip() if name.startswith(head) else name.strip()

    def list_trained_loras(self) -> List[Dict[str, Any]]:
        """The adapters this place has produced, newest first.

        Kohya writes the finished one as `<prefix><project>.safetensors` and an
        intermediate every two epochs as `...-000004.safetensors`. Both are
        listed: at which epoch a run was still worth looking at is a question
        that can only be asked if the epochs are reachable.
        """
        if not OUTPUT_DIR.exists():
            return []

        entries = []
        # One lookup per project, not per file: a project with five epochs would
        # otherwise read its captions five times over.
        triggers: Dict[str, str] = {}
        for path in OUTPUT_DIR.glob(f"{SD35_LORA_PREFIX}*.safetensors"):
            stem = path.stem[len(SD35_LORA_PREFIX):]
            epoch = None
            match = _EPOCH_SUFFIX.match(stem)
            if match:
                stem = match.group("stem")
                epoch = int(match.group("epoch"))
            try:
                stat = path.stat()
            except OSError:
                continue
            if stem not in triggers:
                triggers[stem] = self.project_trigger(stem)
            entries.append({
                "file": path.name,
                "project": stem,
                "epoch": epoch,
                "size_mb": round(stat.st_size / (1024 * 1024), 1),
                "modified": stat.st_mtime,
                # What to write into a prompt to call this adapter, empty where
                # the project it came from is gone.
                "trigger": triggers[stem],
            })

        entries.sort(key=lambda e: (e["modified"], e["file"]), reverse=True)
        return entries

    def resolve_loras(self, entries: Any) -> List[Dict[str, Any]]:
        """What a client asked for, turned into what a run may load.

        The name reaches the diffusers backend as `LORA_DIR / name`, so it is
        matched against the files this place actually produced rather than
        against a pattern. Strength is held inside what a LoRA scale means;
        outside that range the adapter either does nothing or drowns the model.
        """
        if not entries:
            return []
        if not isinstance(entries, list):
            raise ValueError("loras must be a list")

        known = {e["file"] for e in self.list_trained_loras()}
        resolved = []
        for entry in entries:
            name = entry.get("name") if isinstance(entry, dict) else None
            if name not in known:
                raise ValueError(f"unknown LoRA: {name!r}")
            try:
                strength = float(entry.get("strength", 1.0))
            except (TypeError, ValueError):
                raise ValueError(f"strength for {name!r} is not a number")
            resolved.append({
                "name": name,
                "strength": max(0.0, min(2.0, strength)),
            })
        return resolved

    def delete_project_files(self, project_name: str):
        """GDPR Compliance: Deletes ALL training images for a project."""
        if self._training_status["is_training"] and self._training_status["project_name"] == project_name:
            return False # Cannot delete while training
            
        safe_name = _safe_project_name(project_name)
        project_dir = DATASET_BASE_DIR / safe_name
        
        if project_dir.exists():
            try:
                shutil.rmtree(project_dir)
                return True
            except Exception as e:
                logger.error(f"Failed to delete project files for {safe_name}: {e}")
                return False
        return True # Already deleted or didn't exist

    # The trainer's own progress bar, and nothing else: `steps:  12%|###| 480/
    # 4000 [10:23<...]`. Anchored at the whole shape on purpose — a bare pair of
    # numbers before a bracket appears in resolutions, epochs and dataset counts
    # too, and a wrong pair here becomes a wrong hour on somebody's screen.
    _STEP_RE = re.compile(r"^steps:\s*\d+%\|[^|]*\|\s*(\d+)\s*/\s*(\d+)")

    # Under this many watched steps the pace is still the first steps' pace —
    # the slowest of a run — and a remaining time taken there is wrong by
    # minutes while reading like a promise.
    MIN_STEPS_FOR_ESTIMATE = 10

    # A progress bar this old means the trainer stopped moving. The pace from
    # before the stall would go on quoting a remaining time that shrinks while
    # nothing happens, so the estimate withdraws instead.
    STALE_PROGRESS_S = 600

    def _note_progress(self, line: str) -> None:
        """Read the step counter off the trainer's progress bar.

        Without this the platform can say that the card is training and nothing
        about how long that lasts — which is the one question somebody who was
        just turned away has.

        tqdm redraws with a carriage return, so one read line can hold a whole
        run of updates. The last one that parses is the current state.
        """
        current = total = None
        for part in reversed(str(line).split("\r")):
            m = self._STEP_RE.match(part.strip())
            if not m:
                continue
            try:
                current, total = int(m.group(1)), int(m.group(2))
            except ValueError:
                return
            break
        if current is None or total is None or total <= 0 or current > total:
            return
        # Same lock as the log this line came from: the estimate is read from
        # request threads while this writes, and a reader must not pair the
        # step of one line with the total of another.
        with self._log_lock:
            st = self._training_status
            st["current_step"] = current
            st["total_steps"] = total
            st["progress"] = round(current * 100.0 / total)
            st["last_step_at"] = time.time()
            if st.get("first_step_at") is None:
                st["first_step_at"] = time.time()
                st["first_step_no"] = current

    def remaining_estimate_s(self) -> Optional[float]:
        """Seconds until this training is done, or None when nothing measured.

        None travels all the way to the surface, which has its own sentence for
        the unknown case. A zero, or a guess, would be read as a promise about
        a card that is held for hours.
        """
        with self._log_lock:
            st = dict(self._training_status)
        if not st.get("is_training"):
            return None
        current = st.get("current_step") or 0
        total = st.get("total_steps") or 0
        since = st.get("first_step_at")
        last = st.get("last_step_at")
        if not since or total <= current:
            return None
        if not last or (time.time() - last) > self.STALE_PROGRESS_S:
            return None
        watched = current - (st.get("first_step_no") or 0)
        if watched < self.MIN_STEPS_FOR_ESTIMATE:
            return None
        elapsed = time.time() - since
        if elapsed <= 0:
            return None
        return (elapsed / watched) * (total - current)

    def get_status(self, include_vram: bool = True):
        """
        Get current training status.

        Args:
            include_vram: If True, includes current VRAM metrics

        Returns:
            Dict with training status and optionally VRAM info
        """
        status = self._training_status.copy()

        if include_vram:
            status["vram"] = self._get_vram_status()

        return status

    def _reset_status(self, project_name):
        self._training_status = {
            "is_training": False,
            "project_name": project_name,
            "progress": 0,
            "current_step": 0,
            "total_steps": 0,
            "first_step_at": None,
            "first_step_no": 0,
            "last_step_at": None,
            "log_lines": [],
            "error": None
        }

    def _append_log(self, line: str):
        line = line.strip()
        if not line: return
        with self._log_lock:
            self._training_status["log_lines"].append(line)
            # Keep log size manageable (last 1000 lines)
            if len(self._training_status["log_lines"]) > 1000:
                self._training_status["log_lines"].pop(0)

# Global Instance
training_service = TrainingService()