"""The installers and the deploy script describe the installation that exists.

Read as text, because the scripts talk to systemd, pip and the network; what
is checked is what they would do.

- S-022  install_comfyui_nodes.sh installs into ComfyUI's venv or not at all;
  the fallback into the DevServer's venv installed transformers 5 into an
  environment pinned to 4.57 and broke it.
- S-047  5_pullanddeploy.sh restarts ComfyUI with the two services and waits
  for it: the platform's nodes are read at ComfyUI's start.
- S-048  setup.sh and update.sh install in the order requirements.txt names
  and carry no SwarmUI; the venv is python3.13.
- S-058  the pilot scripts take address and key from the provider table.
"""
import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _text(rel):
    return (REPO / rel).read_text(encoding="utf-8")


def test_the_node_installer_never_falls_back_to_the_devserver_venv(tmp_path):
    text = _text("install_comfyui_nodes.sh")
    assert "$SCRIPT_DIR/venv" not in text
    assert "using system Python" not in text
    # Run it against a ComfyUI that has no venv: it stops before anything is
    # installed, and says what is missing.
    comfy = tmp_path / "ComfyUI"
    (comfy / "custom_nodes").mkdir(parents=True)
    result = subprocess.run(["bash", str(REPO / "install_comfyui_nodes.sh")],
                            env=dict(os.environ, COMFYUI_PATH=str(comfy)),
                            capture_output=True, text=True, cwd=tmp_path)
    assert result.returncode == 1
    assert "no venv at" in result.stdout + result.stderr


def test_the_deploy_restarts_and_checks_comfyui():
    """The ComfyUI unit is restarted where one exists (the lab supervision
    writes one; install_systemd_services.sh does not, and there the backend
    starts ComfyUI itself): unconditional, the restart failed the deploy
    under its ERR trap (second review of 2026-10-10)."""
    text = _text("5_pullanddeploy.sh")
    assert "systemctl restart ai4artsed-gpu ai4artsed-backend\n" in text
    assert "systemctl list-unit-files ai4artsed-comfyui.service" in text
    assert "sudo systemctl restart ai4artsed-comfyui\n" in text
    assert "127.0.0.1:17804/system_stats" in text
    assert "-u ai4artsed-comfyui" in text


def test_the_setup_scripts_install_in_the_order_requirements_names():
    for rel in ("setup.sh", "update.sh"):
        text = _text(rel)
        assert "SwarmUI" not in text and "SWARMUI" not in text, rel
        assert "api_keys.json" not in text, rel
        torch = text.index("deployment/requirements-torch.txt")
        base = text.index("-r requirements.txt")
        git = text.index("deployment/requirements-git.txt")
        spacy = text.index("deployment/requirements-spacy.txt")
        assert torch < base < git < spacy, rel
    assert "python3.13 -m venv" in _text("setup.sh")
    assert not (REPO / "setup_venv.sh").exists()
    assert not (REPO / "docs/installation/comfyui_custom_nodes_requirements.txt").exists()


def test_the_pilot_scripts_take_their_credentials_from_the_table():
    for rel in ("devserver/scripts/h7_pilot_runner.py",
                "devserver/scripts/substance_pilot_runner.py",
                "devserver/scripts/abc_form_comparison.py"):
        text = _text(rel)
        assert "mammouth.key" not in text, rel
        assert "api.mammouth.ai" not in text, rel
        assert 'credentials("mammouth")' in text, rel
    assert "openrouter/" not in _text("devserver/scripts/h7_pilot_runner.py")
