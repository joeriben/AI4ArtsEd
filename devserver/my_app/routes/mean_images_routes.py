"""
Routes of the Latent Lab instrument "Mean Images".

Two things the surface cannot do for itself:

  POST /api/latent-lab/mean-images/variants
      one English sentence, and n-1 variants of it that say the same thing.

  POST /api/latent-lab/mean-images/overlay
      a set of finished runs, laid over each other: mean, relief, contact sheet.
      Where every run of the set kept its final latent — the two SD 3.5 rows do,
      the ComfyUI rows have no latent path at all — the MEAN is taken before the
      decoder: the latents are averaged and the average is decoded once. The
      answer says which of the two it holds (`mean_kind`), and so does the cell.

The composites come back as base64 PNGs, and where the request carries a
`record` the instrument's recorder (services/latent_lab_recorder.py) also writes
them as a run of their own. `refs` in the answer holds the address each of them
then has inside that run, and the surface hands those addresses back when it
writes the whole raster at the end: a `ref` gives the recorder an address inside
the storage, and the recorder COPIES the bytes into the raster run, so each run
stays complete on its own and the surface is spared holding the pictures and
uploading them again. The single images behind a set are pipeline runs of their
own, and their run ids travel in the recorded run's `results`.
"""

import base64
import logging
import math
from typing import Any, Dict, List, Optional, Sequence

from flask import Blueprint, jsonify, request

from my_app.services import mean_images
from my_app.services.streaming_response import answered_either_way

logger = logging.getLogger(__name__)

mean_images_bp = Blueprint('mean_images', __name__, url_prefix='/api/latent-lab/mean-images')

# What a set may hold. The instrument offers 5, 20 and 50; the ceiling is what
# one press may ask a model for in one axis of one row.
MAX_PER_CELL = 50

# How many runs one overlay may lay over each other. A row holds one axis, and
# an axis holds at most a set.
MAX_RUNS = MAX_PER_CELL


class NotCleared(Exception):
    """A run whose picture the content check has not cleared (yet).

    Told apart from a run that simply keeps no latent, because the two ask for
    different things of the caller: a cell asks again at the next picture for
    this one, and stops asking for the other."""

    def __init__(self, run_id: str, cause: str):
        super().__init__(f"{run_id}: {cause}")
        self.run_id = run_id
        self.cause = cause


class LatentUnreadable(Exception):
    """A run kept a latent and it cannot be used.

    Having none and having a broken one are different states. Having none is
    ordinary — the ComfyUI rows keep none, and no picture made before this
    instrument asked for one has one — and the set is then averaged pixel by
    pixel, which is what it always was. Having one that cannot be read is a
    fault of this platform's own storage, and a fault must not leave as the
    other mean under the name of this one: the run is named and the request
    fails.
    """

    def __init__(self, run_id: str, cause: Any):
        self.run_id = run_id
        self.cause = cause
        super().__init__(f"the latent of run {run_id} could not be read: {cause}")


class CheckDidNotRun(Exception):
    """The image check on the mean could not be carried out at all.

    Distinct from a refusal, which IS an answer. A scratch file that cannot be
    written, or a checker that breaks, leaves this platform without a judgement
    on a picture nobody has looked at — and an absent judgement is never read as
    a pass here.
    """


@mean_images_bp.route('/variants', methods=['POST'])
def variants():
    """
    The English sentence, and n-1 variants of it.

    Request: {"prompt": "...", "n": 5, "enable_streaming": true?}
    Answer:  {"status": "success", "translation_en": "...",
              "variants": ["...", ...],   # n entries, [0] IS the translation
              "shortfall": 0}

    `shortfall` is how many of the asked-for variants the model did not deliver
    as distinct sentences. It is reported and never filled in: a padded list
    would put the same image into the mean twice under a label saying otherwise.

    With "enable_streaming" the answer travels as the platform's SSE stream
    instead of as one JSON body. It is the same run; only its way back is
    different, and it is the way the direct run already takes. A large set is
    collected in ROUNDS and every round is a model call, so this route is
    regularly silent for minutes: measured on 2026-09-04, one press was out for
    21 min 50 s inside a single POST. The edge in front of this server ends a
    request whose origin has sent nothing for about 100 seconds and hands the
    browser a 524 — so that run finished on the server and its variants were
    thrown away.

    The run names no `client_gone` parameter, and that is a decision rather than
    an omission: the rounds it collects ARE the answer, and it saves what it
    made, so a run left by its reader still finishes something. Work that could
    give something back by stopping asks for the signal by declaring the
    parameter; see `streamed_answer`.
    """
    data = request.get_json(silent=True)

    return answered_either_way(data, _run_variants, data,
                               label='MEAN-IMAGES-VARIANTS')


