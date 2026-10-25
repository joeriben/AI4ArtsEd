#!/usr/bin/env python3
"""Repair the runs whose sound or film was recorded as a picture.

Between 2026-02-01 and 2026-03-22 the platform typed the stage-4 result of the
music and film configs `output_image`, whatever it was: 47 HeartMuLa runs carry
an MP3 under that word and one WAN run an MP4. The files themselves are intact -
only the word the record uses for them is wrong, and that word is what every
reader goes by (`settings_routes.resolve_preview_media`,
`favorites_routes._entity_types_for`, `media_routes._find_entities_by_type`).
In the research table those runs are therefore offered as pictures, the
miniature cannot be built, and the row shows an empty preview; a star on such a
run would pass the "does it hold one?" test and produce a plate that draws
nothing.

Since 2026-03-22 the same configs record correctly (`output_music`,
`output_audio`, `output_video`), so this repairs a closed period and is meant to
be run ONCE.

Per affected run:
  * the file is SNIFFED by its first bytes, never by its suffix - a file that
    really is a picture is left alone, whatever it is called;
  * the new word is taken from what the platform ITSELF wrote for that same
    config afterwards, not from a table in this script; where a config has no
    later run, the sniffed medium decides (`output_video` / `output_audio`);
  * the file is renamed so its name carries the same word;
  * `expected_outputs` is corrected too, but only where no picture remains;
  * metadata.json is rewritten with the recorder's own formatting
    (`json.dumps(..., indent=2, ensure_ascii=False)`).

Every metadata.json that is touched is copied first, with its path, into a
directory OUTSIDE the repository. Dry run by default; `--apply` writes.
"""
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
IMAGE_TYPE = 'output_image'

#: Recorded as `output_*` and no medium at all: the two SD 3.5 rows keep the
#: picture's final latent (numpy, `.npy`) next to it so a SET can be averaged
#: before the decoder - the Mean Images instrument. It is never what a config
#: 'speaks', and a mis-typed picture is never one, so it stays out of both.
LATENT_TYPE = 'output_latent'

