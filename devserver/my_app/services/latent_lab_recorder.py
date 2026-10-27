"""
LatentLabRecorder - recording for Latent Lab experiments.

Frontend-primary hybrid: the surface POSTs parameters and results after each
generation; this recorder writes them to disk using the folder layout of
LivePipelineRecorder / CanvasRecorder (exports/json/YYYY-MM-DD/device_id/run_xxx/).

ONE RUN FOLDER PER GENERATION. It used to be one folder per open tab, with
every generation of that tab written into it. That folder was unreachable from
the platform's storage: the Ablage (favorites) addresses a RUN, one run holds
one thing to look at, and a tab folder holds a series - so what got stored was
the thin pipeline run with the finished picture, while the parameters and the
whole sequence sat in a folder nothing pointed at. The tab is still recorded:
every run carries the sitting it was made in (`session_id`, `generation`), so a
session can be reassembled without the nesting that hid its parts.

What a run folder holds:
    metadata.json                        tool, sitting, parameters, results, entities
    prompting_process/001_parameters.json
    prompting_process/002_step_01.jpg ...  the ordered parts, if the run made any
    final/NN_output_image.png            what the run produced

Phase 2 (future): QDA-compatible research format in exports/research/.
"""

import base64
import json
import logging
import os
import re
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from my_app.utils.media_ref import is_media_entity

logger = logging.getLogger(__name__)


def _marked(raw: bytes, entity_type: str, entity_metadata: Dict[str, Any]) -> bytes:
    """AI-Origin Disclosure (EU AI Act Art. 50) — see watermark_service.

    This recorder writes its files itself instead of going through
    LivePipelineRecorder.save_entity, which is where the marking is applied.
    For as long as that was so, everything the latent lab produced — the
    pictures a workshop takes home among them — left the house unmarked.

    Fail-open: an unmarked file beats no file (services/media_marking).
    """
    from my_app.services.media_marking import mark_or_pass

    return mark_or_pass(raw, entity_type, entity_metadata, "[LAB_RECORDER]")


#: The one shape a `ref` may have: `/api/media/<kind>/<run_id>/<index>`, the
#: address of one output of one recorded run. See `_output_bytes` for why the
#: recorder checks this itself instead of leaving it to the resolver.
_RUN_REF_RE = re.compile(r"^/api/media/(image|audio|video)/[A-Za-z0-9_\-]+/\d+$")