def _run_variants(data: Any):
    """The variants run, and the ``(payload, http_status)`` it answers with.

    Split out of the route so that one run can be answered either way. It must
    not reach for ``request``: everything it needs stands in ``data``, and a
    streamed answer runs this on a thread of its own.
    """
    if not isinstance(data, dict):
        return {'status': 'error', 'error': 'A JSON body is required'}, 400

    prompt = data.get('prompt')
    if not isinstance(prompt, str) or not prompt.strip():
        return {'status': 'error', 'error': 'prompt is required and must carry text'}, 400
    prompt = prompt.strip()

    # A whole number, and nothing that merely converts to one. `int(9.5)` is 9,
    # so a JSON float would silently become a different set size than the one
    # the surface asked for; a bool is an int in Python and is out for the same
    # reason.
    raw_n = data.get('n', 1)
    if isinstance(raw_n, bool) or not isinstance(raw_n, int):
        return {
            'status': 'error',
            'error': f'n must be a whole number, received {raw_n!r}',
        }, 400
    n = raw_n
    if n < 1 or n > MAX_PER_CELL:
        return {
            'status': 'error',
            'error': f'n must lie between 1 and {MAX_PER_CELL}, received {n}',
        }, 400

    from my_app.routes.schema_pipeline_routes import translate_one
    from my_app.routes.chat_routes import call_chat_helper

    try:
        translation = translate_one(prompt, 'en')
    except Exception as exc:
        logger.error(f"[MEAN-IMAGES] translation failed: {exc}")
        return {'status': 'error', 'error': f'Translation failed: {exc}'}, 502
    if not translation:
        return {'status': 'error', 'error': 'Translation came back empty'}, 502

    wanted = n - 1
    if wanted == 0:
        return {
            'status': 'success',
            'translation_en': translation,
            'variants': [translation],
            'shortfall': 0,
        }, 200

    # The variants are collected in ROUNDS. One request for all of a large set
    # asks a chat model for more sentences than its window holds: the array comes
    # back cut off, nothing parses, and the column that varies the text falls to
    # a single picture with the whole set reported as shortfall. Every round
    # carries what the earlier ones wrote, so a round adds to the set.
    #
    # The ceiling on the rounds is what the set needs plus two, so a model that
    # answers a little short of what it was asked for still gets to fill up,
    # while a run stays bounded.
    written: List[str] = []
    rounds = 0
    max_rounds = math.ceil(wanted / mean_images.VARIANTS_PER_CALL) + 2
    while len(written) < wanted and rounds < max_rounds:
        rounds += 1
        asked = min(mean_images.VARIANTS_PER_CALL, wanted - len(written))
        try:
            # No cap on the answer and no read timeout: the list is the whole
            # point of the call, and a cap truncates it mid-sentence.
            result = call_chat_helper(
                mean_images.variants_messages(translation, asked, taken=written),
                temperature=0.9,
                enable_thinking=False,
            )
        except Exception as exc:
            logger.error(f"[MEAN-IMAGES] variants round {rounds} failed: {exc}")
            # What the earlier rounds wrote is a usable set, and the shortfall
            # says how far it falls short. Only a run with nothing at all in hand
            # answers with an error.
            if written:
                break
            return {'status': 'error', 'error': f'The variants call failed: {exc}'}, 502

        content = result.get('content') or ''
        fresh = mean_images.parse_variants(content, translation, asked, taken=written)
        logger.info(f"[MEAN-IMAGES] round {rounds} asked for {asked} and carried {len(fresh)}")

        # A round that brought nothing is asked again. Whichever way it came
        # back empty — a refusal, prose, a list of objects, or twelve sentences
        # this run has already written — the next turn is a fresh draw at a
        # temperature of 0.9 and may well carry a set the last one did not, and
        # ending the whole run on one such answer costs the set the rounds it
        # still had. What bounds the cost is the ceiling above: a model that
        # keeps answering the same thing spends `max_rounds` turns and no more.
        if not fresh:
            logger.warning(f"[MEAN-IMAGES] round {rounds} brought nothing new")
            continue
        written.extend(fresh)

    logger.info(f"[MEAN-IMAGES] {len(written)} of {wanted} variants came back distinct")

    return {
        'status': 'success',
        'translation_en': translation,
        'variants': [translation] + written,
        'shortfall': wanted - len(written),
    }, 200


# The two columns that make a set. The reference column holds a single picture,
# which is a pipeline run of its own and is never composed.
SET_AXES = ('seedFixed', 'promptFixed')


def cell_account(
    model_label: str, axis: str, count: int, seed: Optional[int], translation_en: str,
    mean_kind: str = 'pixel'
) -> str:
    """
    What this cell IS, in one English paragraph.

    It is written into the cell's run as a text output, and `view_run` reads
    every text output of a run aloud. Without it the assistant is handed a grey
    average with no way to tell what was held still and what was moved — and a
    mean image says neither by looking at it.

    `mean_kind` is WHERE the averaging happened. The two are different pictures
    of the same set — a latent mean keeps the local sharpness of a single
    picture, a pixel mean has less than half of it — so a reader who is not told
    which one is in front of them would read the difference as a difference
    between the sets. A set of one is neither and says so.
    """
    one = count == 1
    if one:
        head = "The single picture of this cell."
    elif mean_kind == 'latent':
        head = (f"Mean of {count} pictures, taken before the decoder: "
                f"their latents were averaged and decoded once.")
    else:
        head = f"Mean image of {count} pictures, averaged pixel by pixel."
    if axis == 'seedFixed':
        made = (
            f"{model_label} generated it from an English rewording of one prompt, "
            f"on seed {seed}."
            if one else
            f"{model_label} generated them from {count} English rewordings of one prompt, "
            f"all on seed {seed}."
        )
    else:
        made = (
            f"{model_label} generated it from the prompt as entered, on one random seed."
            if one else
            f"{model_label} generated them from the prompt as entered, each on a "
            f"different random seed."
        )
    # Single typographic quotes, because Help sets this whole account inside
    # double quotes of its own: with double quotes here the line ended `"."`.
    return f'{head} {made} The prompt in English: ‘{translation_en}’.'


