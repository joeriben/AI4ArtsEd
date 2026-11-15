#!/usr/bin/env python3
"""Write the AI-Origin Disclosure (EU AI Act Art. 50) into stored media made before it reached them.

Every medium the platform generates has carried the disclosure since
2026-08-15 (da596fbe). What the storage holds from before that date carries
none of it: on the development machine this script marked 6,979 outputs from
11/2025 to 2026-08 on 2026-11-15. The project lead, 2026-11-14, on how to
bring them in line: "es ist einfacher die metadaten in den altdateiein zu
korrigieren".

Per file:
  * only a medium the platform generated is touched
    (watermark_service.is_generated_medium): never what a person brought in,
    never prompts, records or latents: not a file that is a copy of what a
    person brought into its run, and not a prompt of its run stored under a
    sketch's name (in March 2026 runs that wrote no code stored it so). A
    sketch that is generated code is marked although the run kept the same
    code as its generation prompt;
  * whose bytes do not carry the disclosure (watermark_service.carries_disclosure)
    is marked by the same function as on the way to the disk
    (watermark_media_bytes), with the record's own metadata and the time the run
    recorded for it as `generated_at`, in local time with its offset, so the
    marking names the day the medium was made and not the day it was marked;
  * the marked bytes replace the file in place (temporary file, then rename);
    its name and its record stay as they were. PNG and JPEG are not
    re-encoded: the chunks go in beside the ones that are there;
  * a file the disclosure has no place in (an animated picture, a picture
    format without a slot, MIDI) keeps its bytes and gets `_ai_generated`
    before its extension, as a new file would (services/media_marking); its
    record is rewritten to name it so;
  * a file whose marking failed for any other reason (bytes that do not
    decode, an ffmpeg error) is left as it is and listed: a second run marks it.

Besides the files the records name, a run's folder holds outputs no record
names (canvas runs whose record lists only their input, early runs, a song
filed under its title). A medium in a run's folder that no record names is
an output of that run and is treated the same way, unless its name marks it as
brought in by a person (watermark_service._is_user_material) or its bytes are
a copy of what a person brought in; those whose name does not say `output`
are listed. Outside a run's folder only a name that says it is an output
(`output` or the early `-audiovisual-audio`) counts, its type read off its
name; every other medium there is listed and left alone.

The script refuses to run while a visible or invisible layer is switched on
(marking would change pixels), and while a metadata switch is off or ffmpeg
is missing (every file of that kind would come back unmarked). Runs written to
within the last hour are left alone: their writer may still be at work.

Every file that is replaced, and every record that is rewritten, is copied
first into a directory OUTSIDE the repository, under its path in the storage;
a renamed file keeps its bytes, so its record is what is copied. The
directory has to be new. Dry run by default; `--apply` writes.

The DevServer keeps the records it has read in memory: restart it after
`--apply`, or a renamed file is looked for under its old name.

USAGE:
    python3 devserver/scripts/mark_stored_media.py            # count, no writes
    python3 devserver/scripts/mark_stored_media.py --apply    # mark
"""
import argparse
import collections
import io
import json
import os
import re
import shutil
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from my_app.services.watermark_service import (  # noqa: E402
    UNMARKED_SUFFIX,
    _is_user_material,
    carries_disclosure,
    is_generated_medium,
    plain_filename,
    unmarked_filename,
    watermark_media_bytes,
)

REPO = Path(__file__).resolve().parents[2]
SETTLE_SECONDS = 3600
METADATA_SWITCHES = (
    "metadata_image", "metadata_video", "metadata_audio",
    "metadata_3d", "metadata_svg", "metadata_code",
)
MEDIA_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp3", ".wav", ".flac", ".ogg",
    ".m4a", ".mp4", ".webm", ".mov", ".mkv", ".glb", ".svg", ".mid", ".midi",
}
#: An output's name: `NN_output_<type>.<ext>`, with or without `_ai_generated`.
#: The earliest runs wrote `output_<type>.<ext>`, and a converted film still
#: kept the extension it had before (`06_output_video.png.webp`).
OUTPUT_NAME = re.compile(
    r"^(?:\d+_)?(output_[a-z0-9_]+?)(?:" + re.escape(UNMARKED_SUFFIX) + r")?(?:\.[A-Za-z0-9]+)+$"
)
#: What tells code from a prompt that was stored under a sketch's name.
CODE_SIGNS = (b"function", b"=>", b"setup(", b"new Tone.", b"let ", b"const ", b"var ", b"live_loop", b"{")
#: What the early audiovisual pipeline called the sound it made.
EARLY_AUDIO_NAME = re.compile(r"-audiovisual-audio\.[A-Za-z0-9]+$")


