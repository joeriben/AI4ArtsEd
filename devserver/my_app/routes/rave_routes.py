"""
RAVE Training Controller Routes

Manages RAVE model training via subprocess calls to rave.sh.
Supports v1 and v2 runs via ?run=v1|v2 query parameter.
Includes dataset pipeline (normalize, preprocess) management.
"""

import logging
import os
import subprocess
import json
import re
import threading
from datetime import datetime
from pathlib import Path
from flask import Blueprint, jsonify, request, send_file

logger = logging.getLogger(__name__)

rave_bp = Blueprint('rave', __name__)

RAVE_DIR = Path.home() / "ai" / "rave_research"
RAVE_SH = RAVE_DIR / "rave.sh"
PYTHON = RAVE_DIR / "venv" / "bin" / "python"
RAVE_BIN = RAVE_DIR / "venv" / "bin" / "rave"
TEST_OUTPUT = RAVE_DIR / "test_output"
RUNS_DIR = RAVE_DIR / "runs"
SCHEDULE_FILE = RAVE_DIR / ".rave_schedule.json"
EVAL_LOG = RAVE_DIR / "eval_logs" / "eval_log.csv"

AUDIO_DIR = RAVE_DIR / "dataset" / "audio"
AUDIO_NORMALIZED_DIR = RAVE_DIR / "dataset" / "audio_normalized"
PREPROCESSED_V2_DIR = RAVE_DIR / "dataset" / "preprocessed_v2"
PIPELINE_PID_FILE = RAVE_DIR / ".rave_pipeline.pid"
PIPELINE_LOG_FILE = RAVE_DIR / "pipeline.log"
PIPELINE_STATE_FILE = RAVE_DIR / ".rave_pipeline_state.json"

RUN_CONFIGS = {
    "v1": {"pattern": "mini70_v1_*", "name": "mini70_v1"},
    "v2": {"pattern": "mini70_v2_*", "name": "mini70_v2"},
}

DEFAULT_SLOT = {
    "start": "00:00", "stop": "00:00",
    "days": {"mon": False, "tue": False, "wed": False, "thu": False, "fri": False, "sat": False, "sun": False},
}

DEFAULT_SCHEDULE = {
    "enabled": False,
    "manual_override": False,
    "run_version": "v2",
    "slots": [
        {"start": "22:00", "stop": "07:00", "days": {"mon": True, "tue": True, "wed": True, "thu": True, "fri": True, "sat": True, "sun": True}},
        DEFAULT_SLOT.copy(),
        DEFAULT_SLOT.copy(),
    ],
}


def _get_run_version():
    """Get run version from query parameter, default v2."""
    return request.args.get("run", "v2")


def _pid_file(version):
    return RAVE_DIR / f".rave_training_{version}.pid"


def _log_file(version):
    return RAVE_DIR / f"training_{version}.log"


def _rave_env(version):
    """Build environment with RUN= set for rave.sh."""
    env = {**os.environ, "TORCH_FLOAT32_MATMUL_PRECISION": "high", "RUN": version}
    return env


def _load_schedule():
    if SCHEDULE_FILE.exists():
        try:
            return json.loads(SCHEDULE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return json.loads(json.dumps(DEFAULT_SCHEDULE))


def _save_schedule(schedule):
    SCHEDULE_FILE.write_text(json.dumps(schedule, indent=2))


def _slot_active_now(slot):
    """Check if a single time slot is active right now."""
    now = datetime.now()
    day_key = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][now.weekday()]

    if not slot.get("days", {}).get(day_key, False):
        return False

    start = slot.get("start", "00:00")
    stop = slot.get("stop", "00:00")
    if start == stop:
        return False

    sh, sm = int(start.split(":")[0]), int(start.split(":")[1])
    eh, em = int(stop.split(":")[0]), int(stop.split(":")[1])
    start_min = sh * 60 + sm
    stop_min = eh * 60 + em
    now_min = now.hour * 60 + now.minute

    if start_min < stop_min:
        return start_min <= now_min < stop_min
    else:
        return now_min >= start_min or now_min < stop_min


def _should_train_now(schedule):
    """Check if training should be running based on any active slot."""
    if not schedule.get("enabled"):
        return None

    return any(_slot_active_now(slot) for slot in schedule.get("slots", []))