def _usable_record(raw: Any) -> Optional[Dict[str, Any]]:
    """
    The `record` block of an overlay request, or None where it cannot be used.

    A malformed block costs the recording and nothing else: the composite is
    what the request is for, and a cell that stands on the surface unrecorded is
    a better answer than no cell at all. Every refusal says what it saw.
    """
    if raw is None:
        return None
    if not isinstance(raw, dict):
        logger.warning(f"[MEAN-IMAGES] record is not an object ({type(raw).__name__}); not recorded")
        return None

    session_id = raw.get('session_id')
    if not isinstance(session_id, str) or not session_id.strip():
        logger.warning("[MEAN-IMAGES] record carries no session_id; not recorded")
        return None

    axis = raw.get('axis')
    if axis not in SET_AXES:
        logger.warning(f"[MEAN-IMAGES] record carries an unknown axis {axis!r}; not recorded")
        return None

    seed = raw.get('seed')
    if isinstance(seed, bool) or not isinstance(seed, (int, type(None))):
        logger.warning(f"[MEAN-IMAGES] record carries a seed that is no whole number ({seed!r}); not recorded")
        return None
    # The axis that HOLDS the seed is about that seed: its account says "all on
    # seed <n>", and the run's parameters are what a later reader compares two
    # cells by. Recorded without it, the cell would claim a held seed and name
    # none. The other axis draws a fresh seed per picture and has none to name.
    if axis == 'seedFixed' and seed is None:
        logger.warning("[MEAN-IMAGES] a held seed is missing; not recorded")
        return None

    return {
        'session_id': session_id.strip(),
        'model': str(raw.get('model') or ''),
        'model_label': str(raw.get('model_label') or raw.get('model') or 'The model'),
        'axis': axis,
        'seed': seed,
        'translation_en': str(raw.get('translation_en') or ''),
    }


def _record_cell(
    cell: Dict[str, Any], composed: Dict[str, Any], run_ids: List[str]
) -> Dict[str, Any]:
    """
    The composite as a run of its own, written into the sitting the cell belongs to.

    A raster run is written ONCE, at the end (`writeRun` on the surface), and
    until then Help had no address for anything standing on the page. A cell
    that exists is a cell that can be looked at, so it becomes a run the moment
    its composite does.

    The ORDER of the outputs is the point: `view_run` shows a run's FIRST image
    to the vision channel and reads its text outputs aloud, so the account comes
    first and the mean is the picture that is looked at.

    `run_ids` are the runs that went INTO this composite — the ones a picture
    was actually read from. A run that carried none is left out of the record,
    because the parameters of a cell are what a later reader recomputes it from.

    Returns {"run_id": str | None, "refs": {view: address}} — the address each
    picture has inside the new run, so the surface can name them instead of
    sending their bytes up again when it writes the raster.
    """
    from my_app.services.latent_lab_recorder import _readable_plates, get_lab_recorder

    recorder = get_lab_recorder(cell['session_id'])
    if recorder is None:
        logger.warning(f"[MEAN-IMAGES] no open sitting {cell['session_id']}; the cell is not recorded")
        return {'run_id': None, 'refs': {}}

    count = int(composed.get('count') or 0)
    mean_kind = 'latent' if composed.get('mean_kind') == 'latent' else 'pixel'
    account = cell_account(
        cell['model_label'], cell['axis'], count, cell['seed'], cell['translation_en'],
        mean_kind,
    )
    # What each picture IS, for whoever reads the run back: a plate the
    # instrument computed rather than something a model rendered, and the view
    # and the number of pictures it was computed from (`name_plate`). The kind
    # of mean travels with every plate of the cell, because the mean is the one
    # that was made differently and the other two are read against it.
    marks = {'model': cell['model'], 'axis': cell['axis'], 'count': count,
             'plate': 'composite', 'mean_kind': mean_kind}

    def plate(view: str, data: str) -> Dict[str, Any]:
        return {
            'type': 'image',
            'format': 'png',
            'dataBase64': data,
            'meta': {**marks, 'view': view, 'reading': {'view': view, 'pictures': count}},
        }

    outputs: List[Dict[str, Any]] = [
        {
            'type': 'text',
            'format': 'txt',
            'dataBase64': base64.b64encode(account.encode('utf-8')).decode('ascii'),
        },
        plate('mean', composed['mean']),
        plate('relief', composed['relief']),
    ]
    # A set of one carries no contact sheet: the mean IS that picture.
    if composed.get('sheet'):
        outputs.append(plate('images', composed['sheet']))

    written = recorder.record(
        parameters={
            # How a reader tells a cell run from the whole-raster run that the
            # surface writes into the same sitting at the end.
            'part': 'cell',
            'model': cell['model'],
            'model_label': cell['model_label'],
            'axis': cell['axis'],
            'count': count,
            'seed': cell['seed'],
            'prompt_en': cell['translation_en'],
            'mean_kind': mean_kind,
            'run_ids': run_ids,
        },
        outputs=outputs,
    )

    run_id = written.get('run_id')
    if not run_id:
        return {'run_id': None, 'refs': {}}

    # The address of each picture, under the view it shows. The media route
    # numbers an output by its place among the run's image outputs, and
    # `_readable_plates` is the recorder's own rule for that order — so a
    # picture that could not be written moves the ones after it up. Numbering
    # off the outputs sent in instead would hand out the address of a
    # neighbouring picture from the first failed write on.
    refs: Dict[str, str] = {}
    for index, entity in enumerate(_readable_plates(written.get('entities') or [])):
        view = (entity.get('metadata') or {}).get('view')
        if isinstance(view, str) and view:
            refs[view] = f"/api/media/image/{run_id}/{index}"
    return {'run_id': run_id, 'refs': refs}