def _refusal(settings: dict) -> str:
    if settings.get("visible_image") or settings.get("visible_video") or settings.get("invisible_image"):
        return "A visible or invisible layer is switched on; marking would change pixels."
    off = [key for key in METADATA_SWITCHES if not settings.get(key, True)]
    if off:
        return f"Switched off in the settings: {', '.join(off)}; those files would come back unmarked."
    if shutil.which("ffmpeg") is None:
        return "ffmpeg is not on the PATH; sound and film would come back unmarked."
    return ""


def _inside(path: Path, folder: Path) -> bool:
    try:
        return path.resolve().is_relative_to(folder.resolve())
    except OSError:
        return False


def _stored_path(run_folder: Path, filename: str):
    """Where a record's file lies, and the name it lies under.

    Also under the other spelling: a run interrupted between renaming a file
    and rewriting its record names the file without `_ai_generated` while the
    disk holds it with, and the next run puts the record right.
    """
    for name in dict.fromkeys((filename, unmarked_filename(filename), plain_filename(filename))):
        for candidate in (run_folder / "final" / name, run_folder / name):
            if _inside(candidate, run_folder) and candidate.is_file():
                return candidate, name
    return None, filename


def _local_time(stamp: str) -> str:
    """The recorders write the server's local time without its zone."""
    try:
        moment = datetime.fromisoformat(stamp)
    except ValueError:
        return ""
    if moment.tzinfo is None:
        moment = moment.astimezone()
    return moment.isoformat()


def _has_no_slot(raw: bytes, entity_type: str) -> bool:
    """Whether the disclosure has no place in this file at all, as against a
    marking that failed (watermark_service: animated pictures and picture
    formats without a slot are handed back untouched; nothing writes into MIDI)."""
    if "midi" in (entity_type or "").lower():
        return True
    try:
        from PIL import Image

        with Image.open(io.BytesIO(raw)) as img:
            frames = int(getattr(img, "n_frames", 1) or 1)
            return frames > 1 or (img.format or "").upper() not in ("PNG", "JPEG", "WEBP")
    except Exception:
        return False


def _backup(path: Path, root: Path, backup_dir: Path) -> None:
    target = backup_dir / path.relative_to(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)


def _replace(path: Path, data: bytes) -> None:
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


