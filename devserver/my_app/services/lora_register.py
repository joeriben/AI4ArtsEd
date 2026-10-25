"""
The LoRA register: which adapter files this platform offers, to whom, and
with which word in front of the prompt. WHICH MODEL is no longer one of them:
the Settings let an admin tick the models off by hand until 2026-09-22, and
the file says itself what it was trained over — `my_app/services/lora_base.py`
reads it, and `configs_for` below joins it to the configs that run it.

Until 2026-09-21 an adapter reached a run by its file name alone —
`training_service.list_trained_loras()` globbed `sd35_*` in the LoRA folder and
`resolve_loras()` accepted any of those. A name pattern cannot say who may see
an adapter (a personal training must never appear in a workshop, issue #70),
what to write to call it, or which model's workflow loads it (a hand-picked
Flux 2 with the "Cooked Film" perspective in the ring put an SD3.5 adapter into
the Flux workflow). The register row (`my_app/lab/models.py::LoraAdapter`)
says all of it, and every run that goes through `custom_params['loras']` on
the schema-pipeline routes reads it here: the Flow's generation route with the
tiles and the perspective in the ring, and the four-stage route with the
perspective alone.

The LoRA Explorer in the Latent Lab keeps reading the folder through the
training service (the direct route): it is about the epochs of what THIS place
trained, which is a different question from what a surface offers.

Sessions: every function opens a session of its own and closes it before it
returns. The thread-scoped session (`SessionLocal()`) is right for a request
thread, whose teardown removes it; a generation thread has no teardown, and a
session taken there would hold its pool connection through the GPU gate and
the whole render.

Location: devserver/my_app/services/lora_register.py
"""
from __future__ import annotations

import logging
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from config import LORA_OUTPUT_DIR
from schemas.engine.config_loader import config_is_hidden

logger = logging.getLogger(__name__)

# What a LoRA scale means: outside this range the adapter either does nothing
# or drowns the model. The same clamp the training service applied.
STRENGTH_MIN = 0.0
STRENGTH_MAX = 2.0

# Kohya writes an intermediate every two epochs as `<stem>-000004.safetensors`.
_EPOCH_SUFFIX = re.compile(r"^(?P<stem>.+)-(?P<epoch>\d{6})$")
# The preset that brings an adapter says what to write for it, in this form.
_TRIGGER_TERM = re.compile(r"trigger term\s+['‘’\"]([^'‘’\"]+)['‘’\"]", re.IGNORECASE)


@contextmanager
def _session() -> Iterator[Any]:
    """A session of its own, closed on the way out (see the module note)."""
    from my_app.lab.db import SessionLocal
    db = SessionLocal.session_factory()
    try:
        yield db
    finally:
        db.close()


def is_present(file: str) -> bool:
    """Whether the registered file lies in the LoRA folder right now."""
    try:
        return (LORA_OUTPUT_DIR / file).is_file()
    except (OSError, TypeError, ValueError):
        return False


def _check_file(file: Any) -> str:
    file = str(file or "").strip()
    if (
        not file
        or "/" in file
        or "\\" in file
        or not file.endswith(".safetensors")
        or len(file) <= len(".safetensors")
    ):
        raise ValueError("file must be a .safetensors name in the LoRA folder")
    return file


def _check_course(db, course_id: Any) -> Optional[int]:
    from my_app.lab.models import Course
    if course_id in (None, "", 0):
        return None
    try:
        cid = int(course_id)
    except (TypeError, ValueError):
        raise ValueError("course_id must be a number")
    if db.get(Course, cid) is None:
        raise ValueError(f"no course with id {cid}")
    return cid


def display_name(file: str) -> str:
    """A name to start from where nobody gave one: the file without extension,
    epoch suffix and the training place's prefix, underscores as spaces."""
    from my_app.services.training_service import SD35_LORA_PREFIX
    stem = Path(file).stem
    m = _EPOCH_SUFFIX.match(stem)
    if m:
        stem = m.group("stem")
    if stem.startswith(SD35_LORA_PREFIX):
        stem = stem[len(SD35_LORA_PREFIX):]
    return " ".join(stem.replace("_", " ").split()) or stem