def _latent_of(run_id: str, cleared_only: bool = False):
    """
    The final latent one run kept, and what that latent says about itself.

    With `cleared_only`, a run whose pictures the platform would NOT hand out
    contributes nothing (`pipeline_recorder.entity_cleared_for_delivery`, the
    same rule the media routes answer by): a picture the check turned back at
    this run's level, and a picture still being checked, are both refused, and
    a run holding no picture at all has nothing to derive a verdict from. The
    latent preview asks for this at the levels that check pictures.

    Returns `(array, meta)`, or None where the run HAS none. None is the only
    ordinary absence and it is no failure: a row whose chunk keeps no latent has
    none, and a picture made before this instrument asked for latents has none
    either. What it costs is the latent mean of the set the run belongs to — the
    answer then says the mean was taken pixel by pixel, which is what it always
    was.

    Every other state raises `LatentUnreadable`, naming the run: a record that
    BREAKS while loading, an entity that names no model or no pipeline class, a
    file that will not load or carries the wrong rank. Those are a latent that IS
    there and cannot be used, and letting them fall through to the pixel mean
    would answer a broken store with a different picture under the same name.

    A record that is simply ABSENT is the first case, not the second: nothing
    says the run ever kept a latent, and the picture reached this route by its
    own address anyway. The set is then averaged pixel by pixel.

    The entity is selected by the platform's single rule (`find_media_entities`)
    and read out of the recorder's own folder, so a latent is addressed exactly
    the way the media route addresses a picture.
    """
    from pathlib import Path

    from config import JSON_STORAGE_DIR
    from my_app.services.pipeline_recorder import load_recorder
    from my_app.utils.media_ref import find_media_entities

    try:
        recorder = load_recorder(run_id, base_path=JSON_STORAGE_DIR)
    except Exception as exc:
        # A record this platform HAS and cannot read is a fault of the store,
        # not a run without a latent — it may well have had one.
        logger.warning(f"[MEAN-IMAGES] {run_id}: the run record would not load ({exc})")
        raise LatentUnreadable(run_id, f"the run record would not load ({exc})")
    if not recorder:
        logger.debug(f"[MEAN-IMAGES] {run_id}: no run record, so no latent")
        return None

    if cleared_only:
        from my_app.services.pipeline_recorder import entity_cleared_for_delivery
        pictures = find_media_entities(recorder.metadata.get('entities', []), 'image')
        if not pictures:
            raise NotCleared(run_id, "no picture yet, so no verdict to derive")
        for picture in pictures:
            cleared, reason = entity_cleared_for_delivery(picture, recorder.metadata)
            if not cleared:
                raise NotCleared(run_id, f"its picture is {reason}, so its latent "
                                         f"stays out of the drawing")

    entities = find_media_entities(recorder.metadata.get('entities', []), 'latent')
    if not entities:
        return None
    entity = entities[0]

    # Both names come out of the record and never out of this file: the mean of
    # a set is decoded by the model that made the set, addressed as that run
    # addressed it.
    meta = (entity.get('metadata') or {}).get('latent') or {}
    for named in ('model_id', 'pipeline_class'):
        if not isinstance(meta.get(named), str) or not meta[named]:
            logger.warning(f"[MEAN-IMAGES] {run_id}: the stored latent names no {named}")
            raise LatentUnreadable(run_id, f"the stored latent names no {named}")

    path = Path(recorder.final_folder) / entity['filename']
    try:
        return mean_images.load_latent(path), meta
    except Exception as exc:
        logger.warning(f"[MEAN-IMAGES] {run_id}: latent unreadable ({exc})")
        raise LatentUnreadable(run_id, exc)


