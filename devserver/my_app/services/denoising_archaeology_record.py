"""
The Denoising Archaeology's run, written into the platform's storage by the
server that answers it.

Until 2026-09-22 the surface wrote this record itself. The direct endpoint
answered with the step frames (25 by default) and the finished picture as
base64, the surface showed them, and then it sent the same bytes back up as the
run's record. The frames and the picture of a 25-step run are 18 MB (SDXL) to
23 MB (SD 3.5) as files, 25 MB and 31 MB as base64 in the answer, and the same
again on the way up. Measured on 2026-09-22 on lab6000, from the backend's
journal (two runs at 25 steps, SD 3.5 and SDXL): 45 s and 34 s for the answer,
79 s and 64.5 s for the record, while the frames and the axis stood on the
surface for the whole second stretch under a line saying "Waiting for
transfer". The server's own share of the record is small: from the first part
file to metadata.json, by the files' mtimes, 0.151 s (SD 3.5) and 0.127 s
(SDXL); that span holds the decoding and the AI-origin marking of the frames
and leaves out Flask's parse of the body.

Now the surface names its open sitting in the request (`record`), the endpoint
writes the run into it here, through the same recorder and with the same
parameters, results, parts and output the surface used to send, and answers
with the run as the storage hands it back (`instrument_from_metadata`), whose
parts are addresses. The Mean Images instrument writes its cells this way
since 2026-09-04 (routes/mean_images_routes.py, `_record_cell`); what is new
here is that the answer carries the stored run's object in place of the bytes.

A request without `record`, a `record` this module cannot use, a sitting the
server does not know, or a write that fails leaves the endpoint on its old
answer: the bytes travel, and the surface records them as before. Every
refusal is logged with what was seen and returned as a word, so the route can
tell the surface.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

#: The instrument whose sittings this module writes into.
TOOL = 'denoising_archaeology'


def step_of_capture(capture_index: int, scheduler_order: int) -> Dict[str, Any]:
    """Which step of the RUN a captured frame belongs to.

    A first-order method asks the net once per step, so the capture index is
    the step. A second-order method asks twice per step, and the captures come
    in pairs: (0,1) is step 1, (2,3) is step 2, and the last step has no
    partner. This is the surface's own rule (`stepOfCapture` in
    views/latent_lab/denoising_archaeology.vue), written into each part's
    `meta` so that a restore reads it off the part; the surface keeps its copy
    for parts recorded before the number travelled with them.
    """
    if scheduler_order < 2:
        return {'step': capture_index + 1, 'second': False}
    return {'step': capture_index // 2 + 1, 'second': capture_index % 2 == 1}


def _read_record(raw: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """What the surface says about its sitting and its own settings, checked
    field by field.

    Returns the checked record and None, or None and the word for the refusal.
    A run recorded with a wrong seed field is worse than one the surface
    records itself, so every field is checked and every refusal is logged
    with what arrived.
    """
    if not isinstance(raw, dict):
        logger.warning(
            "[ARCHAEOLOGY-RECORD] record is not an object (%s); not recorded here",
            type(raw).__name__,
        )
        return None, 'record_malformed'

    session_id = raw.get('session_id')
    if not isinstance(session_id, str) or not session_id.strip():
        logger.warning("[ARCHAEOLOGY-RECORD] record carries no session_id; not recorded here")
        return None, 'no_session_id'

    device_id = raw.get('device_id')
    if not isinstance(device_id, str) or not device_id.strip():
        logger.warning("[ARCHAEOLOGY-RECORD] record carries no device_id; not recorded here")
        return None, 'no_device_id'

    # The seed that went out, and the tick that says whether it was drawn
    # regardless of what changed. Both are the surface's: since 2026-10-03 its
    # seed automatic decides the seed and writes it into the field before the
    # run is sent (composables/useSeedAutomatic.ts). Before, this was the field
    # as it stood, null for a field that held no whole number, and under the
    # tick a number the run did not use.
    seed = raw.get('seed')
    if isinstance(seed, bool) or not isinstance(seed, (int, type(None))):
        logger.warning(
            "[ARCHAEOLOGY-RECORD] record carries a seed that is no whole number (%r); "
            "not recorded here", seed,
        )
        return None, 'seed_not_a_whole_number'
    random_seed = raw.get('random_seed')
    if not isinstance(random_seed, bool):
        logger.warning(
            "[ARCHAEOLOGY-RECORD] record carries no random_seed tick (%r); not recorded here",
            random_seed,
        )
        return None, 'random_seed_not_a_tick'

    return {
        'session_id': session_id.strip(),
        'device_id': device_id.strip(),
        'seed': seed,
        'random_seed': random_seed,
    }, None


def _parts_of(archaeology_data: Dict[str, Any], scheduler_order: int) -> List[Dict[str, Any]]:
    """The captured frames as the recorder takes them: bytes and, per part, the
    step of the run it belongs to.

    The index is the one the SERVICE counted (`step` on each capture), because
    a capture that fails is logged and left out, and then a frame's place in
    the list is no longer its place in the run. A capture that names no index
    is counted by its place, which is all there is to count it by.
    """
    parts: List[Dict[str, Any]] = []
    for position, capture in enumerate(archaeology_data.get('step_images') or []):
        if not isinstance(capture, dict):
            continue
        data = capture.get('image_base64')
        if not isinstance(data, str) or not data:
            continue
        index = capture.get('step')
        if isinstance(index, bool) or not isinstance(index, int):
            index = position
        parts.append({
            'format': 'jpg',
            'dataBase64': data,
            'meta': step_of_capture(index, scheduler_order),
        })
    return parts


def record_archaeology_run(
    raw_record: Any,
    *,
    prompt: str,
    negative_prompt: Any,
    steps: Any,
    cfg: Any,
    output_config: str,
    pipeline_run_id: str,
    result_seed: Any,
    archaeology_data: Dict[str, Any],
    image_base64: Optional[str],
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Write the run into the sitting the surface named, and hand back the run
    as the storage hands it back.

    Returns `(instrument, None)` when the run was written here, `(None, None)`
    when the request asked for no record, and `(None, word)` when it asked and
    was refused; the word names the refusal for the surface.

    `prompt`, `negative_prompt`, `steps` and `cfg` are what the request carried;
    `pipeline_run_id` is the direct run this generation is the other half of;
    `result_seed` is the seed the direct endpoint reports in `media_output`,
    read where the chunk reports none of its own. The record written here has
    the fields the surface wrote until 2026-09-22, under the same names.
    """
    if raw_record is None:
        return None, None
    record, refusal = _read_record(raw_record)
    if record is None:
        return None, refusal

    from my_app.services.latent_lab_recorder import get_lab_recorder, instrument_from_metadata

    recorder = get_lab_recorder(record['session_id'])
    if recorder is None:
        logger.warning(
            "[ARCHAEOLOGY-RECORD] no open sitting %s; the surface records the run itself",
            record['session_id'],
        )
        return None, 'no_open_sitting'
    if recorder.latent_lab_tool != TOOL:
        logger.warning(
            "[ARCHAEOLOGY-RECORD] sitting %s belongs to %s; not recorded here",
            record['session_id'], recorder.latent_lab_tool,
        )
        return None, 'sitting_of_another_instrument'
    if recorder.device_id != record['device_id']:
        logger.warning(
            "[ARCHAEOLOGY-RECORD] sitting %s belongs to another device; not recorded here",
            record['session_id'],
        )
        return None, 'sitting_of_another_device'

    # Which net ran, in the chunk's own report (both archaeology chunks name
    # it): the restore chooses the net by this word.
    backbone = archaeology_data.get('backbone')
    if not isinstance(backbone, str) or not backbone:
        logger.warning("[ARCHAEOLOGY-RECORD] the chunk names no backbone; not recorded here")
        return None, 'backbone_unnamed'

    order = archaeology_data.get('scheduler_order')
    if isinstance(order, bool) or not isinstance(order, int) or order < 1:
        order = 1
    total_steps = archaeology_data.get('total_steps') or steps

    # The seed that MADE the picture: what the chunk reports, or what the
    # endpoint reports for the run, and nothing where neither names one. Seed 0
    # is a seed and is kept.
    results: Dict[str, Any] = {
        'total_steps': total_steps,
        'scheduler_order': order,
    }
    scheduler = archaeology_data.get('scheduler')
    if scheduler is not None:
        results['scheduler'] = scheduler
    for candidate in (archaeology_data.get('seed'), result_seed):
        if isinstance(candidate, int) and not isinstance(candidate, bool):
            results['seed'] = candidate
            break

    parameters = {
        'prompt': prompt,
        'negative_prompt': negative_prompt,
        'steps': steps,
        'cfg': cfg,
        'seed': record['seed'],
        'random_seed': record['random_seed'],
        'backbone': backbone,
        # What ran, and where the other half of this generation lies: the
        # pipeline's own run carries the config, the safety level and the
        # served file.
        'output_config': output_config,
        'pipeline_run_id': pipeline_run_id,
    }
    outputs = (
        [{'type': 'image', 'format': 'png', 'dataBase64': image_base64}]
        if image_base64 else None
    )

    try:
        written = recorder.record(
            parameters=parameters,
            results=results,
            outputs=outputs,
            steps=_parts_of(archaeology_data, order),
        )
        # The object is built from the metadata the recorder has just written,
        # without a search of the store (`load_recorder` globs every date
        # folder and keeps a second recorder in memory for the life of the
        # process).
        instrument = instrument_from_metadata(
            written['run_id'],
            written['metadata'],
            Path(written['run_folder']) / 'final',
        )
    except Exception as e:
        # The picture exists and the answer can still carry it. A record that
        # could not be written costs the surface its round trip; the run is
        # answered either way.
        logger.error("[ARCHAEOLOGY-RECORD] the run was not written: %s", e)
        return None, 'not_written'

    if not instrument:
        logger.error(
            "[ARCHAEOLOGY-RECORD] run %s was written and cannot be read back; "
            "the surface records the run itself", written.get('run_id'),
        )
        return None, 'not_readable'
    return instrument, None
