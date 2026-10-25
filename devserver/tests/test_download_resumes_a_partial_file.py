"""The model download scripts resume a broken-off download and never take a
fragment for the model.

download_file in _lib.sh (sourced by download_models.sh, download_flux2.sh and
download_qwen.sh) skipped every file that existed, and the downloader wrote
straight to the final name: a run that broke off left a fragment under the
model's name, and the next run reported it as present. The three scripts
promised the opposite ("re-run this script to resume downloads"); the fragment
failed when ComfyUI loaded it (finding S-021 of the code review of 2026-10-10).

The downloader is a stand-in on PATH that appends two bytes to the file it is
told to write and exits as the test says. A fragment aria2c preallocated
(its control file ".part.aria2" beside it) is struck before wget runs, which
would otherwise take the full-length fragment for a whole file (second
review of 2026-10-10).
"""
import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "_lib.sh"

STUB = """#!/bin/bash
# A downloader that writes two bytes to <dir>/<name> and exits as told; its
# arguments go to STUB_RECORD when that is set.
printf '%s ' "$@" >> "${STUB_RECORD:-/dev/null}"
dir=.; name=out
while [ $# -gt 0 ]; do
  case "$1" in
    -d) dir="$2"; shift 2;;
    -o) name="$2"; shift 2;;
    -O) dir=$(dirname "$2"); name=$(basename "$2"); shift 2;;
    *) shift;;
  esac
done
printf 'ab' >> "$dir/$name"
exit "${STUB_EXIT:-0}"
"""


@pytest.fixture
def downloader(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("aria2c", "wget"):
        stub = bin_dir / name
        stub.write_text(STUB, encoding="utf-8")
        stub.chmod(0o755)
    return bin_dir


def _download(tmp_path, downloader, exit_code, record=None, tool="aria2c"):
    out = tmp_path / "models" / "a_model.safetensors"
    out.parent.mkdir(exist_ok=True)
    env = dict(os.environ, PATH=f"{downloader}:{os.environ['PATH']}", STUB_EXIT=str(exit_code))
    if record is not None:
        env["STUB_RECORD"] = str(record)   # the stub's arguments, for the resume flag
    script = (
        f"source {LIB}; DOWNLOADER={tool}; "
        f"download_file http://example.invalid/a_model.safetensors '{out}'"
    )
    result = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, cwd=tmp_path)
    return out, result


def test_a_broken_off_download_leaves_no_file_under_the_models_name(tmp_path, downloader):
    out, result = _download(tmp_path, downloader, exit_code=1)
    assert result.returncode != 0
    assert not out.exists(), "a fragment stands under the model's name"
    assert out.with_name(out.name + ".part").read_bytes() == b"ab"


def test_the_next_run_resumes_the_fragment_and_renames_it_whole(tmp_path, downloader):
    _download(tmp_path, downloader, exit_code=1)
    record = tmp_path / "args.txt"
    out, result = _download(tmp_path, downloader, exit_code=0, record=record)
    assert result.returncode == 0, result.stdout + result.stderr
    assert out.read_bytes() == b"abab"
    assert not out.with_name(out.name + ".part").exists()
    assert " -c " in " " + record.read_text(encoding="utf-8") + " ", "the downloader was not told to continue"
    assert "Resuming" in result.stdout


def test_a_whole_file_is_left_alone(tmp_path, downloader):
    out = tmp_path / "models" / "a_model.safetensors"
    out.parent.mkdir()
    out.write_bytes(b"whole")
    out2, result = _download(tmp_path, downloader, exit_code=0)
    assert result.returncode == 0
    assert out2.read_bytes() == b"whole"
    assert "Already exists" in result.stdout


def test_wget_strikes_the_fragment_aria2c_preallocated(tmp_path, downloader):
    out = tmp_path / "models" / "a_model.safetensors"
    out.parent.mkdir(exist_ok=True)
    part = out.with_name(out.name + ".part")
    part.write_bytes(b"\0" * 8)                       # aria2c's preallocated length
    part.with_name(part.name + ".aria2").write_bytes(b"") # its control file
    out, result = _download(tmp_path, downloader, exit_code=0, tool="wget")
    assert result.returncode == 0, result.stdout + result.stderr
    assert out.read_bytes() == b"ab", "the zeros aria2c preallocated were handed out as the model"
    assert not part.with_name(part.name + ".aria2").exists()
    assert "Discarding" in result.stdout


def test_wget_resumes_its_own_fragment(tmp_path, downloader):
    out = tmp_path / "models" / "a_model.safetensors"
    out.parent.mkdir(exist_ok=True)
    out.with_name(out.name + ".part").write_bytes(b"ab")
    out, result = _download(tmp_path, downloader, exit_code=0, tool="wget")
    assert result.returncode == 0, result.stdout + result.stderr
    assert out.read_bytes() == b"abab"
    assert "Resuming" in result.stdout