def _refused(png: bytes, run_ids: Sequence[str], safety_level: str) -> Optional[Dict[str, Any]]:
    """
    The image check on a mean this platform has just made, where it refused it.

    Returns the body of a refusal, or None where the picture passed or the level
    asks for no check. The decoded latent mean is a NEW picture — nobody has
    ever looked at it, and it is not any of the pictures that were checked on
    their way in — so it goes through the same check a generated picture goes
    through, at `kids` and `youth`.

    `safety_level` is resolved AT THE REQUEST BOUNDARY and handed in. Asked for
    here, it would be asked for from a worker thread whenever the answer is
    streamed, and the resolver reads the session — see the docstring of
    my_app/services/safety_level_resolver.py, written after a whole surface ran
    a kids course at the installation level. Whether this picture is looked at
    at all hangs on this one value, so it is taken where the session is.

    The checker's own policy stands as it is: `vlm_safety_check` is FAIL-CLOSED
    and answers False for everything it cannot confirm as safe, operational
    failures included. Nothing is softened and nothing is tightened here.

    Where the check cannot be CARRIED OUT — no scratch file, a checker that
    breaks — `CheckDidNotRun` is raised and the route answers 500. That is the
    one thing this function will not do: return None because it never got as far
    as an answer.

    `run_ids` is the set the mean was taken from. It goes into the log line of a
    refusal, which is the only trace of it on this side: the instrument keeps
    the refusal per cell on the surface, and this platform would otherwise hold
    a blocked picture it cannot connect to a single run.
    """
    import os
    import tempfile

    if safety_level not in ('kids', 'youth'):
        return None

    from config import ANALYSIS_TMP_DIR
    from my_app.utils.vlm_safety import vlm_safety_check

    tmp = None
    try:
        # The checker reads a FILE. The scratch is the platform's own,
        # deliberately not uploads_tmp — that one is emptied wholesale when
        # ComfyUI starts.
        ANALYSIS_TMP_DIR.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.NamedTemporaryFile(
            dir=str(ANALYSIS_TMP_DIR), suffix='.png', delete=False)
        try:
            tmp.write(png)
            tmp.close()
            is_safe, reason, description = vlm_safety_check(tmp.name, safety_level)
        finally:
            # Closing belongs here too: a write that fails on a full volume
            # would otherwise leave the handle open for the rest of the process.
            try:
                tmp.close()
            except Exception:
                pass
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
    except Exception as exc:
        logger.error(f"[MEAN-IMAGES] the image check on the mean could not run: {exc}")
        raise CheckDidNotRun(exc)

    if is_safe:
        return None
    logger.warning(
        f"[MEAN-IMAGES] the mean image was turned back at {safety_level}: "
        f"{reason or 'no reason named'} — set: {', '.join(run_ids)}")
    return {'status': 'blocked', 'blocked': True, 'stage': 'vlm_safety',
            'reason': reason, 'vlm_description': description}


@mean_images_bp.route('/latent-preview', methods=['POST'])
def latent_preview():
    """
    The set as it stands, before any decoder has seen it.

    Request: {"run_ids": ["...", ...]}
    Answer:  {"status": "success", "preview": "<base64 png>" | null, "count": n}

    A cell fills over minutes and shows nothing until its set is complete. This
    is what it can show meanwhile: the mean of the latents that are already in,
    drawn as the tensor it is (`mean_images.latent_view`) — the first three
    channels as three colours, in a window that belongs to the whole set rather
    than to any one picture of it (see `mean_images.latent_view`). No decoder,
    no card, no queue: the latents lie on this disk and the answer is one mean
    and one rescaling.

    It is not the mean image and does not look like one. What it shows is the
    arithmetic: one picture at the first step, settling with every further one
    onto what the set shares — and losing contrast exactly insofar as its
    pictures disagree.

    **The drawing is made of pictures the check has cleared.** At `kids` and
    `youth` a run contributes its latent only where the run itself records
    verdicts and every picture of it passed (`pipeline_recorder.
    entity_cleared_for_delivery`), which is the platform's own rule for a
    picture made of pictures (`DERIVED_IMAGE_KINDS`) and costs no model call. A
    run whose picture is still being checked has no verdict yet and joins the
    drawing at the next step; a run recorded at a level that checks nothing
    stays out of it at these two. Where the level cannot be resolved, the
    stricter half of the rule applies.

    Earlier there was no drawing at all at those two levels, on the
    ground that a drawn latent is a picture no check has seen. It is a picture
    of the TENSOR: at 1024 pixels it is 128 by 128, the first three of sixteen
    channels as three colours. The coarse composition, light and dark, colour: a
    check has nothing there that it does not have in the decoded picture, and
    without the drawing the instrument lost its build-up at the two levels a
    workshop runs at.

    `preview` is null, with a 200, wherever there is nothing to draw rather than
    something to complain about: a row that keeps no latents (the ComfyUI rows
    keep none), a set that mixes two measures or two models, a latent that will
    not load. The instrument leaves the cell as it was — nothing on that surface
    hangs on this answer, and a preview that fails must not take a run with it.
    A malformed REQUEST is a 400 wherever the request got that far: that is this
    platform's own caller getting it wrong, and it is worth saying. Where the
    level allows no drawing the answer is the same fixed body whatever the body
    said, because the level is read before anything else is — nothing about a
    request should be learnable from how it is turned away.

    Each call reads the WHOLE set again; the route holds nothing between calls,
    so a cell that loses a picture, a browser that comes back, and a second
    instrument asking about the same runs all get the same answer from the same
    files. The caller keeps the total down: it draws each of the first steps and
    then every fourth, so a cell of fifty pictures costs on the order of n^2/8
    reads of a half-megabyte file spread over the minutes it takes to make it,
    and none at the levels that get no drawing.
    """
    data = request.get_json(silent=True)

    # Resolved HERE, in the thread that serves the request, for the reason the
    # overlay resolves it here (see there). It decides which runs may feed the
    # drawing, and a level that does not resolve takes the stricter half.
    from my_app.services.safety_level_resolver import (
        SAFETY_LEVELS_STRICTEST_FIRST, resolve_safety_level)
    try:
        safety_level = resolve_safety_level()
        cleared_only = (SAFETY_LEVELS_STRICTEST_FIRST.index(safety_level)
                        < SAFETY_LEVELS_STRICTEST_FIRST.index('open'))
    except Exception as exc:
        logger.warning(
            f"[MEAN-IMAGES] the level did not resolve ({exc}); the drawing takes "
            f"only runs whose pictures the check cleared")
        cleared_only = True

    if not isinstance(data, dict):
        return jsonify({'status': 'error', 'error': 'A JSON body is required'}), 400
    run_ids = data.get('run_ids')
    if not isinstance(run_ids, list) or not run_ids:
        return jsonify({'status': 'error',
                        'error': 'run_ids must be a non-empty list'}), 400
    if len(run_ids) > MAX_RUNS:
        return jsonify({
            'status': 'error',
            'error': f'At most {MAX_RUNS} runs may be averaged, received {len(run_ids)}',
        }), 400
    if not all(isinstance(run_id, str) and run_id for run_id in run_ids):
        return jsonify({'status': 'error',
                        'error': 'run_ids must be a list of run ids'}), 400

    latents = []
    waiting = False
    for run_id in run_ids:
        try:
            held = _latent_of(run_id, cleared_only=cleared_only)
        except NotCleared as exc:
            # A picture the check has not judged yet. The next step asks again.
            logger.debug(f"[MEAN-IMAGES] preview without {exc.run_id}: {exc.cause}")
            waiting = True
            continue
        except LatentUnreadable as exc:
            # In the overlay this is a fault that must not pass as the other
            # mean. Here it is one picture missing from a drawing that claims
            # nothing: the set's own answer will name it when the cell closes.
            logger.debug(f"[MEAN-IMAGES] preview without {exc.run_id}: {exc.cause}")
            continue
        if held:
            latents.append(held)

    if not latents:
        return jsonify({'status': 'success', 'preview': None, 'count': 0,
                        'why': 'not_yet' if waiting else 'no_latents'}), 200

    # The same three questions the overlay asks before it averages latents at
    # all (`_run_overlay`). A drawing that stood for a set the cell will average
    # pixel by pixel would be a picture of arithmetic that never happens.
    shapes = {tuple(array.shape) for array, _meta in latents}
    models = {meta['model_id'] for _array, meta in latents}
    classes = {meta['pipeline_class'] for _array, meta in latents}
    if len(shapes) != 1 or len(models) != 1 or len(classes) != 1:
        return jsonify({'status': 'success', 'preview': None, 'count': 0,
                        'why': 'mixed_set'}), 200

    try:
        view = mean_images.latent_view([array for array, _meta in latents])
    except Exception as exc:
        logger.warning(f"[MEAN-IMAGES] the latent preview could not be drawn: {exc}")
        return jsonify({'status': 'success', 'preview': None, 'count': 0,
                        'why': 'undrawable'}), 200

    return jsonify({
        'status': 'success',
        'preview': mean_images.to_png_base64(view),
        'count': len(latents),
    }), 200


