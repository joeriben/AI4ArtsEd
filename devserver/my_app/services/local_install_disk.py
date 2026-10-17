"""What an installer reads off the disk: the bytes a download has written
so far, and the free space of the filesystem a folder will land on. Both
installers (local_llm_install, local_media_install) carried these two
functions letter for letter until 2026-10-10; they stand here once.
"""
import os
import shutil


def bytes_on_disk(folder: str, in_flight: bool = True) -> int:
    """What the download has written so far: the files it finished, plus,
    with in_flight, the blocks of every part still being written. The hub
    preallocates a part at its full size (sparse), so st_size would read
    100 % at once; st_blocks * 512 is what is actually there. The precheck
    counts finished files only: a part in flight is rewritten when the
    download is taken up again (the installers' module docstrings)."""
    done = 0
    if not os.path.isdir(folder):
        return 0
    for root, _dirs, files in os.walk(folder):
        for f in files:
            try:
                st = os.stat(os.path.join(root, f))
            except OSError:
                continue
            if f.endswith(".incomplete"):
                if in_flight:
                    done += min(st.st_size, st.st_blocks * 512)
            else:
                done += st.st_size
    return done


def free_bytes_under(path) -> int:
    """Free space of the filesystem `path` will be created on: the nearest
    existing ancestor is asked, so a precheck creates nothing."""
    p = os.path.abspath(str(path))
    while not os.path.exists(p):
        parent = os.path.dirname(p)
        if parent == p:
            break
        p = parent
    return shutil.disk_usage(p).free