class Run:
    """One pass over the storage."""

    def __init__(self, root: Path, backup_dir: Path, apply: bool):
        self.root = root
        self.backup_dir = backup_dir
        self.apply = apply
        self.now = time.time()
        self.seen = set()
        self.counts = collections.Counter()
        self.by_month = collections.Counter()
        self.renamed = []
        self.failed = []
        self.unnamed = []
        self.taken_as_output = []
        self.copies = []
        self.bytes_backed_up = 0

    def backup(self, path: Path) -> None:
        _backup(path, self.root, self.backup_dir)
        self.bytes_backed_up += path.stat().st_size

    def mark(self, path: Path, entity_type: str, meta: dict, month: str, copy_of=None):
        """Mark one file in place. Returns the name it has to carry instead, or None."""
        try:
            raw = path.read_bytes()
        except OSError:
            self.counts["files unreadable"] += 1
            return None
        if not is_generated_medium(raw, entity_type):
            return None
        if copy_of is not None and copy_of(path, raw):
            self.counts["copy of another file of its run, left alone"] += 1
            self.copies.append(str(path.relative_to(self.root)))
            return None
        self.counts["generated media"] += 1
        if carries_disclosure(raw):
            self.counts["already marked"] += 1
            return None

        marked = watermark_media_bytes(raw, entity_type, meta)
        if carries_disclosure(marked):
            self.counts["marked now"] += 1
            self.by_month[month] += 1
            if self.apply:
                self.backup(path)
                _replace(path, marked)
            return None
        if not _has_no_slot(raw, entity_type):
            self.counts["marking failed, left for a second run"] += 1
            self.failed.append(str(path.relative_to(self.root)))
            return None
        named = unmarked_filename(path.name)
        if named == path.name:
            self.counts["no place for it, already named so"] += 1
            return None
        return named

    def run_folder(self, record_path: Path) -> None:
        run_folder = record_path.parent
        try:
            stat = record_path.stat()
            if self.now - stat.st_mtime < SETTLE_SECONDS:
                self.counts["runs still recent, left alone"] += 1
                return
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.counts["records unreadable"] += 1
            return
        entities = record.get("entities") if isinstance(record, dict) else None
        if not isinstance(entities, list):
            entities = []

        def copy_of(path: Path, raw: bytes) -> bool:
            """Whether these bytes are a copy of what a person brought into the
            run, or a prompt of the run that is no code: another file the record
            names holds them, the same file, or for text the same text up to the
            white space round it."""
            code = any(sign in raw for sign in CODE_SIGNS)
            text = b"\x00" not in raw[:4096]
            for other in entities:
                if not isinstance(other, dict):
                    continue
                other_path, _ = _stored_path(run_folder, str(other.get("filename") or ""))
                if other_path is None or other_path == path:
                    continue
                try:
                    size = other_path.stat().st_size
                    if size == len(raw):
                        data = other_path.read_bytes()
                        same = data == raw
                    elif text and size < 1_000_000 and raw.strip():
                        data = other_path.read_bytes()
                        same = data.strip() == raw.strip()
                    else:
                        continue
                except OSError:
                    continue
                other_type = str(other.get("type") or other.get("node_type") or "")
                if not same or is_generated_medium(data, other_type):
                    continue
                if _is_user_material(other_type) or not code:
                    return True
            return False

        changes = []   # (entity, old path, new name) for the record, written once below
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            filename = str(entity.get("filename") or "")
            entity_type = str(entity.get("type") or entity.get("node_type") or "")
            path, found_as = _stored_path(run_folder, filename) if filename else (None, filename)
            if path is None or path in self.seen:
                continue
            self.seen.add(path)
            if found_as != filename:
                changes.append((entity, None, found_as))
                self.counts["record put right to the name on disk"] += 1

            meta = dict(entity.get("metadata") or {})
            stamp = str(entity.get("timestamp") or "")
            if stamp and _local_time(stamp):
                meta["generated_at"] = _local_time(stamp)
            new_name = self.mark(path, entity_type, meta, stamp[:7] or "unknown", copy_of)
            if new_name is not None:
                changes.append((entity, path, str(Path(found_as).with_name(new_name))))

        if changes:
            self.rewrite(record_path, stat, record, changes)

        # Outputs in this run's folder that no record names.
        for folder in (run_folder / "final", run_folder):
            if not folder.is_dir():
                continue
            for path in sorted(folder.iterdir()):
                if path.is_file() and path not in self.seen:
                    self.loose(path, copy_of)

    def rewrite(self, record_path: Path, stat, record: dict, changes) -> None:
        renames = [(path, path.with_name(Path(name).name)) for _, path, name in changes if path]
        for _, target in renames:
            if target.exists():
                self.counts["rename target exists, run left alone"] += 1
                return
        for path, target in renames:
            self.counts["no place for it, renamed"] += 1
            self.renamed.append(f"{path.relative_to(self.root)} -> {target.name}")
        if not self.apply:
            return
        try:
            unchanged = record_path.stat().st_mtime_ns == stat.st_mtime_ns
        except OSError:
            unchanged = False
        if not unchanged:
            # The server wrote into this run meanwhile; its record is not ours to overwrite.
            self.counts["record changed while working, left for a second run"] += 1
            return
        self.backup(record_path)
        for path, target in renames:
            os.rename(path, target)
        for entity, _, name in changes:
            entity["filename"] = name
        _replace(record_path, json.dumps(record, indent=2, ensure_ascii=False).encode("utf-8"))

    def loose(self, path: Path, copy_of=None) -> None:
        """A file no record names. `copy_of` is the copy test of the run in
        whose folder it lies, None outside a run's folder."""
        if path.suffix.lower() not in MEDIA_EXTENSIONS:
            return
        self.seen.add(path)
        named = OUTPUT_NAME.match(path.name)
        if named:
            entity_type = named.group(1)
        elif EARLY_AUDIO_NAME.search(path.name):
            entity_type = "output_audio"
        elif copy_of is not None and not _is_user_material(
            re.sub(r"^\d+_", "", path.name.split(".")[0])
        ):
            # What a person brings into a run is stored under a name that says
            # so; whatever else lies in the run's folder the platform made.
            entity_type = "output_media"
            self.taken_as_output.append(str(path.relative_to(self.root)))
        else:
            self.unnamed.append(str(path.relative_to(self.root)))
            return
        made = datetime.fromtimestamp(path.stat().st_mtime).astimezone()
        if self.now - made.timestamp() < SETTLE_SECONDS:
            return
        new_name = self.mark(path, entity_type, {"generated_at": made.isoformat()},
                             made.strftime("%Y-%m"), copy_of)
        if new_name is None:
            return
        target = path.with_name(new_name)
        if target.exists():
            self.counts["rename target exists, run left alone"] += 1
            return
        self.counts["no place for it, renamed"] += 1
        self.renamed.append(f"{path.relative_to(self.root)} -> {new_name}")
        if self.apply:
            os.rename(path, target)

    def folders_without_record(self, run_folders: set) -> None:
        """Outputs in folders that belong to no run (the early audiovisual folder)."""
        for folder, dirs, files in os.walk(self.root):
            folder = Path(folder)
            # A run's own folders were gone through with its record, or left
            # alone with it while it is still being written.
            dirs[:] = [d for d in dirs if folder / d not in run_folders]
            if folder in run_folders:
                continue
            for name in sorted(files):
                path = folder / name
                if path not in self.seen:
                    self.loose(path, None)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="write (default: count only)")
    parser.add_argument("--root", default=str(config.JSON_STORAGE_DIR))
    parser.add_argument("--backup-dir", default="",
                        help="where the originals go (default: beside the repository)")
    args = parser.parse_args(argv)

    refusal = _refusal(getattr(config, "WATERMARK", {}) or {})
    if refusal:
        print(f"{refusal} Refused.")
        return 2

    root = Path(args.root).resolve()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path(args.backup_dir) if args.backup_dir else (
        REPO.parent / f"stored_media_before_disclosure_{stamp}"
    )
    if backup_dir.resolve().is_relative_to(REPO) or backup_dir.resolve().is_relative_to(root):
        print(f"Backup directory {backup_dir} lies inside the repository or the storage. Refused.")
        return 2
    if backup_dir.exists() and any(backup_dir.iterdir()):
        print(f"Backup directory {backup_dir} is not empty. Refused.")
        return 2

    run = Run(root, backup_dir, args.apply)
    records = sorted(root.rglob("metadata.json"))
    for record_path in records:
        run.run_folder(record_path)
    run.folders_without_record({record_path.parent for record_path in records})

    print(f"storage: {root}")
    print(f"time zone of the recorded times: {time.strftime('%Z')}")
    for key, value in run.counts.items():
        print(f"  {key}: {value}")
    print("marked now, by month the run recorded:")
    for month in sorted(run.by_month):
        print(f"  {month}: {run.by_month[month]}")
    for line in run.renamed:
        print(f"  renamed: {line}")
    for line in run.failed:
        print(f"  marking failed: {line}")
    for line in run.copies:
        print(f"  copy of another file of its run, left alone: {line}")
    for line in run.taken_as_output:
        print(f"  no record names it, taken as an output of its run: {line}")
    for line in run.unnamed:
        print(f"  medium no record names, left alone: {line}")
    if args.apply:
        print(f"originals: {backup_dir} ({run.bytes_backed_up / 1e9:.2f} GB)")
    else:
        print("dry run: nothing written (--apply writes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