@mean_images_bp.route('/overlay', methods=['POST'])
def overlay():
    """
    A set of runs laid over each other.

    Request: {"run_ids": ["...", ...],
              "record": {"session_id": "...", "model": "...", "model_label": "...",
                         "axis": "seedFixed" | "promptFixed", "seed": 424242,
                         "translation_en": "..."}?}
    Answer:  {"status": "success", "mean": "<base64 png>", "relief": "...",
              "sheet": "...", "count": 5, "missing": [], "resized": false,
              "width": 1024, "height": 1024, "mean_kind": "latent" | "pixel",
              "run_id": "..." | null,
              "refs": {"mean": "/api/media/image/<run_id>/0", ...}}

    `mean_kind` is WHERE the averaging happened. "latent" wherever a set of MORE
    THAN ONE run kept a final latent throughout and all of them name one model,
    one pipeline class and one measure: the latents are averaged and the average
    is decoded ONCE, and that decode is the mean. "pixel" everywhere else — a set
    of one, a row with no latent path, a set in which a run kept no latent, a set
    that mixes two models or two classes.

    None of those is an error. Four things are, and each says which, rather than
    quietly handing back the other mean under the name of this one:

      502  a run's latent is THERE and cannot be read — a record that will not
           load, an entity naming no model or class, a file that will not load.
           The run is named in the message.
      502  the decode of the mean latent failed.
      503  the card is taken. The same request works in a moment.
      500  the image check on the decoded mean could not be CARRIED OUT. An
           absent judgement is not a pass.

    The decoded mean is a picture nobody has looked at yet, so it goes through
    the image check like a generated picture.

    A set of ONE is the recorded picture and nothing was averaged at all, so
    there is nothing to take before a decoder: it is answered as "pixel", no
    decode is asked for, the picture is not put through the image check a second
    time, and the account keeps its own sentence about a single picture.

    A refusal answers 200 with {"status": "blocked", "blocked": true,
    "stage": "vlm_safety", "reason": ..., "vlm_description": ...} — the fields
    the rest of this platform blocks in — and records nothing.

    With a `record` the composite becomes a run of its own and `run_id` is its
    address — what the surface hands Help so a finished cell can be looked at
    while the rest of the raster is still filling. Without one, or where the
    writing failed, `run_id` is null and the composite is exactly what it was.

    `refs` names where each of those pictures now lies, keyed by the view it
    shows (`mean`, `relief`, `images`) and holding only what was actually
    written. The surface passes these addresses on when it writes the whole
    raster, instead of holding the pictures and uploading them a further time.
    Empty wherever `run_id` is null.

    A run whose image cannot be read is named in `missing` and left out of both
    composites; `count` says how many actually went in. One image is a set of
    one: the mean IS that image, `sheet` comes back as null because a sheet of
    one would be a second copy of it, and the relief is its own.

    With "enable_streaming" the answer travels as the platform's SSE stream
    instead of as one JSON body. It is the same run; only its way back is
    different. A latent mean takes the plant-wide GPU slot and waits its turn in
    the queue — up to GPU_ADMISSION_ACQUIRE_TIMEOUT_S, an hour and a half
    (gpu_service/config.py) — and where the level asks for a check, what it
    decoded queues a second time. The edge in front of this server ends a
    request whose origin has sent nothing for about 100 seconds and hands the
    browser a 524, so a busy card used to cost the answer of a decode that had
    already happened.

    The run names no `client_gone` parameter, and that is a decision rather than
    an omission: the mean it decodes is saved, so a run left by its reader still
    finishes something. Work that could give something back by stopping asks for
    the signal by declaring the parameter; see `streamed_answer`.
    """
    data = request.get_json(silent=True)

    # Resolved HERE, in the thread that serves the request, and handed down.
    # Asked from a worker of the streamed transport the resolver answers with
    # the STRICTEST level plus a warning: the transport MARKS that thread, and
    # the resolver reads the mark — see the docstring of
    # my_app/services/safety_level_resolver.py. (Until 2026-09-05 the guard
    # there rested on `has_request_context()` alone, which is True on such a
    # worker, so the promise did not hold.) Whether the decoded mean is looked
    # at at all hangs on this answer, so it is taken where the session is,
    # rather than wherever the run happens to be executing.
    from my_app.services.safety_level_resolver import resolve_safety_level
    try:
        safety_level = resolve_safety_level()
    except Exception as exc:
        # The resolver documents that it never raises. If that ever stops being
        # true, the level is unknown — and an unknown level leaves the mean
        # unjudged, which is never a pass here.
        return jsonify({
            'status': 'error',
            'error': 'The image check of the mean could not run: '
                     f'the safety level could not be resolved ({exc})',
        }), 500

    return answered_either_way(data, _run_overlay, data, safety_level,
                               label='MEAN-IMAGES-OVERLAY')


