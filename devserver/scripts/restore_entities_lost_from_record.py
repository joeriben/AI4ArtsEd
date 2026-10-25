#!/usr/bin/env python3
"""
Give a run back the outputs its own record forgot.

A run folder holds two things: the files under `final/`, and `metadata.json`
with the ordered `entities` list that says what those files ARE. Every reader of
the research data goes by the list, never by the folder - so a file the list
does not mention is, for the platform, not there: no picture in the table, no
address to serve it from, a favorite pointing into nothing.

On 2026-01-31 one run had its record re-initialised in the middle of a session:
the list was replaced by a fresh one starting at sequence 1, while 54 files from
the previous hour stayed on disk. Eleven outputs, one of them the only video of
that session, went silent. Of 6673 runs it is the only ordinary one in this
state; the canvas runs that also show it record through their own pipeline and
are out of scope here - the script refuses them by name.

WHAT THE RECONSTRUCTION IS ALLOWED TO USE

The folder says what each file is: filenames have the form NN_<type>.<ext>, and
across the corpus <type> is the entity's type. That rule alone is not enough -
this repository's own history contains files named `output_image` that hold an
MP3 - so for every output the first bytes have to agree with the name, and where
they disagree the run is refused rather than relabelled.

The file's mtime says when it arrived, and that order is the session's true
order even where the numbering restarted. Two checks stand in front of that: no
two files may share an mtime (then the folder cannot order them), and every
entity that SURVIVED must have its recorded timestamp within five seconds of its
file's mtime (then the folder's clocks still describe this run - a plate that
was set again later fails this and the run is refused).

Everything the lost entities carried besides this - the seed, the config, the
source path - is gone. The rebuilt entry says so with `recovered_from_file`, and
names `file_mtime` as the origin of its timestamp, rather than inventing them.

WHAT IT DOES NOT TOUCH

`expected_outputs` is a fixed six-slot schedule, read elsewhere as the
denominator of a run's progress, never an inventory - so it stays as written.
`current_state` is the snapshot of a live run and stays too. This script
restores what a run PRODUCED, not what it planned or how far it got.

AFTERWARDS

The backend keeps a loaded run in memory for the life of the process and writes
that copy back when the run is touched again, so a repaired record only reaches
readers - and only stops being at risk - after `systemctl restart
ai4artsed-backend`. The script says so at the end, and drops the run's cached
miniatures, which are keyed by run and index and would otherwise show one
picture under another's name for a year.

Dry run by default. `--apply` writes, after copying every record it touches to a
backup directory OUTSIDE any git working tree.

    python3 devserver/scripts/restore_entities_lost_from_record.py run_1769860554995_0a3098
    python3 devserver/scripts/restore_entities_lost_from_record.py run_… --apply
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO = Path(__file__).resolve().parents[2]
EXPORTS = REPO / "exports" / "json"
NAMED = re.compile(r"^(\d+)_(.+)\.([A-Za-z0-9]+)$")

#: Every entity type an ordinary run writes into `final/`. A stem outside this
#: set is not something this script knows how to name, and the run is refused.
#: `output_latent` is in it and is no medium: the two SD 3.5 rows keep the
#: picture's final latent next to it so a SET can be averaged before the decoder
#: (Mean Images). Without the entry a run that kept one would be refused whole,
#: and its picture would stay lost over a numpy file.
KNOWN_TYPES = {
    "input", "translation_en", "context_prompt", "interception",
    "generation_prompt", "output_image", "output_video", "output_audio",
    "output_music", "output_latent",
}

#: What kind of thing the NAME claims, against which the bytes are held.
NAME_KIND = {"image": "image", "video": "film", "audio": "sound", "music": "sound",
             "latent": "latent"}

#: The clocks of one session may drift this far from each other before the
#: folder stops being a witness to its own order.
CLOCK_TOLERANCE_S = 5.0


def sniff(path: Path):
    """What a file says it is, by its first bytes. Same reading as the sibling
    script that had to correct 48 records typed by their name alone."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(16)
    except OSError:
        return None
    if head[:8] == b"\x89PNG\r\n\x1a\n" or head[:3] == b"\xff\xd8\xff":
        return "image"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "image"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image"
    # An ISO base-media file opens with the length of its first box and then
    # the word: `ftyp` sits at 4, not at 8.
    if head[4:8] == b"ftyp":
        return "film"
    if head[:3] == b"ID3" or head[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"\xff\xe3"):
        return "sound"
    if head[:4] in (b"OggS", b"fLaC"):
        return "sound"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "sound"
    # Numpy's own magic. Nothing anybody is handed - a kept latent - but it is
    # held against its name like every other file here.
    if head[:6] == b"\x93NUMPY":
        return "latent"
    return None


