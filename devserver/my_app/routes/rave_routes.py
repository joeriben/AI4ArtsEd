"""
RAVE Training Controller Routes

Manages RAVE model training via subprocess calls to rave.sh.
"""

import logging
import os
import subprocess
import json
import re
from datetime import datetime
from pathlib import Path
from flask import Blueprint, jsonify, request, send_file

logger = logging.getLogger(__name__)

rave_bp = Blueprint('rave', __name__)

RAVE_DIR = Path.home() / "ai" / "rave_research"
RAVE_SH = RAVE_DIR / "rave.sh"
PID_FILE = RAVE_DIR / ".rave_training.pid"
LOG_FILE = RAVE_DIR / "training.log"
TEST_OUTPUT = RAVE_DIR / "test_output"
RUNS_DIR = RAVE_DIR / "runs"
SCHEDULE_FILE = RAVE_DIR / ".rave_schedule.json"

DEFAULT_SLOT = {
    "start": "00:00", "stop": "00:00",
    "days": {"mon": False, "tue": False, "wed": False, "thu": False, "fri": False, "sat": False, "sun": False},
}

DEFAULT_SCHEDULE = {
    "enabled": False,
    "manual_override": False,
    "slots": [
        {"start": "22:00", "stop": "07:00", "days": {"mon": True, "tue": True, "wed": True, "thu": True, "fri": True, "sat": True, "sun": True}},
        DEFAULT_SLOT.copy(),
        DEFAULT_SLOT.copy(),
    ],
}


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
        return False  # Slot not configured

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


def _is_training_running():
    """Check if training process is alive."""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            return True, pid
        except (ProcessLookupError, ValueError):
            return False, None
    return False, None


def _find_run_dir():
    """Find the training run directory."""
    if not RUNS_DIR.exists():
        return None
    for d in RUNS_DIR.iterdir():
        if d.is_dir() and d.name.startswith("mini70_v1_"):
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


def _parse_log_tail(n=10):
    """Read last N lines of training log and extract epoch/step info."""
    if not LOG_FILE.exists():
        return [], None, None

    lines = LOG_FILE.read_text().strip().split('\n')
    tail = lines[-n:] if len(lines) >= n else lines

    # Parse epoch and step from progress bar lines like "Epoch 180: 100%|..."
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