class LatentLabRecorder:
    """
    Recorder for one open instrument — one instance per tab, one folder per run.

    Key differences from LivePipelineRecorder:
    - No stage tracking, no expected_outputs, no progress
    - Receives pre-built data from the frontend (parameters, results, base64)
    - Lives for the tab; `record()` writes a run of its own each time
    """

    def __init__(
        self,
        session_id: str,
        latent_lab_tool: str,
        device_id: Optional[str] = None,
        user_id: str = 'anonymous',
        base_path: Optional[Path] = None,
    ):
        import uuid as uuid_module

        self.session_id = session_id
        self.latent_lab_tool = latent_lab_tool
        self.user_id = user_id
        self.device_id = device_id or f"lab_{uuid_module.uuid4().hex[:12]}"

        if base_path is None:
            from config import JSON_STORAGE_DIR
            base_path = JSON_STORAGE_DIR
        self.base_path = Path(base_path)

        # How many runs this sitting has made. It numbers them; it is not an
        # address — the run_id is.
        self.generation = 0

        logger.info(f"[LAB_RECORDER] Session {session_id} open for {latent_lab_tool}")

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(
        self,
        parameters: Dict[str, Any],
        results: Optional[Dict[str, Any]] = None,
        outputs: Optional[List[Dict[str, Any]]] = None,
        steps: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Record one generation as a run of its own.

        Args:
            parameters: Generation parameters (prompt, seed, cfg, etc.)
            results: Result metadata (seed, timing, statistics)
            outputs: Final outputs [{type, format, dataBase64 | ref, meta?}].
                A `ref` hands this recorder an ADDRESS inside the storage —
                `/api/media/<kind>/<run_id>/<index>`, the address the platform
                passes a picture around by. It is resolved, the file is read,
                and the bytes are copied into this run's `final/` folder like
                any other output: every run stays complete on its own. What the
                address spares is the base64 round trip — a composite that a
                route has already recorded as a run of its own travels as five
                dozen characters instead of being held on the surface and
                uploaded again.
            steps: The ordered parts [{format, dataBase64, meta?}] — denoising
                steps, axis cells, probe frames. `meta` is the instrument's own
                word about a part: this recorder carries it and does not read it.

        Returns:
            {"run_id": str, "entity_count": int, "entities": [...],
             "metadata": dict, "run_folder": str}

            `entities` is the record as it was WRITTEN: an output whose bytes
            could not be read or written is missing from it. A caller that hands
            out addresses into this run has to number them off this list rather
            than off the outputs it passed in, because the two differ exactly
            when a write failed.
        """
        self.generation += 1

        run_id = generate_run_id()
        date_folder = datetime.now().strftime('%Y-%m-%d')
        run_folder = self.base_path / date_folder / self.device_id / run_id
        final_folder = run_folder / "final"
        prompting_folder = run_folder / "prompting_process"
        final_folder.mkdir(parents=True, exist_ok=True)
        prompting_folder.mkdir(parents=True, exist_ok=True)

        metadata: Dict[str, Any] = {
            "run_id": run_id,
            "timestamp": datetime.now().isoformat(),
            "type": "latent_lab",
            "latent_lab_tool": self.latent_lab_tool,
            # The sitting this run was made in, and which run of it this is.
            "session_id": self.session_id,
            "generation": self.generation,
            "device_id": self.device_id,
            "user_id": self.user_id,
            "parameters": parameters or {},
            "results": results or {},
            "entities": [],
        }

        sequence = 0

        # 1) Parameters as JSON in prompting_process/
        sequence += 1
        params_filename = "001_parameters.json"
        (prompting_folder / params_filename).write_text(
            json.dumps(
                {
                    "parameters": parameters,
                    "results": results or {},
                    "timestamp": metadata["timestamp"],
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding='utf-8',
        )
        metadata["entities"].append({
            "sequence": sequence,
            "type": "latent_lab_params",
            "filename": f"prompting_process/{params_filename}",
            "timestamp": metadata["timestamp"],
            "metadata": parameters,
        })

        # 2) The ordered parts in prompting_process/
        #
        # One unreadable part must not cost the run. The metadata is written at
        # the end, so a raise here would leave a folder of files that no lookup
        # can find - the parameters and every part before it lost with it.
        for idx, step_data in enumerate(steps or []):
            fmt = step_data.get("format", "jpg")
            part_meta = dict(step_data.get("meta") or {})
            step_filename = f"002_step_{idx + 1:02d}.{fmt}"
            try:
                raw = base64.b64decode(step_data["dataBase64"])
                raw = _marked(raw, "latent_lab_step", {"step_index": idx, "format": fmt})
                (prompting_folder / step_filename).write_bytes(raw)
            except Exception as e:
                logger.warning(f"[LAB_RECORDER] Part {idx} of {run_id} not written: {e}")
                continue

            sequence += 1
            metadata["entities"].append({
                "sequence": sequence,
                "type": "latent_lab_step",
                "filename": f"prompting_process/{step_filename}",
                "timestamp": datetime.now().isoformat(),
                # `step_index` is the place in the sequence; everything else in
                # here is the instrument's own word about this part.
                "metadata": {"step_index": idx, "format": fmt, **part_meta},
            })

        # 3) Final outputs in final/
        for out in outputs or []:
            media_type = out.get("type", "image")
            fmt = out.get("format", "png")
            out_meta = dict(out.get("meta") or {})
            sequence += 1
            out_filename = f"{sequence:02d}_output_{media_type}.{fmt}"
            try:
                raw = self._output_bytes(out, media_type)
                # Bytes that came through a `ref` are taken EXACTLY as they lie.
                # They were marked when they were first written, and marking
                # them again would put a second disclosure into the file: the
                # copy would then differ from the picture the address it came
                # from still hands out, and the two could no longer be compared.
                if not out.get("ref"):
                    raw = _marked(
                        raw,
                        f"output_{media_type}",
                        {"format": fmt, **_disclosed(parameters, results)},
                    )
                (final_folder / out_filename).write_bytes(raw)
            except Exception as e:
                logger.warning(f"[LAB_RECORDER] Output of {run_id} not written: {e}")
                continue

            metadata["entities"].append({
                "sequence": sequence,
                "type": f"output_{media_type}",
                "filename": out_filename,
                "timestamp": datetime.now().isoformat(),
                "metadata": {"format": fmt, **out_meta},
            })

        metadata["total_entities"] = len(metadata["entities"])
        # Written beside it and moved into place, as _amend_entity_meta and
        # the pipeline and canvas recorders do: the run folder is made at the
        # start of this method, so a reader listing runs can arrive while the
        # record is being written, and finds it whole or not at all.
        metadata_path = run_folder / "metadata.json"
        tmp = metadata_path.with_name(f"{metadata_path.name}.{uuid.uuid4().hex}.tmp")
        try:
            tmp.write_text(
                json.dumps(metadata, indent=2, ensure_ascii=False),
                encoding='utf-8',
            )
            os.replace(str(tmp), str(metadata_path))
        except BaseException:
            # BaseException, not only Exception: whatever exception ends the
            # write, the temporary file does not stay behind.
            try:
                tmp.unlink()
            except OSError:
                pass
            raise

        logger.info(
            f"[LAB_RECORDER] {self.latent_lab_tool} run {run_id} "
            f"({len(steps or [])} parts, {len(outputs or [])} outputs)"
        )
        return {
            "run_id": run_id,
            "entity_count": len(metadata["entities"]),
            "entities": metadata["entities"],
            # What was just written, for a caller that answers the run in the
            # same request (services/denoising_archaeology_record.py builds
            # the instrument object from these through instrument_from_metadata
            # and spares the store the search that load_recorder makes).
            "metadata": metadata,
            "run_folder": str(run_folder),
        }

    @staticmethod
    def _output_bytes(out: Dict[str, Any], media_type: str) -> bytes:
        """The bytes of ONE output, whether they came as base64 or as a reference.

        A reference is the address of one output of one run and nothing else,
        and the shape is checked HERE, before any file is opened. The route that
        carries a `ref` into this recorder (POST /api/latent-lab/record) is open
        to any client, and `resolve_media_ref` accepts far more than a run
        address: its FIRST branch returns any existing filesystem path, and it
        also takes upload ids and bare ids. Handing it whatever arrived would
        let a caller name a file anywhere this process can read and have it
        copied into a run folder, from where the media routes serve it.

        What is accepted is resolved through the platform's single resolver, so
        the file that is read is the very one the address hands out. Everything
        either step refuses raises, and the caller drops that output the way it
        drops undecodable base64: one output must never cost the run.
        """
        ref = out.get("ref")
        if ref:
            from my_app.utils.media_ref import resolve_media_ref

            address = str(ref).strip()
            if not _RUN_REF_RE.match(address):
                raise ValueError(f"{address[:160]!r} is no run address")
            kind = media_type if media_type in ("image", "audio", "video", "3d") else "image"
            return Path(resolve_media_ref(address, kind=kind)).read_bytes()
        return base64.b64decode(out["dataBase64"])

    def complete(self) -> None:
        """The sitting is over. Its runs are already on disk, each one complete."""
        logger.info(
            f"[LAB_RECORDER] Session {self.session_id} closed "
            f"after {self.generation} run(s)"
        )


# ---------------------------------------------------------------------------
# Rewriting the plate a run is SHOWN by
# ---------------------------------------------------------------------------

#: How much base64 this will take for one plate. A 1024 x 1024 PNG is around
#: 3 MB encoded; four times a 4K plate is past anything a surface composes.
MAX_PLATE_BASE64 = 32 * 1024 * 1024

#: The instruments that lay a PLATE — a picture that is the instrument's own
#: reading of a run rather than something the model made, and that may therefore
#: be set again when the reading changes. The mark `plate: "reading"` is written
#: by the browser, so on its own it is a claim, not a fact: without this list any
#: run recorded through this module could be made overwritable by asking for it.
PLATE_TOOLS = ("attention_cartography",)

#: One writer at a time per run. The server is threaded, and setting a plate is
#: two writes — the picture and the record of what it says. Two stars racing
#: would otherwise interleave them and leave a picture captioned by the other
#: one's reading, with the attention maps gone and no way to notice.
_plate_locks: Dict[str, threading.Lock] = {}
_plate_locks_guard = threading.Lock()


def _plate_lock(run_id: str) -> threading.Lock:
    with _plate_locks_guard:
        lock = _plate_locks.get(run_id)
        if lock is None:
            lock = threading.Lock()
            _plate_locks[run_id] = lock
        return lock


def _readable_plates(entities: List[Any]) -> List[Any]:
    """The image outputs of a run, in the order the media routes number them.

    `/api/media/image/<run>/<i>` resolves i against entities sorted by
    `sequence` (media_routes._find_entities_by_type). Counting them in list
    order here instead would let this write to one file while the URL that is
    then handed out addresses another.
    """
    images = [
        e for e in entities
        if isinstance(e, dict) and e.get("type") == "output_image"
    ]
    images.sort(key=lambda e: e.get("sequence", (e.get("metadata") or {}).get("file_index", 0)))
    return images


def replace_output_image(
    run_id: str,
    index: int,
    data_base64: str,
    device_id: str = "",
    reading: Optional[Dict[str, Any]] = None,
    base_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Put another picture in the place of a run's Nth image output.

    ONLY for a picture that is a READING and says so. Attention Cartography
    shows a map over its render, and which map that is depends on the words, the
    depth and the step the surface stands at; the plate the run is shown by has
    to be able to follow that. Everything else stays untouchable, and that is
    what the three gates below are for:

      * the run is a Latent Lab run of an instrument that lays plates at all
        (`PLATE_TOOLS`) — `output_image` is what the WHOLE platform names its
        pictures, so without this any workshop's artwork would be one POST away
        from being overwritten, and its run folder holds the only copy;
      * the output carries `plate: "reading"`, written when it was recorded, so
        the model's own render beside it can never be the one replaced;
      * the run was made on the device now asking, by the same rule the sitting
        listing goes by;
      * the bytes are a picture of the format the record names — the recorded
        `format` stays true, and a file the marking service cannot classify is
        never written in place of one it marked.

    `reading` is what the plate SAYS — which words, through which encoders, at
    which depth and step, at what strength, over which ground. It is written
    with the picture, because a heat map whose reading is unrecorded cannot be
    interpreted six months later, and the plate on disk is the only thing left
    of it. It goes onto the entry through `_amend_entity_meta`, which reads the
    metadata file from DISK: `recorder.metadata` has pipeline-shaped fields
    filled into it by `load_recorder` where they are absent (`current_state`,
    `expected_outputs`), and saving that object would make those invented facts
    permanent in the research record.

    Picture and record are set as one: the previous bytes are kept until the
    reading is written beside them, and go back if it cannot be. A plate whose
    record says something else is worse than no plate, because nothing can tell
    afterwards which of the two is the lie.

    Returns {"ok": True, "version": int} — the modification time in
    MICROSECONDS, which a URL carries so that a picture answered as `immutable`
    can still change. Microseconds, not nanoseconds: the number travels through
    JSON into a browser, where every number is a double, and a nanosecond stamp
    of this era needs 61 bits — the browser rounds it and then addresses the
    same file under a different name than the server does. A microsecond stamp
    needs 51 and stays exact on both sides; two writes cannot fall inside one. On refusal {"ok": False, "reason": str}; the reason is what
    the route turns into a status, so a bad payload is never reported as a
    missing run.
    """
    from my_app.services.pipeline_recorder import load_recorder

    if not isinstance(data_base64, str) or not data_base64:
        return {"ok": False, "reason": "no_picture"}
    if len(data_base64) > MAX_PLATE_BASE64:
        return {"ok": False, "reason": "too_large"}

    if base_path is None:
        from config import JSON_STORAGE_DIR
        base_path = JSON_STORAGE_DIR

    recorder = load_recorder(run_id, base_path=Path(base_path))
    if not recorder:
        return {"ok": False, "reason": "no_run"}

    metadata = recorder.metadata or {}
    if metadata.get("type") != "latent_lab" or metadata.get("latent_lab_tool") not in PLATE_TOOLS:
        return {"ok": False, "reason": "not_a_lab_run"}

    entities = metadata.get("entities")
    if not isinstance(entities, list):
        return {"ok": False, "reason": "no_such_output"}

    images = _readable_plates(entities)
    if index < 0 or index >= len(images):
        return {"ok": False, "reason": "no_such_output"}
    entity = images[index]

    entity_meta = dict(entity.get("metadata") or {})
    if entity_meta.get("plate") != "reading":
        return {"ok": False, "reason": "not_a_reading"}

    recorded_device = str(metadata.get("device_id") or "")
    if not device_id or not recorded_device or not _same_device(recorded_device, device_id):
        return {"ok": False, "reason": "other_device"}

    filename = str(entity.get("filename") or "")
    # The name comes out of our own record, and it stays a name: a filename
    # carrying a path would write outside the run's own folder.
    if not filename or Path(filename).name != filename:
        logger.warning(f"[LAB_RECORDER] {run_id} output {index} has no plain filename")
        return {"ok": False, "reason": "no_such_output"}

    try:
        raw = base64.b64decode(data_base64, validate=True)
    except Exception as e:
        logger.warning(f"[LAB_RECORDER] New plate for {run_id} unreadable: {e}")
        return {"ok": False, "reason": "no_picture"}
    if not raw:
        return {"ok": False, "reason": "no_picture"}
    recorded_format = str(entity_meta.get("format") or "png").lower()
    if _sniff_format(raw) != recorded_format:
        # The file keeps the name and the format the record gives it. Writing
        # other bytes under it would leave `metadata.json` describing something
        # that is not there, and the marking service classifies BY content — so
        # what it cannot name, it hands back unmarked (watermark_service).
        logger.warning(f"[LAB_RECORDER] New plate for {run_id} is not {recorded_format}")
        return {"ok": False, "reason": "no_picture"}

    # From wherever the run keeps them. The one field the reading plates of
    # this store actually carry is the seed: of the 25 stored Attention-
    # Cartography runs — the only tool this route admits — none names a model in
    # its parameters, 21 name their seed at the top level of the record and 3
    # more in their own parameters file. Read the same way as in `record`, so a
    # re-set plate and the picture it replaces name their seed by the same rule.
    # The blocks they read it from differ: `record` has the run in hand, and a
    # plate is re-set long after, from whatever the record kept — for 3 of the
    # 25 that is the run's own parameters file, and for the one folder holding
    # several generations it is nothing at all.
    parameters, results = recovered_run_data(metadata, recorder.final_folder)
    raw = _marked(raw, "output_image",
                  {"format": entity_meta.get("format", "png"), **_disclosed(parameters, results)})

    path = recorder.final_folder / filename
    # A name of this call's own, not of this process's: the server is threaded
    # (waitress), so two requests for one run would otherwise write the same
    # temporary file and promote a mixture of the two.
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    with _plate_lock(run_id):
        try:
            previous = path.read_bytes() if path.exists() else None
        except OSError:
            previous = None
        try:
            tmp.write_bytes(raw)
            os.replace(str(tmp), str(path))
        except OSError as e:
            logger.error(f"[LAB_RECORDER] Could not write {path.name} of {run_id}: {e}")
            try:
                tmp.unlink()
            except OSError:
                pass
            return {"ok": False, "reason": "write_failed"}

        if reading is not None and not _amend_entity_meta(
            recorder.run_folder, filename, {"reading": reading}
        ):
            # The picture goes back. What a heat map SHOWS is only knowable from
            # what it says it shows, so a picture that outran its own record is
            # not a lesser success — it is a run nobody can read afterwards.
            if previous is not None:
                back = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
                try:
                    back.write_bytes(previous)
                    os.replace(str(back), str(path))
                except OSError as e:
                    logger.error(f"[LAB_RECORDER] {run_id} left unrepaired: {e}")
            return {"ok": False, "reason": "record_write_failed"}

        # The reader cache holds this run's metadata for the life of the process
        # (pipeline_recorder._active_recorders), so without this every route
        # that goes through `load_recorder` — the run itself, the favourites,
        # Resona's view of it — would answer with the reading it had before.
        # Worse, a later save of that stale object would put it back on disk.
        try:
            from my_app.services import pipeline_recorder as _pr
            _pr._active_recorders.pop(run_id, None)
        except Exception:
            pass

        # And the miniatures were built from the old bytes. They are answered as
        # `immutable` for a year, and their own freshness check compares
        # modification times, which a losing race can invert (services.thumbnails).
        try:
            from my_app.services.thumbnails import drop_cached
            drop_cached(f"{run_id}_{index}")
        except Exception:
            pass

        # In microseconds, not seconds: a plate set twice inside one second
        # would otherwise keep its URL, and a miniature answered as `immutable`
        # would go on showing the earlier one. See the docstring on why not
        # nanoseconds.
        try:
            return {"ok": True, "version": path.stat().st_mtime_ns // 1000}
        except OSError:
            return {"ok": True, "version": time.time_ns() // 1000}


#: The first bytes of the picture formats this platform records, in the spelling
#: `metadata.json` uses for them.
_MAGIC = (
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpg"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
)


def _sniff_format(raw: bytes) -> str:
    """What these bytes ARE, read off their head rather than off a claim."""
    for magic, name in _MAGIC:
        if raw.startswith(magic):
            return name
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "webp"
    return ""


def name_plate(entity_metadata: Optional[Dict[str, Any]]) -> str:
    """How to NAME a picture that is a plate, for anyone reading a run back.

    A Latent Lab run is shown by the instrument's own reading — a heat map, a
    difference, a trace drawn over the render. Handing that to a vision channel
    under the words "the rendered image" would report it as something the model
    made, and every account built on it would be wrong about its subject. So
    whoever reads a run asks here what it is looking at.

    Two kinds of plate stand under `plate`, and they are different pictures:

      * "reading"   — the instrument's own reading laid over the render it was
        read from, the shape Attention Cartography lays;
      * "composite" — a picture the instrument computed out of several renders,
        the shape Mean Images lays: a mean, a relief, a contact sheet.

    Any other truthy value is named as a reading, which is what a plate written
    before the composite existed is. What stands under `reading` is appended to
    either as `(key: value, …)`.

    Empty string where the picture is an ordinary render; the caller then uses
    its own wording.
    """
    meta = entity_metadata or {}
    plate = meta.get("plate")
    if not plate:
        return ""
    reading = meta.get("reading") or {}
    terms = ", ".join(
        f"{key}: {value}" for key, value in reading.items()
        if value not in (None, "", [], {})
    )
    what = (
        "a picture the instrument computed from several renders"
        if plate == "composite"
        else "the instrument's own reading, laid over the picture it was read from"
    )
    return f"{what} ({terms})" if terms else what


def _amend_entity_meta(run_folder: Path, filename: str, fields: Dict[str, Any]) -> bool:
    """Add fields to one entity's own `metadata`, in the file as it lies on disk.

    Read from disk on purpose. The recorder object in memory may carry fields
    `load_recorder` invented for readers that expect a pipeline run, and writing
    that object out would put those into the research record for good. What is
    written here is the file plus the named fields on the named entry, nothing
    else, and the write is atomic so a reader is never handed half a record.
    """
    path = run_folder / "metadata.json"
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
        entities = stored.get("entities")
        if not isinstance(entities, list):
            return False
        for entity in entities:
            if isinstance(entity, dict) and entity.get("filename") == filename:
                meta = entity.get("metadata")
                entity["metadata"] = {**(meta if isinstance(meta, dict) else {}), **fields}
                break
        else:
            return False
        tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
        tmp.write_text(json.dumps(stored, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(str(tmp), str(path))
        return True
    except (OSError, ValueError) as e:
        # The picture is already set; the run keeps the reading it was written
        # with rather than losing the record altogether.
        logger.warning(f"[LAB_RECORDER] Reading of {run_folder.name} not amended: {e}")
        return False


# ---------------------------------------------------------------------------
# Reading a run back — the instrument object
# ---------------------------------------------------------------------------

def build_instrument_object(run_id: str, base_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """The whole of one run, in the shape the instrument that made it can take back.

    THE one place that reads this layout: the Ablage's restore route serves it
    to whichever instrument made the run, and the run route serves it directly.
    Neither of them knows what a part MEANS — that is the instrument's own
    business, and it travels in each part's `meta`.

    Returns None when the run is not a Latent Lab run (or does not exist), so
    callers can fall through to their own shape.
    """
    from my_app.services.pipeline_recorder import load_recorder

    if base_path is None:
        from config import JSON_STORAGE_DIR
        base_path = JSON_STORAGE_DIR

    recorder = load_recorder(run_id, base_path=Path(base_path))
    if not recorder:
        return None

    return instrument_from_metadata(run_id, recorder.metadata or {}, recorder.final_folder)


def _disclosed(
    parameters: Optional[Dict[str, Any]],
    results: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """The fields of the AI-Origin Disclosure that come from the run itself.

    The seed is the one that MADE the picture, which the run reports back as its
    result; what stands in `parameters` is what was ASKED FOR, and the two part
    company wherever the service drew the number itself. Where a surface keeps
    -1 in its seed field to have it drawn, that -1 is recorded as the parameter:
    34 stored runs carry it as their parameters are read here — 24 of the
    Crossmodal Lab, 3 each of the Arcimboldo Mosaic and the Latent Text Lab, 2
    each of Attention Cartography and the Denoising Archaeology — and disclosing
    it would name a seed no picture was made with. It is refused from either
    side; no stored run has ever recorded a negative result.

    The blocks arrive here straight from the route in one of the two callers, so
    neither is trusted to be an object: a disclosure is worth less than the
    pictures of the run, and raising here would cost them.
    """
    asked = parameters if isinstance(parameters, dict) else {}
    produced = results if isinstance(results, dict) else {}
    fields = {k: v for k, v in asked.items() if k in ("model", "model_name")}
    for candidate in (produced.get("seed"), asked.get("seed")):
        # `isinstance(True, int)` holds in Python, and True is no seed.
        if isinstance(candidate, int) and not isinstance(candidate, bool) and candidate != -1:
            fields["seed"] = candidate
            break
    return fields


def recovered_run_data(
    metadata: Any,
    final_folder: Optional[Path] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """What a Latent Lab run was made with, and what came of it.

    The parameters stand at the top level of the record for every run written
    since a491f92f, the results wherever the caller supplied any — 40 runs of
    Mean Images and of the Fusion Workbench, all after that commit, keep none.
    Before it both were written only into the run's own
    `prompting_process/001_parameters.json`, in the same call as the record.
    Of the 442 stored runs, 98 hold several generations and are refused below;
    of the remaining ones 139 are missing a block, 137 have that file, and 95
    get their results back with it — and with the results the seed for 83 of
    them, the total step count for 20 and the order of the scheduler for 4.
    Read only from the top level, a surface restoring such a run shows nothing
    of it and fills the fields from whatever happens to stand on it.

    One direct read, no search of the store and no folder made while merely
    reading: the run's folder is handed in. Where it is not, the run's own
    params entity still carries the parameters, the same dict the writer puts in
    both places.
    """
    if not isinstance(metadata, dict):
        return {}, {}

    parameters = metadata.get("parameters") or {}
    results = metadata.get("results") or {}
    # Both are handed on to callers that index them. A record whose blocks are
    # not objects has nothing to hand on.
    if not isinstance(parameters, dict):
        parameters = {}
    if not isinstance(results, dict):
        results = {}
    if parameters and results:
        return parameters, results

    # A folder from before the split holds a whole SITTING: several parameter
    # blocks, one per generation, and `001_parameters.json` is the FIRST one.
    # 98 of the 442 stored folders are of that kind, and 22 of them hold several
    # pictures — handing out generation 1's prompt and seed for a picture from
    # generation 5 would state something false about that picture. Nothing is
    # read for such a folder; what the record itself holds is handed on as it
    # always was. `instrument_from_metadata` refuses these folders outright, the
    # two other callers do not, so the reading stops here.
    entities = metadata.get("entities")
    blocks = sum(
        1 for e in (entities if isinstance(entities, list) else [])
        if isinstance(e, dict) and e.get("type") == "latent_lab_params"
    )
    if blocks > 1:
        return parameters, results

    if final_folder is not None:
        try:
            kept = json.loads(
                (final_folder.parent / "prompting_process" / "001_parameters.json")
                .read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            kept = None
        if isinstance(kept, dict):
            if not parameters and isinstance(kept.get("parameters"), dict):
                parameters = kept["parameters"]
            if not results and isinstance(kept.get("results"), dict):
                results = kept["results"]

    if not parameters:
        for ent in entities if isinstance(entities, list) else []:
            if isinstance(ent, dict) and ent.get("type") == "latent_lab_params":
                fallback = ent.get("metadata")
                if isinstance(fallback, dict):
                    parameters = fallback
                break

    return parameters, results


def instrument_from_metadata(
    run_id: str,
    metadata: Any,
    final_folder: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """The same object, built from metadata already in hand.

    Reading a whole sitting means the metadata of every run has just been read
    from disk; going back through `load_recorder` for each of them searched the
    whole store again per run, opened a recorder that stays in memory for the
    life of the process, and created a `final/` folder while merely READING.
    """
    if not isinstance(metadata, dict):
        return None
    if metadata.get("type") != "latent_lab":
        return None

    entities = metadata.get("entities", [])
    if not isinstance(entities, list):
        return None

    # A folder from before the split holds a whole SITTING: several parameter
    # blocks, and the steps of several generations one after another. Handing
    # that out as one run would merge three runs into a single sequence with no
    # parameters at all — better no answer than a made-up one.
    if sum(1 for e in entities if isinstance(e, dict) and e.get("type") == "latent_lab_params") > 1:
        logger.info(f"[LAB_RECORDER] {run_id} is a pre-split sitting, not a run")
        return None

    parts: List[Dict[str, Any]] = []
    outputs: List[Dict[str, Any]] = []
    # The media routes address an output by its place AMONG ITS OWN KIND, and
    # without that number they serve the last one of the kind. A run with a
    # reference image and a result would then offer two URLs for the result.
    per_type: Dict[str, int] = {}
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        entity_type = entity.get("type", "")
        if entity_type == "latent_lab_step":
            parts.append({
                "index": len(parts),
                "kind": "step",
                "url": f"/api/latent-lab/run/{run_id}/part/{len(parts)}",
                "meta": dict(entity.get("metadata") or {}),
            })
        elif is_media_entity(entity_type):
            # `is_media_entity`, not a bare `output_` prefix: a run may also keep
            # its final latent, which is numpy, has no media route, and would
            # otherwise be handed out here as /api/media/latent/<run>/<i> — an
            # address that answers nothing.
            media_type = entity_type[len("output_"):]
            meta = dict(entity.get("metadata") or {})
            index = per_type.get(media_type, 0)
            per_type[media_type] = index + 1
            # The moment the file was last written travels with its URL. A
            # miniature of it is answered as `immutable` (media_routes), and a
            # reading can be set again after the run — without this a strip
            # would go on showing the picture from before it for a year.
            version = ""
            if final_folder is not None:
                try:
                    stamp = (final_folder / str(entity.get("filename") or "")).stat().st_mtime_ns
                    # Microseconds, the same unit `replace_output_image` hands
                    # back — a nanosecond stamp is rounded by the browser, and
                    # one file would carry two names across the surfaces.
                    version = f"?v={stamp // 1000}"
                except (OSError, TypeError, ValueError):
                    version = ""
            outputs.append({
                "type": media_type,
                "format": meta.get("format", ""),
                "url": f"/api/media/{media_type}/{run_id}/{index}{version}",
                "meta": meta,
            })

    parameters, results = recovered_run_data(metadata, final_folder)

    return {
        "run_id": run_id,
        "tool": metadata.get("latent_lab_tool", ""),
        "session_id": metadata.get("session_id", ""),
        "generation": metadata.get("generation", 0),
        "timestamp": metadata.get("timestamp", ""),
        "parameters": parameters,
        "results": results,
        "parts": parts,
        "outputs": outputs,
    }


def _session_days(session_id: str) -> List[str]:
    """The date folders a sitting's runs can lie in.

    A sitting's id carries the moment it was opened (`lab_<milliseconds>_<hex>`),
    and a run lies in the folder of the day it was MADE. A tab is not closed at
    midnight — it stays open over a night, a weekend, a holiday — so the days
    searched run from the day the sitting was opened up to today. Counted in
    CALENDAR days, not in 86400-second steps: on the night the clocks go
    forward, a day added in seconds skips the day after it entirely.

    Where the id says nothing about a moment, today and yesterday are searched.
    """
    today = datetime.now().date()
    try:
        opened = datetime.fromtimestamp(int(session_id.split('_')[1]) / 1000).date()
    except (IndexError, ValueError, OSError, OverflowError):
        opened = today - timedelta(days=1)
    # A sitting that claims to be older than the cap, or to lie in the future,
    # is not a sitting this tab can still be in.
    if not (today - timedelta(days=_SESSION_DAYS_MAX) <= opened <= today):
        opened = today - timedelta(days=1)
    span = (today - opened).days
    return [(opened + timedelta(days=n)).strftime('%Y-%m-%d') for n in range(span + 1)]


#: How far back a sitting id is still taken seriously. A browser tab open for
#: longer than this is not the same sitting in any sense the surface cares about.
_SESSION_DAYS_MAX = 31

_DATED_DEVICE = re.compile(r'^(?P<browser>.+)_\d{4}-\d{2}-\d{2}$')


def _same_device(folder_name: str, device_id: str) -> bool:
    """Whether a device folder belongs to the browser now asking.

    A device id carries the date it was made on (`<browser>_<YYYY-MM-DD>`, see
    the frontend's `useDeviceId` — a shared classroom tablet gets a new identity
    each day). A sitting opened before midnight therefore lies in YESTERDAY's
    folder while the browser already calls itself by today's date, and a folder
    compared whole would never match. What identifies the device is the part in
    front of the date; where there is no date, the whole name is that part.
    """
    def browser_part(name: str) -> str:
        dated = _DATED_DEVICE.match(name)
        return dated.group('browser') if dated else name

    return browser_part(folder_name) == browser_part(device_id)


def list_session_runs(
    session_id: str,
    device_id: Optional[str] = None,
    base_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Every run of one sitting, in the order it was made.

    The runs of a sitting were reachable one by one and never together: each one
    carries its `session_id`, and nothing asked for it. A surface that shows its
    runs kept them in the browser, so a reload emptied the surface while every
    run of it lay complete on disk.

    Each run comes back as the same instrument object a single run does — one
    reader for the layout, one shape for the surfaces.
    """
    if base_path is None:
        from config import JSON_STORAGE_DIR
        base_path = JSON_STORAGE_DIR
    base_path = Path(base_path)

    runs: List[Dict[str, Any]] = []
    for day in _session_days(session_id):
        day_folder = base_path / day
        try:
            if not day_folder.is_dir():
                continue
            if device_id:
                device_folders = [
                    d for d in day_folder.iterdir() if d.is_dir() and _same_device(d.name, device_id)
                ]
            else:
                device_folders = [d for d in day_folder.iterdir() if d.is_dir()]
        except OSError:
            # A day that cannot be read leaves the other days of the sitting
            # standing; it must not take the whole listing down with it.
            logger.warning(f"[LAB_RECORDER] Day folder unreadable: {day}")
            continue
        for device_folder in device_folders:
            try:
                run_folders = sorted(device_folder.glob('run_*'))
            except OSError:
                continue
            for run_folder in run_folders:
                metadata_path = run_folder / 'metadata.json'
                try:
                    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
                except (OSError, ValueError):
                    continue
                if not isinstance(metadata, dict):
                    continue
                if metadata.get('type') != 'latent_lab':
                    continue
                if metadata.get('session_id') != session_id:
                    continue
                run = instrument_from_metadata(
                    metadata.get('run_id') or run_folder.name, metadata, run_folder / "final"
                )
                if run:
                    runs.append(run)

    runs.sort(key=lambda r: r.get('generation') or 0)
    return runs


def resolve_part_path(run_id: str, index: int, base_path: Optional[Path] = None) -> Optional[Path]:
    """The file of one part, or None.

    The path is built from the run's own metadata and then checked to lie inside
    that run's folder: the index comes off a URL, and a filename read from disk
    is still a filename somebody could have written.
    """
    from my_app.services.pipeline_recorder import load_recorder

    if base_path is None:
        from config import JSON_STORAGE_DIR
        base_path = JSON_STORAGE_DIR

    recorder = load_recorder(run_id, base_path=Path(base_path))
    if not recorder or (recorder.metadata or {}).get("type") != "latent_lab":
        return None

    steps = [
        e for e in (recorder.metadata or {}).get("entities", [])
        if e.get("type") == "latent_lab_step"
    ]
    if index < 0 or index >= len(steps):
        return None

    run_folder = Path(recorder.run_folder).resolve()
    candidate = (run_folder / steps[index].get("filename", "")).resolve()
    if run_folder != candidate.parent and run_folder not in candidate.parents:
        logger.warning(f"[LAB_RECORDER] Part {index} of {run_id} points outside its run folder")
        return None
    return candidate if candidate.exists() else None


# ---------------------------------------------------------------------------
# Run ID generation (same pattern as pipeline_recorder.py)
# ---------------------------------------------------------------------------

def generate_run_id() -> str:
    """Chronologically sortable run ID."""
    return f"run_{int(time.time() * 1000)}_{os.urandom(3).hex()}"


# ---------------------------------------------------------------------------
# Active recorder registry — one entry per open instrument
# ---------------------------------------------------------------------------

_active_recorders: Dict[str, LatentLabRecorder] = {}


def get_lab_recorder(session_id: str) -> Optional[LatentLabRecorder]:
    """Get an open sitting by its session id."""
    return _active_recorders.get(session_id)


def create_lab_recorder(
    latent_lab_tool: str,
    device_id: Optional[str] = None,
    user_id: str = "anonymous",
) -> LatentLabRecorder:
    """Open a sitting and register it. No folder is written until a run is."""
    session_id = f"lab_{int(time.time() * 1000)}_{os.urandom(3).hex()}"
    recorder = LatentLabRecorder(
        session_id=session_id,
        latent_lab_tool=latent_lab_tool,
        device_id=device_id,
        user_id=user_id,
    )
    _active_recorders[session_id] = recorder
    return recorder


def cleanup_lab_recorder(session_id: str) -> None:
    """Remove a sitting from the registry."""
    if session_id in _active_recorders:
        del _active_recorders[session_id]
        logger.info(f"[LAB_RECORDER] Cleaned up session {session_id}")