def _run_overlay(data: Any, safety_level: str):
    """The overlay run, and the ``(payload, http_status)`` it answers with.

    Split out of the route so that one run can be answered either way. It must
    not reach for ``request``: everything it needs stands in ``data``, and the
    safety level is resolved at the request boundary and passed in.
    """
    if not isinstance(data, dict):
        return {'status': 'error', 'error': 'A JSON body is required'}, 400

    run_ids = data.get('run_ids')
    if not isinstance(run_ids, list) or not run_ids:
        return {'status': 'error', 'error': 'run_ids must be a non-empty list'}, 400
    if len(run_ids) > MAX_RUNS:
        return {
            'status': 'error',
            'error': f'At most {MAX_RUNS} runs may be laid over each other, received {len(run_ids)}',
        }, 400
    if not all(isinstance(r, str) and r for r in run_ids):
        return {'status': 'error', 'error': 'run_ids must be a list of run ids'}, 400

    # THE resolver of /api/media/image/<run_id>/0 — a second reading of the
    # storage layout would let a composite be made of other files than the ones
    # the cells are showing.
    from my_app.routes.media_routes import _resolve_image

    arrays = []
    missing = []
    # The runs a picture was actually read from, in the order they went into the
    # stack. `count` is the height of that stack, so the two say the same thing
    # — which is what the recorded cell claims about itself.
    used: List[str] = []
    for run_id in run_ids:
        resolved, _error = _resolve_image(run_id, 0)
        if not resolved:
            missing.append(run_id)
            continue
        file_path = resolved[0]
        try:
            arrays.append(mean_images.load_image(file_path))
        except Exception as exc:
            logger.warning(f"[MEAN-IMAGES] {run_id}: image unreadable ({exc})")
            missing.append(run_id)
            continue
        used.append(run_id)

    if not arrays:
        return {
            'status': 'error',
            'error': f'None of the {len(run_ids)} runs carried a readable image',
            'missing': missing,
        }, 404

    # The mean BEFORE the decoder, where the whole set can give one. Every run
    # that went in has to carry a latent, and all of them have to name one model,
    # one pipeline class and one measure — a set that mixes them is the ComfyUI
    # rows or a row that lost a latent, and it is averaged pixel by pixel as it
    # always was. A run whose latent is THERE and unusable is not that case: it
    # names itself and the request fails (`LatentUnreadable`).
    #
    # A set of ONE is out from the start. There is no averaging in it: the cell
    # IS the picture that was recorded, and decoding its latent a second time
    # would spend the card, and a second image check, on a picture the run
    # already holds and already checked.
    try:
        latents = [_latent_of(run_id) for run_id in used]
    except LatentUnreadable as exc:
        return {
            'status': 'error',
            'error': f'The latent of run {exc.run_id} could not be read: {exc.cause}',
        }, 502
    mean_kind = 'pixel'
    mean_png = None
    if len(used) > 1 and all(latents):
        shapes = {tuple(array.shape) for array, _meta in latents}
        models = {meta['model_id'] for _array, meta in latents}
        classes = {meta['pipeline_class'] for _array, meta in latents}
        if len(shapes) == 1 and len(models) == 1 and len(classes) == 1:
            mean_kind = 'latent'
        else:
            logger.info(f"[MEAN-IMAGES] the set names {len(models)} model(s) and "
                        f"{len(classes)} pipeline class(es) in {len(shapes)} "
                        f"measure(s); the mean is taken pixel by pixel")

    if mean_kind == 'latent':
        from my_app.services import latent_decoder
        from my_app.services.gpu_lease_client import GpuBusyError
        from my_app.services.own_loop import run_blocking

        meta = latents[0][1]

        def decode(npy: bytes) -> bytes:
            """The one asynchronous call of this route, on a thread of its own
            with a copy of this request's context (my_app/services/own_loop.py):
            a decode of a mean is the one moment on this route where a model is
            on the card and the bar could say so
            (my_app/services/streaming_response.py, `note_dispatch`). ComfyUI
            decodes it, under the checkpoint that made the set and under a
            workload of its own, `vae-decode`, so the gate's durations for a
            generation on that checkpoint stay a generation's
            (my_app/services/latent_decoder.py).
            """
            return run_blocking(latent_decoder.decode_in_comfyui(meta, npy))

        try:
            mean_png = decode(mean_images.latent_npy_bytes(
                mean_images.mean_latent([array for array, _meta in latents])))
        except GpuBusyError as exc:
            # Not a failure of the set: the card is taken and the same request
            # works in a moment. It must not come back as the other mean under
            # the name of this one.
            logger.warning(f"[MEAN-IMAGES] the latent mean waits for the card: {exc}")
            return {
                'status': 'error',
                'error': f'The latent mean could not be decoded: the card is busy — {exc}',
            }, 503
        except Exception as exc:
            logger.error(f"[MEAN-IMAGES] the latent mean did not decode: {exc}")
            return {
                'status': 'error',
                'error': f'The latent mean could not be decoded: {exc}',
            }, 502

        try:
            refusal = _refused(mean_png, used, safety_level)
        except CheckDidNotRun as exc:
            # The decode is already spent and the picture exists. What is missing
            # is a judgement on it, and nothing here turns that into a pass.
            return {
                'status': 'error',
                'error': f'The image check of the mean could not run: {exc.args[0]}',
            }, 500
        if refusal is not None:
            return refusal, 200

    try:
        composed = mean_images.compose(arrays, mean_png=mean_png)
    except Exception as exc:
        logger.error(f"[MEAN-IMAGES] overlay failed: {exc}")
        return {'status': 'error', 'error': f'The overlay failed: {exc}'}, 500
    composed['mean_kind'] = mean_kind

    # The composite is the answer, and the recording must never take it away:
    # a sitting that has gone, a full disk or a refused write costs the address
    # and leaves the picture standing.
    run_id = None
    refs: Dict[str, str] = {}
    cell = _usable_record(data.get('record'))
    if cell:
        try:
            recorded = _record_cell(cell, composed, used)
            run_id = recorded['run_id']
            refs = recorded['refs']
        except Exception as exc:
            logger.warning(f"[MEAN-IMAGES] the cell was not recorded: {exc}")

    # AI-Origin Disclosure (EU AI Act Art. 50) on the copy the PAGE gets. The
    # three plates travel there as base64, and the cell shows and downloads that
    # copy until the raster is written back at the end of the run; the recorder
    # above marks only what it writes, and nothing marked what the page held in
    # the meantime — a cell downloaded while the rest of the raster was still
    # filling, or after a write-back that failed, went out unmarked. Marked
    # AFTER the recording, so the recorder receives the plates as it always
    # did and draws an operator's visible layer once rather than twice
    # (watermark_image_bytes skips a marked picture only while no layer is
    # drawn). A cell that could not be recorded here sends this marked copy
    # up again when the raster is written back, and a drawn layer is drawn a
    # second time on that copy, as on every lab result that reaches the
    # recorder as marked base64 (the Fusion Workbench cells among them); the
    # setting is off by default, and the recorder is where that would be
    # settled. What the disclosure names is read off the request rather than
    # off the usable record: a record the recorder had to refuse (a sitting
    # that has ended) still says which model drew the set.
    asked = data.get('record') if isinstance(data.get('record'), dict) else {}
    try:
        from my_app.services.latent_lab_recorder import _disclosed
        from my_app.services.watermark_service import watermark_result_metadata
        watermark_result_metadata(
            composed,
            _disclosed({'model': str(asked.get('model') or ''), 'seed': asked.get('seed')}, None),
            extra_keys=('mean', 'relief', 'sheet'),
        )
    except Exception as exc:
        logger.warning(f"[MEAN-IMAGES] watermark not applied ({exc})")

    composed['status'] = 'success'
    composed['missing'] = missing
    composed['run_id'] = run_id
    composed['refs'] = refs
    return composed, 200
