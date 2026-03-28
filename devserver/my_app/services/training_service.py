import base64
import os
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

# Logger Setup
logger = logging.getLogger(__name__)

# Derived paths
KOHYA_VENV = KOHYA_DIR / "venv"
DATASET_BASE_DIR = TRAINING_DATASET_DIR
OUTPUT_DIR = LORA_OUTPUT_DIR
LOG_DIR = TRAINING_LOG_DIR

# Ensure directories exist
DATASET_BASE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

class TrainingService:
    def __init__(self):
        self._current_process: Optional[subprocess.Popen] = None
        self._training_status = {
            "is_training": False,
            "project_name": None,
            "progress": 0,
            "current_step": 0,
            "total_steps": 0,
            "log_lines": [],
            "error": None
        }
        self._log_lock = threading.Lock()

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
            from config import COMFYUI_PORT
            response = requests.post(
                f"http://127.0.0.1:{COMFYUI_PORT}/free",
                json={"unload_models": True},
                timeout=30
            )
            if response.status_code == 200:
                results["actions"].append("ComfyUI models unloaded")
            else:
                results["actions"].append(f"ComfyUI returned status {response.status_code}")
        except requests.exceptions.ConnectionError:
            results["actions"].append("ComfyUI not running (OK)")
        except Exception as e:
            results["errors"].append(f"ComfyUI unload failed: {e}")

        # Step 4: Unload llama-server models
        try:
            from config import LLAMA_SERVER_URL
            llm_url = LLAMA_SERVER_URL.rstrip('/')

            # Get list of loaded models
            loaded_response = requests.get(
                f"{llm_url}/models",
                timeout=10
            )

            if loaded_response.status_code == 200:
                loaded_data = loaded_response.json()
                models = loaded_data if isinstance(loaded_data, list) else loaded_data.get("data", [])

                if not models:
                    results["actions"].append("llama-server: no models loaded")
                else:
                    unloaded = []
                    for model_info in models:
                        model_name = model_info.get("id", model_info.get("name", ""))
                        if model_name:
                            try:
                                requests.post(
                                    f"{llm_url}/models/unload",
                                    json={"model": model_name},
                                    timeout=30
                                )
                                unloaded.append(model_name)
                            except Exception:
                                pass

                    if unloaded:
                        results["actions"].append(f"llama-server unloaded: {', '.join(unloaded)}")
                    else:
                        results["actions"].append("LLM: no models to unload")
        except requests.exceptions.ConnectionError:
            results["actions"].append("LLM not running (OK)")
        except Exception as e:
            results["errors"].append(f"LLM unload failed: {e}")

        # Step 4b: Unload GPU Service LLM models
        try:
            from config import GPU_SERVICE_URL
            llm_models_response = requests.get(
                f"{GPU_SERVICE_URL}/api/llm/models",
                timeout=10
            )
            if llm_models_response.ok:
                llm_unloaded = []
                for model_info in llm_models_response.json().get("models", []):
                    mid = model_info.get("model_id", "")
                    if mid:
                        try:
                            requests.post(
                                f"{GPU_SERVICE_URL}/api/llm/unload",
                                json={"model_id": mid},
                                timeout=30
                            )
                            llm_unloaded.append(mid)
                        except Exception:
                            pass
                if llm_unloaded:
                    results["actions"].append(f"GPU Service LLM unloaded: {', '.join(llm_unloaded)}")
                else:
                    results["actions"].append("GPU Service LLM: no models loaded")
        except requests.exceptions.ConnectionError:
            results["actions"].append("GPU Service not running (OK)")
        except Exception as e:
            results["errors"].append(f"GPU Service LLM unload failed: {e}")

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
        Determines optimal training parameters based on VRAM.
        SD3.5 Large LoRA Training VRAM Requirements (Approximate @ 1024x1024):
        - Batch 1, GradCheckpointing=True: ~18-22 GB
        - Batch 1, GradCheckpointing=False: ~30-35 GB
        - Batch 4, GradCheckpointing=False: ~48-50 GB
        - Batch 8, GradCheckpointing=False: ~80+ GB
        """
        params = {
            "batch_size": 1,
            "gradient_checkpointing": True,
            "cache_latents_to_disk": True,
            "persistent_workers": True,
            "workers": 4
        }

        if vram_gb >= 90: # RTX 6000 Ada 96GB (or A100 80G+, H100, etc.)
            params.update({
                "batch_size": 8,
                "gradient_checkpointing": False, # Max speed with abundant VRAM
                "workers": 16
            })
        elif vram_gb >= 80: # A100 80G, H100, or Multi-GPU setups acting as one
            params.update({
                "batch_size": 8,
                "gradient_checkpointing": False, # Max speed
                "workers": 16
            })
        elif vram_gb >= 40: # RTX 6000 Ada (48GB), A6000 (48GB), A40
            params.update({
                "batch_size": 4, # Safer fit than 8
                "gradient_checkpointing": False, # Speed priority
                "workers": 8
            })
        elif vram_gb >= 24: # RTX 3090/4090 (24GB)
            params.update({
                "batch_size": 1,
                "gradient_checkpointing": True, # Needed to fit
                "workers": 8
            })
        else: # < 24GB (e.g. 16GB Cards) - might OOM for SD3.5 Large
            params.update({
                "batch_size": 1,
                "gradient_checkpointing": True,
                "cache_latents_to_disk": True,
                "workers": 4
            })
            logger.warning("VRAM < 24GB. Training SD3.5 Large might fail or be extremely slow.")

        logger.info(f"Auto-Config for {vram_gb}GB VRAM: {params}")
        return params

    def create_project(self, project_name: str, images: List[Any], trigger_word: str):
        """Prepares dataset and config for a new training project."""
        if self._training_status["is_training"]:
            raise Exception("Training already in progress")

        # 1. Parse trigger words (comma-separated)
        # First trigger = primary (folder name), rest = additional tags
        triggers = [t.strip() for t in trigger_word.split(',') if t.strip()]
        primary_trigger = triggers[0] if triggers else "lora"
        all_tags = ", ".join(triggers) if triggers else ""

        logger.info(f"Triggers: primary='{primary_trigger}', all_tags='{all_tags}'")

        # 2. Setup Directories
        # Sanitation: simple alphanumeric only for folder safety
        safe_name = "".join([c for c in project_name if c.isalnum() or c in ('-', '_')])
        project_dir = DATASET_BASE_DIR / safe_name
        image_dir = project_dir / "images"

        # 40_ prefix means 40 repeats per image (standard for LoRA)
        # Primary trigger in folder name for DreamBooth compatibility
        img_folder_name = f"40_{primary_trigger}"
        final_image_dir = image_dir / img_folder_name

        if project_dir.exists():
            shutil.rmtree(project_dir)
        final_image_dir.mkdir(parents=True, exist_ok=True)

        # 3. Save Images
        for img in images:
            file_path = final_image_dir / img.filename
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(img.file, buffer)

        # Store trigger info for captioning step (runs in training thread)
        self._pending_caption_info = {
            "image_dir": final_image_dir,
            "trigger": all_tags if all_tags else primary_trigger,
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
            
        return {
            "project_name": safe_name,
            "image_count": len(images),
            "config_path": str(config_path),
            "hardware_info": {
                "vram_gb": vram,
                "config_used": optim_params
            }
        }

    def _generate_sd35_config(self, project_dir: Path, image_dir: Path, output_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generates TOML config for SD 3.5 Large with dynamic hardware params"""
        # SD3.5 Large LoRAs get "sd35_" prefix automatically
        prefixed_name = f"sd35_{output_name}"
        return {
            "model_arguments": {
                "pretrained_model_name_or_path": str(SD35_LARGE_MODEL_PATH),
                "vae": "" # Built-in VAE
            },
            "dataset_arguments": {
                "train_data_dir": str(image_dir),
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
            if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
        )

        if not images:
            return

        self._append_log(f"Auto-captioning {len(images)} images with {CAPTION_VLM_MODEL}...")

        # Short prompt avoids triggering qwen3-vl thinking mode
        vlm_prompt = (
            "Describe this photograph in one dense sentence for AI image training. "
            "Include subject, composition, tonal qualities, photographic technique, and lighting."
        )

        for i, img_path in enumerate(images, 1):
            txt_path = img_path.with_suffix(".txt")
            try:
                # Stage 1: VLM describes the image
                img_b64 = base64.b64encode(img_path.read_bytes()).decode()
                from config import LLAMA_SERVER_URL
                llm_url = LLAMA_SERVER_URL.rstrip('/')
                vlm_model = CAPTION_VLM_MODEL.replace("local/", "") if CAPTION_VLM_MODEL.startswith("local/") else CAPTION_VLM_MODEL

                if not img_b64.startswith("data:"):
                    img_b64_url = f"data:image/jpeg;base64,{img_b64}"
                else:
                    img_b64_url = img_b64

                resp = requests.post(
                    f"{llm_url}/v1/chat/completions",
                    json={
                        "model": vlm_model,
                        "messages": [{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": vlm_prompt},
                                {"type": "image_url", "image_url": {"url": img_b64_url}},
                            ],
                        }],
                        "stream": False,
                        "max_tokens": 500,
                        "temperature": 0.3,
                    },
                    timeout=120,
                )
                resp.raise_for_status()
                choice = resp.json().get("choices", [{}])[0]
                raw = choice.get("message", {}).get("content", "").strip()

                # Stage 2: If VLM output looks like reasoning, extract via fast text LLM
                caption = self._cleanup_caption(raw) if raw else ""

                if caption:
                    txt_path.write_text(f"{trigger}, {caption}", encoding="utf-8")
                    self._append_log(f"  [{i}/{len(images)}] {img_path.name} — OK")
                else:
                    txt_path.write_text(trigger, encoding="utf-8")
                    self._append_log(f"  [{i}/{len(images)}] {img_path.name} — empty response, trigger only")

            except Exception as e:
                # Graceful degradation: write trigger only
                txt_path.write_text(trigger, encoding="utf-8")
                self._append_log(f"  [{i}/{len(images)}] {img_path.name} — FAILED ({e}), trigger only")

        self._append_log("Captioning complete.")
        self._pending_caption_info = None

    def _cleanup_caption(self, raw_text: str) -> str:
        """Extract a clean caption from VLM output that may contain chain-of-thought reasoning."""
        raw_text = raw_text.strip().strip('"\'')

        # If it already looks like a clean description, return as-is
        reasoning_prefixes = ("We are", "Okay,", "Let me", "The user", "I need", "First,", "Got it", "So,", "Alright")
        if not raw_text.startswith(reasoning_prefixes):
            return raw_text

        # Chain-of-thought detected — use a non-thinking LLM to extract the caption
        try:
            from config import LLAMA_SERVER_URL
            llm_url = LLAMA_SERVER_URL.rstrip('/')
            cleanup_model = CAPTION_CLEANUP_MODEL.replace("local/", "") if CAPTION_CLEANUP_MODEL.startswith("local/") else CAPTION_CLEANUP_MODEL

            resp = requests.post(
                f"{llm_url}/v1/chat/completions",
                json={
                    "model": cleanup_model,
                    "messages": [{
                        "role": "user",
                        "content": (
                            "The following text contains reasoning AND a final image description sentence. "
                            "Extract ONLY the final descriptive sentence. Output nothing else, no quotes.\n\n"
                            + raw_text[:3000]
                        ),
                    }],
                    "stream": False,
                    "max_tokens": 300,
                    "temperature": 0.1,
                },
                timeout=60,
            )
            resp.raise_for_status()
            choice = resp.json().get("choices", [{}])[0]
            cleaned = choice.get("message", {}).get("content", "").strip().strip('"\'')
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

        safe_name = "".join([c for c in project_name if c.isalnum() or c in ('-', '_')])
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

        # Construct Command
        # We execute via 'bash -c' to source the venv correctly
        # Explicitly pass Text Encoders as CLI args (paths from config.py)
        cmd = [
            "/bin/bash", "-c",
            f"source {KOHYA_VENV}/bin/activate && "
            f"python {KOHYA_DIR}/sd-scripts/sd3_train_network.py --config_file {config_path} "
            f"--clip_l={CLIP_L_PATH} --clip_g={CLIP_G_PATH} --t5xxl={T5XXL_PATH}"
        ]

        def run_proc():
            try:
                # Auto-caption images before training starts
                self._generate_captions()

                self._current_process = subprocess.Popen(
                    cmd,
                    cwd=str(KOHYA_DIR),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, # Merge stderr into stdout
                    text=True,
                    bufsize=1
                )

                # Stream logs
                if self._current_process.stdout:
                    for line in iter(self._current_process.stdout.readline, ''):
                        self._append_log(line)
                        if "steps:" in line.lower():
                            pass

                    self._current_process.stdout.close()
                return_code = self._current_process.wait()

                if return_code == 0:
                    self._append_log("TRAINING SUCCESSFUL! LoRA saved to ComfyUI.")
                else:
                    self._append_log(f"TRAINING FAILED with code {return_code}")
                    self._training_status["error"] = f"Process exited with {return_code}"

            except Exception as e:
                self._append_log(f"CRITICAL ERROR: {str(e)}")
                self._training_status["error"] = str(e)
            finally:
                # Post-training cleanup
                self._post_training_cleanup()
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

    def stop_training(self):
        if self._current_process:
            self._current_process.terminate()
            self._append_log("Training manually stopped by user.")
            return True
        return False
        
    def delete_project_files(self, project_name: str):
        """GDPR Compliance: Deletes ALL training images for a project."""
        if self._training_status["is_training"] and self._training_status["project_name"] == project_name:
            return False # Cannot delete while training
            
        safe_name = "".join([c for c in project_name if c.isalnum() or c in ('-', '_')])
        project_dir = DATASET_BASE_DIR / safe_name
        
        if project_dir.exists():
            try:
                shutil.rmtree(project_dir)
                return True
            except Exception as e:
                logger.error(f"Failed to delete project files for {safe_name}: {e}")
                return False
        return True # Already deleted or didn't exist

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