def _is_training_running(version):
    """Check if training process is alive via PID file or process scan."""
    pid_file = _pid_file(version)
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)
            return True, pid
        except (ProcessLookupError, ValueError):
            pass

    config = RUN_CONFIGS.get(version, RUN_CONFIGS["v2"])
    try:
        result = subprocess.run(
            ["pgrep", "-f", f"rave train.*{config['name']}"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            pid = int(result.stdout.strip().split('\n')[0])
            return True, pid
    except Exception:
        pass

    return False, None


def _find_run_dir(version):
    """Find the training run directory for given version."""
    if not RUNS_DIR.exists():
        return None
    config = RUN_CONFIGS.get(version, RUN_CONFIGS["v2"])
    for d in sorted(RUNS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if d.is_dir() and d.name.startswith(config["name"] + "_"):
            return d
    return None


def _find_latest_checkpoint(run_dir):
    """Find the most recent checkpoint file."""
    if not run_dir:
        return None
    ckpts = list(run_dir.rglob("last*.ckpt"))
    if not ckpts:
        ckpts = list(run_dir.rglob("best.ckpt"))
    if not ckpts:
        return None
    return str(max(ckpts, key=lambda p: p.stat().st_mtime))


def _find_exported_model(run_dir):
    """Find exported .ts model file."""
    if not run_dir:
        return None
    models = list(run_dir.glob("*streaming.ts"))
    return str(models[0]) if models else None


def _parse_log_tail(version, n=10):
    """Read last N lines of training log and extract epoch/step info."""
    log_file = _log_file(version)
    if not log_file.exists():
        return [], None, None

    lines = log_file.read_text().strip().split('\n')
    tail = lines[-n:] if len(lines) >= n else lines

    epoch = None
    step = None
    for line in reversed(lines):
        if epoch is None:
            m = re.search(r'Epoch\s+(\d+)', line)
            if m:
                epoch = int(m.group(1))
        if step is None:
            m = re.search(r'(\d+)/6250', line)
            if m:
                step = int(m.group(1))
        if epoch is not None and step is not None:
            break

    return tail, epoch, step


def _run_rave_command(command, version, timeout=300):
    """Run a rave.sh subcommand and return output."""
    try:
        result = subprocess.run(
            [str(RAVE_SH), command],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(RAVE_DIR),
            env=_rave_env(version),
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": "Command timed out"}
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": str(e)}


@rave_bp.route('/api/rave/status', methods=['GET'])
def rave_status():
    """Get current training status."""
    version = _get_run_version()
    running, pid = _is_training_running(version)
    run_dir = _find_run_dir(version)
    checkpoint = _find_latest_checkpoint(run_dir)
    exported_model = _find_exported_model(run_dir) if run_dir else None
    log_tail, epoch, step = _parse_log_tail(version, 15)

    test_files = []
    if TEST_OUTPUT.exists():
        test_files = sorted([f.name for f in TEST_OUTPUT.glob("*.wav")])

    total_steps = (epoch * 6250 + (step or 0)) if epoch is not None else None

    # Check if other version is also running
    other_version = "v1" if version == "v2" else "v2"
    other_running, _ = _is_training_running(other_version)

    return jsonify({
        "run_version": version,
        "running": running,
        "pid": pid,
        "epoch": epoch,
        "step": step,
        "total_steps": total_steps,
        "max_steps": 6000000,
        "checkpoint": checkpoint,
        "exported_model": exported_model,
        "run_dir": str(run_dir) if run_dir else None,
        "log_tail": log_tail,
        "test_files": test_files,
        "other_version_running": other_running,
    })


@rave_bp.route('/api/rave/start', methods=['POST'])
def rave_start():
    """Start fresh training."""
    version = _get_run_version()
    running, _ = _is_training_running(version)
    if running:
        return jsonify({"success": False, "error": "Training already running"}), 409

    log_file = _log_file(version)
    try:
        proc = subprocess.Popen(
            [str(RAVE_SH), "start"],
            cwd=str(RAVE_DIR),
            stdout=open(str(log_file), 'w'),
            stderr=subprocess.STDOUT,
            env=_rave_env(version),
        )
        logger.info(f"[RAVE] {version} training started (PID {proc.pid})")
        return jsonify({"success": True, "pid": proc.pid})
    except Exception as e:
        logger.error(f"[RAVE] Start failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@rave_bp.route('/api/rave/resume', methods=['POST'])
def rave_resume():
    """Resume training from latest checkpoint."""
    version = _get_run_version()
    running, _ = _is_training_running(version)
    if running:
        return jsonify({"success": False, "error": "Training already running"}), 409

    run_dir = _find_run_dir(version)
    checkpoint = _find_latest_checkpoint(run_dir)
    if not checkpoint:
        return jsonify({"success": False, "error": "No checkpoint found"}), 404

    log_file = _log_file(version)
    try:
        proc = subprocess.Popen(
            [str(RAVE_SH), "resume"],
            cwd=str(RAVE_DIR),
            stdout=open(str(log_file), 'a'),
            stderr=subprocess.STDOUT,
            env=_rave_env(version),
        )
        logger.info(f"[RAVE] {version} training resumed from {checkpoint} (PID {proc.pid})")
        return jsonify({"success": True, "pid": proc.pid, "checkpoint": checkpoint})
    except Exception as e:
        logger.error(f"[RAVE] Resume failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@rave_bp.route('/api/rave/stop', methods=['POST'])
def rave_stop():
    """Stop running training."""
    version = _get_run_version()
    running, pid = _is_training_running(version)
    if not running:
        return jsonify({"success": True, "message": "Not running"})

    result = _run_rave_command("stop", version, timeout=60)
    logger.info(f"[RAVE] {version} training stopped")
    return jsonify(result)


@rave_bp.route('/api/rave/export', methods=['POST'])
def rave_export():
    """Export trained model."""
    version = _get_run_version()
    result = _run_rave_command("export", version, timeout=120)
    if result["success"]:
        logger.info(f"[RAVE] {version} model exported")
    return jsonify(result)


@rave_bp.route('/api/rave/test', methods=['POST'])
def rave_test():
    """Export latest checkpoint, then generate test reconstructions."""
    version = _get_run_version()
    result = _run_rave_command("test", version, timeout=300)
    if result["success"]:
        test_files = sorted([f.name for f in TEST_OUTPUT.glob("*.wav")]) if TEST_OUTPUT.exists() else []
        result["test_files"] = test_files
    return jsonify(result)


@rave_bp.route('/api/rave/eval', methods=['POST'])
def rave_eval():
    """Run auto-evaluation (export + reconstruct + SNR measurement)."""
    version = _get_run_version()
    result = _run_rave_command("eval", version, timeout=600)
    return jsonify(result)


@rave_bp.route('/api/rave/eval-log', methods=['GET'])
def rave_eval_log():
    """Get evaluation log entries."""
    version = _get_run_version()
    if not EVAL_LOG.exists():
        return jsonify({"entries": []})

    import csv
    entries = []
    with open(EVAL_LOG, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("run", "").startswith(RUN_CONFIGS.get(version, {}).get("name", "")):
                entries.append(row)

    return jsonify({"entries": entries[-100:]})  # Last 100 entries


@rave_bp.route('/api/rave/test-audio/<filename>', methods=['GET'])
def rave_test_audio(filename):
    """Serve a test reconstruction WAV file."""
    filepath = TEST_OUTPUT / filename
    if not filepath.exists() or not filepath.suffix == '.wav':
        return jsonify({"error": "File not found"}), 404
    return send_file(str(filepath), mimetype='audio/wav')


@rave_bp.route('/api/rave/original-audio/<filename>', methods=['GET'])
def rave_original_audio(filename):
    """Serve an original dataset WAV file for A/B comparison."""
    filepath = RAVE_DIR / "dataset" / "audio" / filename
    if not filepath.exists() or not filepath.suffix == '.wav':
        return jsonify({"error": "File not found"}), 404
    return send_file(str(filepath), mimetype='audio/wav')


@rave_bp.route('/api/rave/schedule', methods=['GET'])
def rave_schedule_get():
    """Get current schedule config."""
    schedule = _load_schedule()
    schedule["should_train"] = _should_train_now(schedule)
    return jsonify(schedule)


@rave_bp.route('/api/rave/schedule', methods=['POST'])
def rave_schedule_set():
    """Update schedule config."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400
    schedule = _load_schedule()
    for key in ["enabled", "slots", "manual_override", "run_version"]:
        if key in data:
            schedule[key] = data[key]
    _save_schedule(schedule)
    logger.info(f"[RAVE] Schedule updated: enabled={schedule['enabled']}, run={schedule.get('run_version', 'v2')}")
    return jsonify({"success": True, "schedule": schedule})


@rave_bp.route('/api/rave/schedule/tick', methods=['POST'])
def rave_schedule_tick():
    """Enforce schedule — called periodically by frontend."""
    schedule = _load_schedule()

    if not schedule.get("enabled") or schedule.get("manual_override"):
        return jsonify({"action": "none", "reason": "disabled" if not schedule.get("enabled") else "manual_override"})

    version = schedule.get("run_version", "v2")
    should = _should_train_now(schedule)
    running, pid = _is_training_running(version)

    if should and not running:
        run_dir = _find_run_dir(version)
        checkpoint = _find_latest_checkpoint(run_dir)
        if checkpoint:
            log_file = _log_file(version)
            try:
                proc = subprocess.Popen(
                    [str(RAVE_SH), "resume"],
                    cwd=str(RAVE_DIR),
                    stdout=open(str(log_file), 'a'),
                    stderr=subprocess.STDOUT,
                    env=_rave_env(version),
                )
                logger.info(f"[RAVE-SCHEDULE] Auto-resumed {version} training (PID {proc.pid})")
                return jsonify({"action": "resumed", "pid": proc.pid})
            except Exception as e:
                logger.error(f"[RAVE-SCHEDULE] Auto-resume failed: {e}")
                return jsonify({"action": "error", "error": str(e)})

    elif not should and running:
        _run_rave_command("stop", version, timeout=60)
        logger.info(f"[RAVE-SCHEDULE] Auto-stopped {version} training")
        return jsonify({"action": "stopped"})

    return jsonify({"action": "none", "running": running, "should": should})


# --- Pipeline (Normalize / Preprocess) ---

def _pipeline_is_running():
    """Check if a pipeline step is running."""
    if PIPELINE_PID_FILE.exists():
        try:
            pid = int(PIPELINE_PID_FILE.read_text().strip())
            os.kill(pid, 0)
            return True, pid
        except (ProcessLookupError, ValueError):
            PIPELINE_PID_FILE.unlink(missing_ok=True)
    return False, None


def _pipeline_state():
    """Read pipeline state file."""
    if PIPELINE_STATE_FILE.exists():
        try:
            return json.loads(PIPELINE_STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _set_pipeline_state(step, status, **extra):
    """Write pipeline state."""
    state = _pipeline_state()
    state[step] = {"status": status, "timestamp": datetime.now().isoformat(), **extra}
    PIPELINE_STATE_FILE.write_text(json.dumps(state, indent=2))


def _count_wavs(directory):
    """Count WAV files in a directory."""
    if not directory.exists():
        return 0
    return sum(1 for _ in directory.glob("*.wav"))


def _run_pipeline_step(cmd, step_name):
    """Run a pipeline command in background thread, tracking PID and log."""
    running, _ = _pipeline_is_running()
    if running:
        return jsonify({"success": False, "error": "Pipeline step already running"}), 409

    _set_pipeline_state(step_name, "running")

    def _run():
        try:
            log_fh = open(str(PIPELINE_LOG_FILE), 'w')
            proc = subprocess.Popen(
                cmd,
                cwd=str(RAVE_DIR),
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
            PIPELINE_PID_FILE.write_text(str(proc.pid))
            proc.wait()
            log_fh.close()
            PIPELINE_PID_FILE.unlink(missing_ok=True)
            if proc.returncode == 0:
                _set_pipeline_state(step_name, "done")
                logger.info(f"[RAVE-PIPELINE] {step_name} completed")
            else:
                _set_pipeline_state(step_name, "error", returncode=proc.returncode)
                logger.error(f"[RAVE-PIPELINE] {step_name} failed (rc={proc.returncode})")
        except Exception as e:
            PIPELINE_PID_FILE.unlink(missing_ok=True)
            _set_pipeline_state(step_name, "error", error=str(e))
            logger.error(f"[RAVE-PIPELINE] {step_name} error: {e}")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return jsonify({"success": True, "step": step_name})


@rave_bp.route('/api/rave/pipeline/status', methods=['GET'])
def rave_pipeline_status():
    """Get pipeline step statuses based on filesystem + state file."""
    running, pid = _pipeline_is_running()
    state = _pipeline_state()

    audio_count = _count_wavs(AUDIO_DIR)
    normalized_count = _count_wavs(AUDIO_NORMALIZED_DIR)
    preprocessed_exists = PREPROCESSED_V2_DIR.exists() and any(PREPROCESSED_V2_DIR.iterdir()) if PREPROCESSED_V2_DIR.exists() else False

    # Determine step statuses
    normalize_status = "pending"
    if state.get("normalize", {}).get("status") == "running" and running:
        normalize_status = "running"
    elif normalized_count > 0 and normalized_count >= audio_count * 0.95:
        normalize_status = "done"
    elif state.get("normalize", {}).get("status") == "error":
        normalize_status = "error"
    elif normalized_count > 0:
        normalize_status = "partial"

    preprocess_status = "pending"
    if state.get("preprocess", {}).get("status") == "running" and running:
        preprocess_status = "running"
    elif preprocessed_exists:
        preprocess_status = "done"
    elif state.get("preprocess", {}).get("status") == "error":
        preprocess_status = "error"

    return jsonify({
        "running": running,
        "pid": pid,
        "steps": {
            "normalize": {
                "status": normalize_status,
                "audio_count": audio_count,
                "normalized_count": normalized_count,
            },
            "preprocess": {
                "status": preprocess_status,
                "ready": normalize_status in ("done", "partial"),
            },
        },
    })


@rave_bp.route('/api/rave/pipeline/normalize', methods=['POST'])
def rave_pipeline_normalize():
    """Start dataset normalization."""
    return _run_pipeline_step(
        [str(PYTHON), str(RAVE_DIR / "scripts" / "normalize_dataset.py")],
        "normalize",
    )


@rave_bp.route('/api/rave/pipeline/preprocess', methods=['POST'])
def rave_pipeline_preprocess():
    """Start RAVE preprocessing on normalized dataset."""
    if not AUDIO_NORMALIZED_DIR.exists() or _count_wavs(AUDIO_NORMALIZED_DIR) == 0:
        return jsonify({"success": False, "error": "Normalize dataset first"}), 400

    return _run_pipeline_step(
        [str(RAVE_BIN), "preprocess",
         "--input_path", str(AUDIO_NORMALIZED_DIR),
         "--output_path", str(PREPROCESSED_V2_DIR)],
        "preprocess",
    )


@rave_bp.route('/api/rave/pipeline/log', methods=['GET'])
def rave_pipeline_log():
    """Get pipeline log tail."""
    if not PIPELINE_LOG_FILE.exists():
        return jsonify({"lines": []})
    lines = PIPELINE_LOG_FILE.read_text().strip().split('\n')
    return jsonify({"lines": lines[-20:]})


@rave_bp.route('/api/rave/metrics', methods=['GET'])
def rave_metrics():
    """Get training metrics from TensorBoard event logs."""
    version = _get_run_version()
    run_dir = _find_run_dir(version)
    if not run_dir:
        return jsonify({"error": "No run found"}), 404

    version_dirs = sorted(run_dir.glob("version_*"), key=lambda p: p.stat().st_mtime)
    if not version_dirs:
        return jsonify({"error": "No training versions found"}), 404

    try:
        from tbparse import SummaryReader
        reader = SummaryReader(str(version_dirs[-1]))
        df = reader.scalars

        if df.empty:
            return jsonify({"metrics": {}})

        key_tags = [
            'fullband_spectral_distance',
            'multiband_spectral_distance',
            'adversarial',
            'loss_dis',
            'feature_matching',
            'validation',
        ]

        metrics = {}
        for tag in key_tags:
            sub = df[df['tag'] == tag]
            if sub.empty:
                continue
            n = max(1, len(sub) // 200)
            sampled = sub.iloc[::n]
            metrics[tag] = {
                "steps": sampled['step'].tolist(),
                "values": [round(v, 5) for v in sampled['value'].tolist()],
            }

        return jsonify({"metrics": metrics})

    except ImportError:
        return jsonify({"error": "tbparse not installed"}), 500
    except Exception as e:
        logger.error(f"[RAVE] Metrics error: {e}")
        return jsonify({"error": str(e)}), 500