def _run_rave_command(command, timeout=300):
    """Run a rave.sh subcommand and return output."""
    try:
        result = subprocess.run(
            [str(RAVE_SH), command],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(RAVE_DIR),
            env={**os.environ, "TORCH_FLOAT32_MATMUL_PRECISION": "high"}
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
    running, pid = _is_training_running()
    run_dir = _find_run_dir()
    checkpoint = _find_latest_checkpoint(run_dir)
    exported_model = _find_exported_model(run_dir) if run_dir else None
    log_tail, epoch, step = _parse_log_tail(15)

    # List test output files
    test_files = []
    if TEST_OUTPUT.exists():
        test_files = sorted([f.name for f in TEST_OUTPUT.glob("*.wav")])

    total_steps = (epoch * 6250 + (step or 0)) if epoch is not None else None

    return jsonify({
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
    })


@rave_bp.route('/api/rave/start', methods=['POST'])
def rave_start():
    """Start fresh training."""
    running, _ = _is_training_running()
    if running:
        return jsonify({"success": False, "error": "Training already running"}), 409

    try:
        proc = subprocess.Popen(
            [str(RAVE_SH), "start"],
            cwd=str(RAVE_DIR),
            stdout=open(str(LOG_FILE), 'w'),
            stderr=subprocess.STDOUT,
            env={**os.environ, "TORCH_FLOAT32_MATMUL_PRECISION": "high"},
        )
        # rave.sh writes its own PID file — don't write it here
        logger.info(f"[RAVE] Training started (PID {proc.pid})")
        return jsonify({"success": True, "pid": proc.pid})
    except Exception as e:
        logger.error(f"[RAVE] Start failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@rave_bp.route('/api/rave/resume', methods=['POST'])
def rave_resume():
    """Resume training from latest checkpoint."""
    running, _ = _is_training_running()
    if running:
        return jsonify({"success": False, "error": "Training already running"}), 409

    run_dir = _find_run_dir()
    checkpoint = _find_latest_checkpoint(run_dir)
    if not checkpoint:
        return jsonify({"success": False, "error": "No checkpoint found"}), 404

    try:
        proc = subprocess.Popen(
            [str(RAVE_SH), "resume"],
            cwd=str(RAVE_DIR),
            stdout=open(str(LOG_FILE), 'a'),
            stderr=subprocess.STDOUT,
            env={**os.environ, "TORCH_FLOAT32_MATMUL_PRECISION": "high"},
        )
        # rave.sh writes its own PID file — don't write it here
        logger.info(f"[RAVE] Training resumed from {checkpoint} (PID {proc.pid})")
        return jsonify({"success": True, "pid": proc.pid, "checkpoint": checkpoint})
    except Exception as e:
        logger.error(f"[RAVE] Resume failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@rave_bp.route('/api/rave/stop', methods=['POST'])
def rave_stop():
    """Stop running training."""
    running, pid = _is_training_running()
    if not running:
        return jsonify({"success": True, "message": "Not running"})

    result = _run_rave_command("stop", timeout=60)
    logger.info(f"[RAVE] Training stopped")
    return jsonify(result)


@rave_bp.route('/api/rave/export', methods=['POST'])
def rave_export():
    """Export trained model."""
    result = _run_rave_command("export", timeout=120)
    if result["success"]:
        logger.info("[RAVE] Model exported")
    return jsonify(result)


@rave_bp.route('/api/rave/test', methods=['POST'])
def rave_test():
    """Generate test reconstructions."""
    result = _run_rave_command("test", timeout=120)
    if result["success"]:
        test_files = sorted([f.name for f in TEST_OUTPUT.glob("*.wav")]) if TEST_OUTPUT.exists() else []
        result["test_files"] = test_files
    return jsonify(result)


@rave_bp.route('/api/rave/test-audio/<filename>', methods=['GET'])
def rave_test_audio(filename):
    """Serve a test reconstruction WAV file."""
    filepath = TEST_OUTPUT / filename
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
    for key in ["enabled", "slots", "manual_override"]:
        if key in data:
            schedule[key] = data[key]
    _save_schedule(schedule)
    logger.info(f"[RAVE] Schedule updated: enabled={schedule['enabled']}, {schedule['start_time']}-{schedule['stop_time']}")
    return jsonify({"success": True, "schedule": schedule})


@rave_bp.route('/api/rave/schedule/tick', methods=['POST'])
def rave_schedule_tick():
    """Enforce schedule — called periodically by frontend."""
    schedule = _load_schedule()

    if not schedule.get("enabled") or schedule.get("manual_override"):
        return jsonify({"action": "none", "reason": "disabled" if not schedule.get("enabled") else "manual_override"})

    should = _should_train_now(schedule)
    running, pid = _is_training_running()

    if should and not running:
        # Should be training but isn't — resume
        run_dir = _find_run_dir()
        checkpoint = _find_latest_checkpoint(run_dir)
        if checkpoint:
            try:
                proc = subprocess.Popen(
                    [str(RAVE_SH), "resume"],
                    cwd=str(RAVE_DIR),
                    stdout=open(str(LOG_FILE), 'a'),
                    stderr=subprocess.STDOUT,
                    env={**os.environ, "TORCH_FLOAT32_MATMUL_PRECISION": "high"},
                )
                logger.info(f"[RAVE-SCHEDULE] Auto-resumed training (PID {proc.pid})")
                return jsonify({"action": "resumed", "pid": proc.pid})
            except Exception as e:
                logger.error(f"[RAVE-SCHEDULE] Auto-resume failed: {e}")
                return jsonify({"action": "error", "error": str(e)})

    elif not should and running:
        # Shouldn't be training but is — stop
        _run_rave_command("stop", timeout=60)
        logger.info("[RAVE-SCHEDULE] Auto-stopped training")
        return jsonify({"action": "stopped"})

    return jsonify({"action": "none", "running": running, "should": should})


@rave_bp.route('/api/rave/metrics', methods=['GET'])
def rave_metrics():
    """Get training metrics from TensorBoard event logs."""
    run_dir = _find_run_dir()
    if not run_dir:
        return jsonify({"error": "No run found"}), 404

    # Find latest version directory with events
    version_dirs = sorted(run_dir.glob("version_*"), key=lambda p: p.stat().st_mtime)
    if not version_dirs:
        return jsonify({"error": "No training versions found"}), 404

    try:
        from tbparse import SummaryReader
        reader = SummaryReader(str(version_dirs[-1]))
        df = reader.scalars

        if df.empty:
            return jsonify({"metrics": {}})

        # Key metrics to display — downsample to max 200 points per metric
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
            # Downsample: take every Nth point to keep ~200 points
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