def find_run(run_id: str) -> tuple[Path | None, str]:
    """The one folder named exactly `run_id`. No pattern: a run id is a name."""
    if "/" in run_id or "\\" in run_id:
        return None, "a run id is a folder name, not a path"
    hits = [p for p in EXPORTS.glob("*/*/*") if p.is_dir() and p.name == run_id]
    if not hits:
        return None, "no such run folder under exports/json"
    if len(hits) > 1:
        return None, f"{len(hits)} folders carry this name: {', '.join(str(h) for h in hits)}"
    return hits[0], ""


def rebuild(run_folder: Path):
    """Return (entities or None, one line saying what happened)."""
    record = json.loads((run_folder / "metadata.json").read_text(encoding="utf-8"))
    entities = record.get("entities", [])

    for entity in entities:
        if "type" not in entity:
            return None, "an entity carries no `type` - this is a canvas-shaped record"
        if "/" in (entity.get("filename") or ""):
            return None, "the record mixes final/ with another folder - it will not be reordered here"

    listed = {e["filename"]: e for e in entities if e.get("filename")}

    final = run_folder / "final"
    if not final.is_dir():
        return None, "no final/ folder"

    on_disk, unnamed = [], []
    for p in sorted(final.iterdir()):
        if not p.is_file():
            continue
        (on_disk if NAMED.match(p.name) else unnamed).append(p)
    if unnamed:
        return None, f"final/ holds files without an NN_<type> name: {', '.join(p.name for p in unnamed)}"

    gone = sorted(set(listed) - {p.name for p in on_disk})
    if gone:
        return None, f"the record names {len(gone)} file(s) that are not on disk: {', '.join(gone)}"

    unlisted = [p.name for p in on_disk if p.name not in listed]
    if not unlisted:
        return None, "the record already names every file"

    # The folder must be able to order itself.
    stamps = {}
    for p in on_disk:
        stamps.setdefault(p.stat().st_mtime, []).append(p.name)
    shared = [names for names in stamps.values() if len(names) > 1]
    if shared:
        return None, ("files share a modification time, so the folder cannot order them: "
                      + "; ".join(", ".join(sorted(n)) for n in shared))

    # ...and its clocks must still describe this run.
    for name, entity in listed.items():
        recorded = entity.get("timestamp")
        if not recorded:
            continue
        try:
            drift = abs(datetime.fromisoformat(recorded).timestamp() - (final / name).stat().st_mtime)
        except ValueError:
            return None, f"{name} carries an unreadable timestamp: {recorded}"
        if drift > CLOCK_TOLERANCE_S:
            return None, (f"{name} was written {drift:.0f}s away from the time the record gives it - "
                          "the file times do not describe this run")

    rebuilt = []
    for p in on_disk:
        stem = NAMED.match(p.name).group(2)
        if stem not in KNOWN_TYPES:
            return None, f"{p.name} carries a name this script cannot type: {stem}"
        if stem.startswith("output_"):
            word = stem.split("_", 1)[1]
            if word not in NAME_KIND:
                return None, f"{p.name} names an output kind this script cannot check: {word}"
            if sniff(p) != NAME_KIND[word]:
                return None, (f"{p.name} does not hold what its name claims "
                              f"(bytes say {sniff(p) or 'nothing recognisable'})")

    on_disk.sort(key=lambda p: p.stat().st_mtime)
    for seq, p in enumerate(on_disk, start=1):
        stem, ext = NAMED.match(p.name).group(2), NAMED.match(p.name).group(3)
        kept = listed.get(p.name)
        if kept:
            entity = dict(kept)
            entity["sequence"] = seq
        else:
            meta = {"recovered_from_file": True, "timestamp_source": "file_mtime"}
            if stem.startswith("output_"):
                meta["format"] = ext.lower()
            entity = {
                "sequence": seq,
                "type": stem,
                "filename": p.name,
                "timestamp": datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
                "metadata": meta,
            }
        rebuilt.append(entity)

    return rebuilt, f"{len(unlisted)} of {len(on_disk)} files were unlisted"