def session_scope(client_course_id: Any = None) -> Tuple[Optional[int], Optional[int]]:
    """(course_id, user_id) the current request may act for, by the rule the
    platform set for a course named by the client (chat_routes,
    BAUPLAN Entscheid 1): a participant's course is the one pinned in the
    session and nothing the client says; an educator or admin may name a
    course they lead (`is_course_educator`, admin passes); anonymous is no
    course and no user. Outside a request context: (None, None)."""
    try:
        from my_app.lab.auth_service import current_course_id, current_user, is_course_educator
        from my_app.lab.models import Role
        user = current_user()
    except Exception:
        return None, None
    if user is None:
        return None, None
    if user.role == Role.participant:
        return current_course_id(), user.id
    if client_course_id in (None, "", "null"):
        return current_course_id(), user.id
    try:
        cid = int(client_course_id)
    except (TypeError, ValueError):
        return current_course_id(), user.id
    try:
        if is_course_educator(user, cid):
            return cid, user.id
    except Exception as e:
        logger.info(f"[LORA-REGISTER] course {cid} not checked for user {user.id}: {e}")
    return None, user.id


# What `carrier_configs` read, kept for the life of the process (see there).
_carriers: Optional[List[Dict[str, Any]]] = None


def carrier_configs() -> List[Dict[str, Any]]:
    """The output configs whose workflow can load an adapter, read off the
    chunks themselves: a ComfyUI workflow with a `CheckpointLoaderSimple`
    node is where `_inject_lora_nodes` chains the loaders in
    (schemas/engine/backend_router.py), and a python chunk that names a
    `lora_chunk` is redirected to one. Hidden configs stay out (`display.hidden`,
    the platform's way, and the older `hidden` / `meta.hidden`), and so does
    every chunk that is no image chunk (`output_image_*`, the platform's own
    naming): an adapter trained over an image model is loaded by image
    workflows. Each entry also says which bases its workflow runs, as the
    config names them (`meta.lora_base`); `configs_for` matches those against
    what an adapter file says it was trained over. A config that names no base
    carries no adapter. A list written by hand would drift from the chunks the
    moment one changes.

    Read once per process: the configs are read at start (`config_loader`), so
    an edited config already needs a restart to be seen."""
    global _carriers
    if _carriers is not None:
        return _carriers
    import ast
    import json as _json

    schemas = Path(__file__).resolve().parents[2] / "schemas"
    chunks = schemas / "chunks"

    def chunk_carries(name: str, depth: int = 0) -> bool:
        if not name or depth > 2:
            return False
        js = chunks / f"{name}.json"
        if js.is_file():
            try:
                wf = _json.loads(js.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return False
            # A chunk that runs as a legacy workflow is handed to
            # `_process_legacy_workflow` (schemas/engine/backend_router.py),
            # which passes the workflow through untouched and reaches no
            # LoraLoader. It holds a checkpoint loader like any other and would
            # read here as a carrier of adapters it never loads.
            if isinstance(wf, dict) and wf.get("execution_mode") == "legacy_workflow":
                return False
            nodes = wf.get("workflow", wf) if isinstance(wf, dict) else {}
            return any(
                isinstance(n, dict) and n.get("class_type") == "CheckpointLoaderSimple"
                for n in (nodes.values() if isinstance(nodes, dict) else [])
            )
        py = chunks / f"{name}.py"
        if py.is_file():
            try:
                tree = ast.parse(py.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):
                return False
            for node in tree.body:
                if isinstance(node, ast.Assign) and any(
                    getattr(t, "id", None) == "CHUNK_META" for t in node.targets
                ):
                    try:
                        meta = ast.literal_eval(node.value)
                    except ValueError:
                        return False
                    target = meta.get("lora_chunk") if isinstance(meta, dict) else None
                    return bool(target) and target != name and chunk_carries(target, depth + 1)
        return False

    out: List[Dict[str, Any]] = []
    for cfg_path in sorted((schemas / "configs" / "output").glob("*.json")):
        try:
            cfg = _json.loads(cfg_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(cfg, dict) or config_is_hidden(cfg):
            continue
        chunk = (cfg.get("parameters") or {}).get("OUTPUT_CHUNK")
        if not isinstance(chunk, str) or not chunk.startswith("output_image_"):
            continue
        if not chunk_carries(chunk):
            continue
        name = cfg.get("name")
        if isinstance(name, dict):
            name = name.get("en") or next((v for v in name.values() if v), "")
        bases = [
            b.strip().lower()
            for b in ((cfg.get("meta") or {}).get("lora_base") or [])
            if isinstance(b, str) and b.strip()
        ]
        out.append({"id": cfg_path.stem, "name": str(name or cfg_path.stem), "bases": bases})
    _carriers = out
    return out


def configs_for_base(base: str) -> List[str]:
    """The output configs that run a base: those whose workflow can load an
    adapter at all (`carrier_configs`) and whose config names this base
    (`meta.lora_base`). A base no config names reaches none."""
    if not base:
        return []
    return [c["id"] for c in carrier_configs() if base in c["bases"]]


def configs_for(file: str) -> List[str]:
    """The output configs an adapter file reaches, from what the file says it
    was trained over (`lora_base.declared_base`). A file that names no base, or
    one no config runs, reaches none and is applied nowhere."""
    from my_app.services.lora_base import declared_base

    return configs_for_base(declared_base(file))


def folder_files() -> List[str]:
    """Every adapter file in the LoRA folder, registered or not, sorted."""
    try:
        return sorted(p.name for p in LORA_OUTPUT_DIR.glob("*.safetensors") if p.is_file())
    except OSError:
        return []


def _row_dict(row, db=None) -> Dict[str, Any]:
    from my_app.lab.models import Course, User
    from my_app.services.lora_base import declared_base
    d = row.to_dict()
    d["present"] = is_present(row.file)
    # The model comes from the file and from nowhere else (2026-09-22): `base`
    # is what the file says it was trained over, `base_configs` the configs
    # that run it.
    d["base"] = declared_base(row.file)
    d["base_configs"] = configs_for_base(d["base"])
    d["course_name"] = ""
    d["owner_name"] = ""
    if db is not None:
        if row.course_id is not None:
            c = db.get(Course, row.course_id)
            d["course_name"] = c.name if c is not None else ""
        if row.owner_id is not None:
            u = db.get(User, row.owner_id)
            d["owner_name"] = u.username if u is not None else ""
    return d


def _offered(row, course_id: Optional[int], user_id: Optional[int]) -> bool:
    """Whether a session may see and lay this adapter: released to the
    platform, released to the session's course, or trained by the session's
    user. What is released nowhere is offered to nobody but its owner."""
    from my_app.lab.models import LoraVisibility
    if row.visibility == LoraVisibility.platform:
        return True
    if user_id is not None and row.owner_id == int(user_id):
        return True
    return (
        row.visibility == LoraVisibility.course
        and course_id is not None
        and row.course_id == int(course_id)
    )


def visible_adapters(course_id: Optional[int], user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """What a session is offered (`_offered`), sorted by name; `present` says
    whether the file is there."""
    from my_app.lab.models import LoraAdapter

    try:
        with _session() as db:
            rows = db.query(LoraAdapter).order_by(LoraAdapter.name).all()
            return [_row_dict(r, db) for r in rows if _offered(r, course_id, user_id)]
    except Exception as e:  # the lab DB is fail-safe; a surface without it shows no adapters
        logger.warning(f"[LORA-REGISTER] register unreadable: {e}")
        return []


def all_adapters() -> List[Dict[str, Any]]:
    """Every row, for the Settings table. Sorted by name."""
    from my_app.lab.models import LoraAdapter

    with _session() as db:
        rows = db.query(LoraAdapter).order_by(LoraAdapter.name).all()
        return [_row_dict(r, db) for r in rows]


def unregistered_files() -> List[Dict[str, Any]]:
    """Files in the folder no row names: what the Settings table offers to
    register, each with what the training place still knows about it — the
    project's trigger (`project_trigger`: trigger.txt, else the captions) — so
    the old stock is registered from its own record rather than typed. A file
    that is no training of this place comes with an empty trigger. `base` and
    `base_configs` are read off the file itself, as they are for a row. The
    accelerators of the video pipelines stand here too, and stay here:
    registering is a decision, not a sweep."""
    from my_app.lab.models import LoraAdapter
    from my_app.services.lora_base import declared_base
    from my_app.services.training_service import (
        DATASET_BASE_DIR, SD35_LORA_PREFIX, training_service,
    )

    with _session() as db:
        known = {r.file for r in db.query(LoraAdapter.file).all()}
    out: List[Dict[str, Any]] = []
    for f in folder_files():
        if f in known:
            continue
        entry: Dict[str, Any] = {
            "file": f,
            "name": display_name(f),
            "trigger": "",
            "base": declared_base(f),
            "base_configs": configs_for(f),
        }
        stem = Path(f).stem
        if stem.startswith(SD35_LORA_PREFIX):
            project = stem[len(SD35_LORA_PREFIX):]
            m = _EPOCH_SUFFIX.match(project)
            if m:
                project = m.group("stem")
            try:
                if (DATASET_BASE_DIR / project).is_dir():
                    entry["name"] = project
                    entry["trigger"] = training_service.project_trigger(project)
            except Exception as e:
                logger.info(f"[LORA-REGISTER] no record read for '{f}': {e}")
        out.append(entry)
    return out


def _check_category(value: Any) -> str:
    """The kind of thing an adapter makes, as a short key. The vocabulary is
    NOT fixed here: what the Settings offer stands in the frontend, and a key
    the platform has no word for is shown as it is written. Kept to the shape
    of a key so it can carry a label later.

    Refused rather than coerced, like the file and the configs beside it: a
    dict (the shape every multilingual field on this platform has), a list, a
    number or a true would each have become a plausible-looking key nobody
    ever chose — `{"en": "Foto"}` read as `en_foto` on the ring."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"category must be a string — not {type(value).__name__}")
    key = "_".join(value.strip().lower().split())
    key = "".join(c for c in key if c.isalnum() or c in "_-")[:40]
    if value.strip() and not key:
        raise ValueError(f"category {value!r} holds nothing that could be a key")
    return key


def register_adapter(
    file: str,
    name: str,
    trigger: str = "",
    owner_id: Optional[int] = None,
    course_id: Optional[int] = None,
    visibility: str = "none",
    category: str = "",
    keep_existing: bool = False,
) -> Dict[str, Any]:
    """Write the row for `file`. Called by the training place when a project
    is created, by the seed for the presets' own adapters, and by the
    Settings for the older files. With `keep_existing` a row that is already
    there is returned as it stands: the training place and the seed never
    overwrite what an admin wrote, and a project name typed twice never
    rewrites a platform row."""
    from my_app.lab.models import LoraAdapter, LoraVisibility

    file = _check_file(file)
    try:
        vis = LoraVisibility(visibility or "none")
    except ValueError:
        raise ValueError(f"visibility must be one of platform, course, none — not {visibility!r}")
    if vis == LoraVisibility.course and course_id in (None, "", 0):
        raise ValueError("a course release names the course")
    name = " ".join((name or "").split()) or display_name(file)
    with _session() as db:
        cid = _check_course(db, course_id)
        row = db.query(LoraAdapter).filter(LoraAdapter.file == file).one_or_none()
        if row is not None and keep_existing:
            # The one thing a standing row can LACK is the kind: the column was
            # added on 2026-09-22, long after the rows the seed meets were
            # written. A row without one takes the kind its preset names; a row
            # that has one keeps it, so what an admin chose stands. The price is
            # that clearing the kind of a preset's adapter does not hold — the
            # next start fills it again.
            kind = _check_category(category)
            if kind and not (row.category or ""):
                row.category = kind
                db.commit()
                logger.info(f"[LORA-REGISTER] '{file}' took the kind '{kind}' of its preset")
            else:
                logger.info(f"[LORA-REGISTER] '{file}' is registered already — the row stands")
            return _row_dict(row, db)
        if row is None:
            row = LoraAdapter(file=file)
            db.add(row)
        row.name = name[:200]
        row.trigger = " ".join((trigger or "").split())
        row.category = _check_category(category)
        row.owner_id = int(owner_id) if owner_id is not None else None
        row.course_id = cid
        row.visibility = vis
        db.commit()
        return _row_dict(row, db)


def update_adapter(adapter_id: int, changes: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Change what the Settings table lets an admin change. None when there is
    no such row. A course release without a course is refused only where the
    change touches the release or the course: a row whose course was deleted
    (the FK sets it NULL) can still be renamed, and released elsewhere."""
    from my_app.lab.models import LoraAdapter, LoraVisibility

    with _session() as db:
        row = db.get(LoraAdapter, int(adapter_id))
        if row is None:
            return None
        if "file" in changes:
            file = _check_file(changes["file"])
            other = db.query(LoraAdapter).filter(LoraAdapter.file == file, LoraAdapter.id != row.id).first()
            if other is not None:
                raise ValueError(f"{file} is already registered as {other.name!r}")
            row.file = file
        if "name" in changes:
            name = " ".join(str(changes["name"] or "").split())
            if not name:
                raise ValueError("name must not be empty")
            row.name = name[:200]
        if "trigger" in changes:
            row.trigger = " ".join(str(changes["trigger"] or "").split())
        if "category" in changes:
            row.category = _check_category(changes["category"])
        if "course_id" in changes:
            row.course_id = _check_course(db, changes["course_id"])
        if "visibility" in changes:
            try:
                row.visibility = LoraVisibility(str(changes["visibility"]))
            except ValueError:
                raise ValueError(
                    f"visibility must be one of platform, course, none — not {changes['visibility']!r}"
                )
        if (
            ("visibility" in changes or "course_id" in changes)
            and row.visibility == LoraVisibility.course
            and row.course_id is None
        ):
            raise ValueError("a course release names the course")
        db.commit()
        return _row_dict(row, db)


def delete_adapter(adapter_id: int) -> bool:
    """Take the row out. The file stays where it is: the register says what is
    offered, the folder says what exists."""
    from my_app.lab.models import LoraAdapter

    with _session() as db:
        row = db.get(LoraAdapter, int(adapter_id))
        if row is None:
            return False
        db.delete(row)
        db.commit()
        return True


def seed_from_presets() -> int:
    """The adapters the platform's own perspectives bring (`meta.loras` of an
    interception config) get their row once, at start: the file, a name from
    the file, the trigger term the preset instructs the interception to write
    (read off its context), and the platform release, because a shipped preset
    is the platform's material. A row that exists is left as it stands, so what
    an admin changed holds. Returns the number of rows written."""
    import json as _json

    folder = Path(__file__).resolve().parents[2] / "schemas" / "configs" / "interception"
    written = 0
    for cfg_path in sorted(folder.glob("*.json")):
        try:
            cfg = _json.loads(cfg_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        entries = (cfg.get("meta") or {}).get("loras") if isinstance(cfg, dict) else None
        if not isinstance(entries, list) or not entries:
            continue
        context = cfg.get("context")
        if isinstance(context, dict):
            context = context.get("en") or next((v for v in context.values() if v), "")
        m = _TRIGGER_TERM.search(str(context or ""))
        trigger = m.group(1).strip() if m else ""
        # The kind comes from the preset's own word for what it makes
        # (`meta.medium`), never from a guess at the file name.
        category = str((cfg.get("meta") or {}).get("medium") or "")
        for entry in entries:
            file = entry.get("name") if isinstance(entry, dict) else None
            if not isinstance(file, str) or not file:
                continue
            try:
                before = registered(file)
                register_adapter(
                    file=file,
                    name=display_name(file),
                    trigger=trigger,
                    visibility="platform",
                    category=category,
                    keep_existing=True,
                )
                if not before:
                    written += 1
                    logger.info(f"[LORA-REGISTER] seeded '{file}' from preset '{cfg_path.stem}'")
            except Exception as e:
                logger.warning(f"[LORA-REGISTER] preset '{cfg_path.stem}' not seeded: {e}")
    return written


def registered(file: str) -> bool:
    from my_app.lab.models import LoraAdapter
    with _session() as db:
        return db.query(LoraAdapter.id).filter(LoraAdapter.file == file).first() is not None


def _clamp(strength: Any, fallback: float = 1.0) -> float:
    try:
        s = float(strength)
    except (TypeError, ValueError):
        s = fallback
    return max(STRENGTH_MIN, min(STRENGTH_MAX, s))


def trigger_tags(trigger: Optional[str]) -> List[str]:
    """The tags of a trigger, as the captions carry them: `a, b, c` is three
    words in front of the prompt, each checked on its own."""
    return [t.strip() for t in (trigger or "").split(",") if t.strip()]


def loras_for_run(
    config_loras: Optional[List[Dict[str, Any]]],
    requested: Optional[List[Dict[str, Any]]],
    output_config: str,
    course_id: Optional[int],
    user_id: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """What reaches the workflow, and the words that go in front of the prompt.

    Two sources, one rule: an adapter is applied when the register knows its
    file, offers it to this session (`_offered`), the file lies in the folder,
    AND `output_config` runs the model the FILE says it was trained over
    (`configs_for`).

    `config_loras` come from the perspective in the ring (the `meta.loras` of
    its config). One that fails the rule is left out with a log line — never
    put into a workflow that was not written for it, and never applied where
    the surface, which sees the register through the same rule, marks it as
    not used.

    `requested` comes from the client (the LoRA tiles in the ring). A file the
    register does not know, or that this session is not offered, is a client
    error and raises ValueError, as is a file that is not there; one this
    config cannot carry is left out with a log line, exactly as the surface
    marks it. Where the same file stands in both lists, the hand's strength
    wins.

    Returns (applied, triggers): `applied` as `[{name, strength}]` in the order
    perspective first, then request; `triggers` the tags of the applied
    adapters' trigger words, each once, in that order.
    """
    from my_app.lab.models import LoraAdapter

    config_loras = list(config_loras or [])
    if requested is not None and not isinstance(requested, list):
        raise ValueError("loras must be a list")
    requested = list(requested or [])
    if not config_loras and not requested:
        return [], []

    try:
        with _session() as db:
            rows = {r.file: r for r in db.query(LoraAdapter).all()}
    except Exception as e:
        if requested:
            raise ValueError(f"LoRA register unavailable: {e}")
        logger.warning(f"[LORA-REGISTER] register unreadable, the perspective's LoRA is left out: {e}")
        return [], []

    def carries(row) -> bool:
        return output_config in configs_for(row.file)

    applied: List[Dict[str, Any]] = []
    strengths: Dict[str, float] = {}
    order: List[str] = []

    for entry in config_loras:
        name = entry.get("name") if isinstance(entry, dict) else None
        row = rows.get(name)
        if row is None:
            logger.warning(f"[LORA-REGISTER] '{name}' is not in the register — the perspective's LoRA is left out")
            continue
        if not _offered(row, course_id, user_id):
            logger.warning(f"[LORA-REGISTER] '{name}' is not released to this session — the perspective's LoRA is left out")
            continue
        if not is_present(row.file):
            logger.warning(f"[LORA-REGISTER] '{name}' is not in the LoRA folder — the perspective's LoRA is left out")
            continue
        if not carries(row):
            logger.info(f"[LORA-REGISTER] '{name}' is not carried by '{output_config}' — left out")
            continue
        if name not in strengths:
            order.append(name)
        strengths[name] = _clamp(entry.get("strength", 1.0))

    for entry in requested:
        name = entry.get("name") if isinstance(entry, dict) else None
        row = rows.get(name) if name else None
        if row is None or not _offered(row, course_id, user_id):
            raise ValueError(f"unknown LoRA: {name!r}")
        if not is_present(row.file):
            raise ValueError(f"LoRA file absent: {row.file}")
        try:
            strength = float(entry.get("strength", 1.0))
        except (TypeError, ValueError):
            raise ValueError(f"strength for {name!r} is not a number")
        if not carries(row):
            logger.info(f"[LORA-REGISTER] '{name}' is not carried by '{output_config}' — left out")
            continue
        if name not in strengths:
            order.append(name)
        strengths[name] = _clamp(strength)

    triggers: List[str] = []
    for name in order:
        applied.append({"name": name, "strength": strengths[name]})
        for tag in trigger_tags(rows[name].trigger):
            if tag.lower() not in {t.lower() for t in triggers}:
                triggers.append(tag)
    return applied, triggers


def missing_triggers(prompt: Optional[str], triggers: List[str]) -> List[str]:
    """The tags `with_triggers` puts in front of this prompt: those it does
    not carry yet. The client shows them before the words it sent."""
    if not triggers or not prompt:
        return []
    low = prompt.lower()
    return [t for t in triggers if t.lower() not in low]


def with_triggers(prompt: Optional[str], triggers: List[str]) -> Optional[str]:
    """The prompt with the trigger tags in front, in the form the captions
    were written in (`trigger, caption`). A tag the prompt already carries is
    left where it is — the perspectives that bring an adapter instruct the
    interception to write the trigger term into its text ("You will activate
    a respective LORA by integrating the trigger term …"), and a second copy
    in front would move the prompt. An empty prompt stays empty."""
    missing = missing_triggers(prompt, triggers)
    if not missing:
        return prompt
    return f"{', '.join(missing)}, {prompt}"