#: What a file says it is, by its first bytes.
def sniff(path: Path):
    try:
        with open(path, 'rb') as fh:
            head = fh.read(16)
    except OSError:
        return None
    if head[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image'
    if head[:3] == b'\xff\xd8\xff':
        return 'image'
    if head[:6] in (b'GIF87a', b'GIF89a'):
        return 'image'
    if head[:4] == b'RIFF' and head[8:12] == b'WEBP':
        return 'image'
    # An ISO base-media file opens with the length of its first box and then
    # the word: `ftyp` sits at 4, not at 8.
    if head[4:8] == b'ftyp':
        return 'film'
    if head[:3] == b'ID3':
        return 'sound'
    if head[:2] in (b'\xff\xfb', b'\xff\xf3', b'\xff\xf2', b'\xff\xe3'):
        return 'sound'
    if head[:4] == b'OggS':
        return 'sound'
    if head[:4] == b'fLaC':
        return 'sound'
    if head[:4] == b'RIFF' and head[8:12] == b'WAVE':
        return 'sound'
    if head[:6] == b'\x93NUMPY':
        return 'latent'
    return None


#: Only what a picture may turn OUT to be. A latent is not a medium and no
#: repair renames anything to it, so `latent` has no entry here.
GENERIC = {'sound': 'output_audio', 'film': 'output_video'}


def load_runs(store: Path):
    """Every run in the store as (folder, metadata)."""
    for root, _dirs, files in os.walk(store):
        if 'metadata.json' not in files:
            continue
        try:
            with open(Path(root) / 'metadata.json', encoding='utf-8') as fh:
                yield Path(root), json.load(fh)
        except (OSError, ValueError):
            continue


def main():
    apply = '--apply' in sys.argv
    store = Path(config.JSON_STORAGE_DIR)

    runs = list(load_runs(store))
    print(f'runs in the store: {len(runs)}')

    # What each config records when it records correctly - read off the store,
    # newest first, so the repair speaks the platform's own current word.
    spoken = {}
    for folder, meta in runs:
        cfg = str(meta.get('config_name') or '')
        when = str(meta.get('timestamp') or '')
        kinds = [e.get('type') for e in meta.get('entities', [])
                 if str(e.get('type', '')).startswith('output_')]
        kinds = [k for k in kinds if k not in (IMAGE_TYPE, LATENT_TYPE)]
        if not kinds:
            continue
        if cfg not in spoken or when > spoken[cfg][0]:
            spoken[cfg] = (when, kinds[-1])

    work, unread = [], []
    for folder, meta in runs:
        final = folder / 'final'
        for entity in meta.get('entities', []):
            if entity.get('type') != IMAGE_TYPE:
                continue
            name = str(entity.get('filename') or '')
            if not name:
                continue
            path = final / name if (final / name).exists() else folder / name
            cfg = str(meta.get('config_name') or '')
            if path.exists():
                kind = sniff(path)
                if kind == 'image':
                    # Really a picture, so the word is right - whatever the
                    # file happens to be called. Not a case, not a remainder.
                    continue
                if kind is None:
                    # Unreadable by these first bytes: named, never guessed at.
                    unread.append((cfg, folder.name, name, 'first bytes say nothing'))
                    continue
            else:
                # The run's file is gone - a run that broke off, or a folder
                # that was cleared. The record is still wrong about what it
                # was, and that much can be put right; the NAME stays as it
                # was written, because it is the name the file had.
                said = str((entity.get('metadata') or {}).get('format') or '')
                ext = os.path.splitext(name)[1].lower().lstrip('.')
                kind = {'mp3': 'sound', 'wav': 'sound', 'flac': 'sound', 'ogg': 'sound',
                        'm4a': 'sound', 'mp4': 'film', 'webm': 'film', 'mov': 'film'}.get(said)
                if kind is None or said != ext:
                    unread.append((cfg, folder.name, name, 'file gone, format %r' % said))
                    continue
                path = None
            target = spoken.get(cfg, (None, None))[1] or GENERIC[kind]
            work.append({
                'folder': folder, 'meta': meta, 'entity': entity,
                'path': path, 'kind': kind, 'config': cfg, 'target': target,
                'when': str(meta.get('timestamp') or ''),
            })

    print(f'runs to repair: {len(work)}')
    if not work:
        return 0

    by_target = {}
    for w in work:
        key = (w['config'], w['kind'], w['target'], w['path'] is None)
        by_target[key] = by_target.get(key, 0) + 1
    for (cfg, kind, target, gone), n in sorted(by_target.items()):
        said = spoken.get(cfg)
        why = f'the config itself since {said[0][:10]}' if said else 'no later run of this config - the file decides'
        note = ', file gone: word only, name kept' if gone else ''
        print(f'  {n:3d}  {cfg:20s} {kind:5s} -> {target:14s} ({why}{note})')

    # Never a silent remainder: what this script does NOT touch is named.
    if unread:
        print(f'\nleft alone ({len(unread)}) - look at these by hand:')
        for cfg, run, name, why in unread:
            print(f'  {cfg:20s} {run} {name} ({why})')

    if not apply:
        print('\ndry run - nothing written. Pass --apply.')
        return 0

    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = REPO.parent / f'_repair_sound_runs_backup_{stamp}'
    assert REPO not in backup.parents and backup != REPO, 'the copy must lie outside the repository'
    backup.mkdir(parents=True, exist_ok=False)

    done = 0
    for w in work:
        folder, meta, entity, path = w['folder'], w['meta'], w['entity'], w['path']
        target, old_name = w['target'], str(entity.get('filename'))

        rel = folder.relative_to(store)
        copy_to = backup / rel / 'metadata.json'
        copy_to.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(folder / 'metadata.json', copy_to)

        if path is not None:
            new_name = old_name.replace(IMAGE_TYPE, target)
            new_path = path.with_name(new_name)
            if new_path.exists() and new_path != path:
                print(f'  SKIPPED {folder.name}: {new_name} is already there')
                continue
            if new_path != path:
                os.rename(path, new_path)
            entity['filename'] = new_name

        entity['type'] = target

        left = any(e.get('type') == IMAGE_TYPE for e in meta.get('entities', []))
        if not left:
            meta['expected_outputs'] = [
                target if x == IMAGE_TYPE else x for x in (meta.get('expected_outputs') or [])
            ]

        tmp = folder / 'metadata.json.tmp'
        tmp.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding='utf-8')
        os.replace(tmp, folder / 'metadata.json')
        done += 1

    print(f'\nrepaired: {done}')
    print(f'copies of every touched record: {backup}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