def outside_every_working_tree(path: Path) -> bool:
    """A backup may not land where a `git add` could ever reach it - and this
    repository has sibling worktrees next to it."""
    here = path.resolve()
    for candidate in [here, *here.parents]:
        if (candidate / ".git").exists():
            return False
    return True


def forget_miniatures(run_id: str, images: int) -> str:
    try:
        from my_app.services.thumbnails import drop_cached
    except Exception as exc:  # pragma: no cover - the cache is not reachable from here
        return f"could not reach the miniature cache ({exc}) - drop it by hand"
    drop_cached(run_id)
    for index in range(max(images, 1)):
        drop_cached(f"{run_id}_{index}")
    return f"miniatures forgotten for {run_id} and indices 0-{max(images, 1) - 1}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_ids", nargs="+")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--backup-dir", default=None)
    args = ap.parse_args()

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = Path(args.backup_dir) if args.backup_dir else REPO.parent / f"_restore_entities_backup_{stamp}"
    if not outside_every_working_tree(backup):
        print(f"refusing a backup inside a git working tree: {backup}", file=sys.stderr)
        return 2
    if args.apply:
        print(f"copies of every record this touches: {backup}")
        print()

    rewritten = refused = 0
    for run_id in args.run_ids:
        folder, why_not = find_run(run_id)
        if folder is None:
            print(f"{run_id}: left alone - {why_not}")
            refused += 1
            continue

        try:
            entities, why = rebuild(folder)
        except (OSError, ValueError) as exc:
            print(f"{run_id} ({folder}): left alone - its record could not be read: {exc}")
            refused += 1
            continue

        if entities is None:
            print(f"{run_id} ({folder}): left alone - {why}")
            refused += 1
            continue

        record = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
        print(f"{run_id} ({folder}): {why}")
        print(f"   entities {len(record.get('entities', []))} -> {len(entities)}")
        for e in entities:
            if e["type"].startswith("output_"):
                mark = " (recovered)" if e.get("metadata", {}).get("recovered_from_file") else ""
                print(f"      {e['sequence']:3d}  {e['type']:14s} {e['filename']}{mark}")

        if not args.apply:
            rewritten += 1
            continue

        target = backup / folder.parent.parent.name / folder.parent.name / folder.name
        target.mkdir(parents=True, exist_ok=True)
        if (target / "metadata.json").exists():
            print(f"   left alone - a backup of this record already lies at {target}")
            refused += 1
            continue
        shutil.copy2(folder / "metadata.json", target / "metadata.json")

        record["entities"] = entities
        written = folder / "metadata.json.writing"
        written.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(written, folder / "metadata.json")
        rewritten += 1

        images = sum(1 for e in entities if e["type"] == "output_image")
        print(f"   {forget_miniatures(run_id, images)}")

    print()
    if args.apply:
        print(f"records rewritten: {rewritten}   left alone: {refused}")
        if rewritten:
            print("the running backend still holds its own copy: systemctl restart ai4artsed-backend")
    else:
        print(f"dry run - nothing written. runs that would be rewritten: {rewritten}   left alone: {refused}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
