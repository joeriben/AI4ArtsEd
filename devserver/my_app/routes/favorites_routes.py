"""
Flask routes for Favorites API

Provides REST endpoints for managing user favorites (bookmarked media outputs).
Favorites persist across sessions and allow restoring complete session settings.
"""
import json
import logging
from datetime import datetime
from typing import NamedTuple, Optional

from flask import Blueprint, jsonify, request

from config import JSON_STORAGE_DIR
from my_app.lab.auth_service import (
    account_stamp,
    current_user,
    place_session_unverified,
)
from my_app.services.favorites_store import (
    editing,
    load_favorites,
    load_favorites_strict,
    save_favorites,
    was_dropped,
)
from my_app.services.latent_lab_recorder import build_instrument_object, recovered_run_data
from my_app.services.pipeline_recorder import IMAGE_CHECKED_LEVELS, load_recorder
from my_app.services.safety_gate import (
    CHECKPOINT_RESULT,
    REASON_UNCHECKED,
    check_intake,
    normalise_level,
    run_opens_at,
    safety_block,
)
from my_app.services.safety_level_resolver import resolve_safety_level
from my_app.services.thumbnails import source_size

logger = logging.getLogger(__name__)

# Blueprint erstellen
favorites_bp = Blueprint('favorites', __name__, url_prefix='/api/favorites')


def _media_url(run_id: str, media_type: str, index: int) -> str:
    """The URL of a run's Nth picture, sound or film of that kind.

    `_get_thumbnail_url` answers for a run as a whole and cannot tell two
    pictures of one run apart; this is for a listing that walks the entities.
    """
    if media_type == 'image':
        return f"/api/media/image/{run_id}/{index}"
    if media_type in ('audio', 'music', 'video'):
        return f"/api/media/{media_type}/{run_id}/{index}"
    return f"/api/media/{media_type}/{run_id}"


def _public(entity: dict) -> dict:
    """The entity as it may leave the server — the platform's one wording."""
    from my_app.services.pipeline_recorder import public_entity
    return public_entity(entity)


def _image_file(recorder, level, index: int = 0):
    """The file holding a run's Nth picture, or None where there is none.

    By the SAME order the URL resolves by (media_routes._find_entities_by_type
    sorts on `sequence`). Taking the entities as they lie in the list would
    address one file and answer about another. Asked at the level of whoever
    asks: a picture delivery refuses them is none they are offered.
    """
    if not recorder:
        return None
    from my_app.utils.media_ref import find_media_entities
    from my_app.services.pipeline_recorder import SafetyRefusal
    try:
        images = find_media_entities(recorder.metadata.get('entities') or [], 'image')
        return recorder.checked_entity_path(images[index], level)
    except (AttributeError, IndexError, TypeError, KeyError):
        return None
    except SafetyRefusal:
        # A favourite whose picture the content check refused has no file to
        # offer; the caller already treats "no file" as the ordinary case.
        return None


def _image_version(recorder, level, index: int = 0):
    """When a run's Nth picture was last written, in MICROSECONDS.

    The same unit `replace_output_image` hands back, and for the same reason:
    the number reaches a browser, where a nanosecond stamp of this era is
    rounded, and the two surfaces would then address one file under two names.

    A miniature is answered as `immutable` (media_routes.get_image_thumbnail),
    which is only true while the file stays as it was. Attention Cartography can
    set its plate again after the run — its picture IS the map it was read by —
    so the URL carries the moment, and a changed picture is a changed URL.

    None where there is no such picture; the caller then hands out the plain URL.
    """
    picture = _image_file(recorder, level, index)
    if picture is None:
        return None
    try:
        return picture.stat().st_mtime_ns // 1000
    except OSError:
        return None


#: The kinds a run records under the RUNTIME's own name rather than as
#: `output_<kind>`: a sketch is its source text, and the platform stores and
#: serves it as such (`/api/media/p5/<run>`, media_routes). A card that draws a
#: still of a running sketch is showing a picture the browser made, which is in
#: no run folder — keeping such a run as an image claims something that is not
#: there, and the strip then draws an <img> at a URL answering 404.
RUNTIME_KINDS = ('p5', 'tonejs', 'sonicpi', 'midi')


def _entity_types_for(media_type: str) -> set:
    """The entity names a run of this kind can carry.

    Music and sound are one file to this platform, as the media route reads it
    too; a runtime carries its own name and no `output_` in front of it; and
    runs from before the outputs were named by kind carry the bare word.
    """
    if media_type in RUNTIME_KINDS:
        # The bare name is what the recorders write today; `output_p5` and its
        # kin are accepted too, because the media route prefers that form and
        # the watermark service names it. Three readers of one metadata file
        # must not disagree about which names count.
        return {media_type, f'output_{media_type}'}
    kinds = {media_type}
    if media_type == 'music':
        kinds.add('audio')
    elif media_type == 'audio':
        kinds.add('music')
    return kinds | {f'output_{kind}' for kind in kinds}


def _get_thumbnail_url(run_id: str, media_type: str) -> str:
    """
    Generate thumbnail URL for a given run and media type.

    Args:
        run_id: Run ID
        media_type: Media type (image, audio, video, etc.)

    Returns:
        URL string for the thumbnail
    """
    if media_type == 'image':
        return f"/api/media/image/{run_id}/0"
    elif media_type == 'canvas':
        # A kept workflow has no medium; the strip draws its mark instead.
        return ''
    elif media_type == 'video':
        return f"/api/media/video/{run_id}"
    elif media_type in ['audio', 'music']:
        return f"/api/media/audio/{run_id}"
    else:
        # A runtime answers under its own name and takes no index: the media
        # route addresses a run's sketch, not the n-th of them. A folder that
        # recorded several (three runs landed in one on 2026-06-23) therefore
        # reports each of them at the address of the first.
        return f"/api/media/{media_type}/{run_id}"


def _picture_fields(run_id: str, recorder, level) -> dict:
    """What a surface needs about a kept PICTURE beyond what the record says.

    The stored `thumbnail_url` points at the FULL render - it was written that
    way long before there were miniatures - and is answered small here rather
    than migrated, so the favourites that already stand there get the small copy
    too (2026-08-25). The measurements travel with it because no record holds
    them, and a layer that opens on the picture has to know the place it will
    take before the file is there.

    Both the listing and the answer to a new star go through here. They did not:
    a run starred a moment ago is exactly the one a workshop opens next, and it
    was the one arriving without any of this - the strip drew its plate from the
    full render, and the layer had nothing to hold a place with.
    """
    picture = _image_file(recorder, level)
    version = _image_version(recorder, level)
    fields = {
        'thumbnail_url': (
            f"/api/media/image/{run_id}/0/thumb?v={version}" if version
            else f"/api/media/image/{run_id}/0/thumb"
        )
    }
    size = source_size(picture) if picture else None
    if size:
        fields['width'], fields['height'] = size
    return fields


def _canvas_entity(recorder):
    """The `canvas` entity of a kept workflow (canvas_routes.keep_workflow)."""
    for entity in ((recorder.metadata or {}).get('entities') or []) if recorder else []:
        if isinstance(entity, dict) and entity.get('type') == 'canvas':
            return entity
    return None


def _read_workflow(path) -> dict | None:
    """A workflow file as the Canvas reads it, or None where it holds none."""
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get('nodes'), list):
        return None
    connections = data.get('connections')
    return {
        **data,
        'type': 'canvas_workflow',
        'name': data.get('name') if isinstance(data.get('name'), str) else '',
        'connections': connections if isinstance(connections, list) else [],
    }


def _canvas_workflow_of(run_id: str, recorder) -> dict | None:
    """The Canvas board a run brings along, or None.

    A kept workflow holds it as its entity. An output of a Canvas run is a run
    of its own, `<canvas run>__<node>` (canvas_executor), and its board is the
    `workflow.json` the Canvas run recorded at its start (canvas_recorder).
    Either way the favourites strip can open the board again.
    """
    entity = _canvas_entity(recorder)
    if entity:
        filename = entity.get('filename')
        return _read_workflow(recorder.final_folder / filename) if filename else None
    if '__' not in run_id:
        return None
    parent = load_recorder(run_id.split('__', 1)[0], base_path=JSON_STORAGE_DIR)
    if not parent or (parent.metadata or {}).get('type') != 'canvas_workflow':
        return None
    return _read_workflow(parent.run_folder / 'workflow.json')


def _canvas_label(recorder) -> str:
    """What the plate of a kept workflow says: its name, else its prompt."""
    entity = _canvas_entity(recorder)
    label = ((entity or {}).get('metadata') or {}).get('label')
    if not isinstance(label, str) or not label:
        return ''
    return label[:100] + '...' if len(label) > 100 else label


def _keeps_media(recorder, media_type: str) -> bool:
    """Whether the run really holds a piece of the kind the favourite claims.

    The star was set on the RUN and the kind was taken from the surface that
    drew it, so a run could be kept as an image while what it made was a p5
    sketch, and a run that made nothing at all could be kept too. The strip then
    drew an `<img>` at a URL that answers 404: the browser's own broken-image
    mark and the word "Favorite" where the picture should be, on a plate that
    cannot be opened and has no other gesture on it.

    The music of this platform is a sound file, which is how the media route
    reads it too, and a sketch is the source text a run really holds
    (`RUNTIME_KINDS`) rather than the still its card happens to show.
    """
    if not recorder:
        return False
    entities = (recorder.metadata or {}).get('entities') or []
    wanted = _entity_types_for(media_type)
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        entity_type = entity.get('type', '')
        if entity_type in wanted:
            return True
    return False


def _restorable(recorder, level) -> bool:
    """Whether a run may be opened again by whoever asks at `level`.

    At kids and youth only a run made at the same level or a stricter one: its
    Stage-2 text was checked with the text question of its own level, and a
    looser run's was not. A run that names no level answers for none, and
    neither does a run that is gone. Above youth every run may be opened
    (safety_gate.run_opens_at, which the chat asks as well).
    """
    run_level = (recorder.metadata or {}).get('safety_level') if recorder else None
    return run_opens_at(run_level, level)


def _listable(fav: dict, recorder, level) -> bool:
    """Whether the strip shows this favourite to whoever asks at `level`.

    What it lists can be opened: a run `_restorable` lets through, and of a kept
    picture a first picture delivery hands out. A run whose pictures were kept
    before they carried verdicts is therefore not shown at kids and youth.
    Browsing asks no model; the verdicts are read as they stand.
    """
    if not _restorable(recorder, level):
        return False
    if fav.get('media_type') != 'image' or normalise_level(level) not in IMAGE_CHECKED_LEVELS:
        return True
    return _image_file(recorder, level) is not None


def _note_refusal(body: dict, level):
    """The answer that refuses a favourite's note, or None where it may be kept.

    A note is the user's own material: it is kept beside the favourite, and the
    chat hands it to its model (`lookup_shared_favorites`). It is checked once,
    where it comes in, for names of living private persons and for addresses
    (safety_gate.check_intake). The level it was written at is kept beside it
    (`note_level`); the chat hands it on only where that level opens
    (safety_gate.run_opens_at). A note that does not pass is not kept, and
    neither is the favourite or the change it came with; a check that could not
    run refuses as well, and its block message says so.
    """
    note = body.get('user_note')
    if note is None or not str(note).strip():
        return None
    verdict = check_intake(str(note), level=level, kind="text", field="user_note")
    if verdict.passed:
        return None
    logger.warning("[FAVORITES] note refused (%s)", verdict.reason_key)
    return jsonify({'error': 'safety_blocked', 'safety_block': verdict.block()}), 403


class _Asker(NamedTuple):
    """Whoever asks: the account the session is signed in with, held with the
    moment it was made, or, without an account, the device id the request
    sends."""
    owner_id: Optional[int] = None
    owner_stamp: Optional[str] = None
    device_id: Optional[str] = None


# The answer to a request whose place session could not be checked: it runs
# without its account, and what it kept would go to the device.
_UNCHECKED = {'error': 'The sign-in could not be checked; try again'}


def _asker(device_id) -> _Asker:
    """Who asks.

    Since 2026-11-14 a favourite belongs to the account it was kept under, as a
    kept perspective does (interception_prompts_routes.py): the account of a
    place keeps what its devices starred under every code the place is given,
    and a leader's account keeps its favourites on every machine. A request
    without an account is told apart by the device id it sends, the browser id
    with the day (composables/useDeviceId.ts), as before.

    The account is held with the moment it was made (`account_stamp`): SQLite
    gives the id of a deleted account to the next account made, and that one
    must not find the favourites of the one before.

    A sign-in that has ended (a place whose code was replaced, or whose course
    closed, was archived or deleted; lab/auth_service.py,
    `_check_place_session`) asks as a device without an account. A course that
    closed lets its codes in again once its access is open; an archived or a
    deleted course lets no code in. What the device keeps in between stays on
    the device, and an account signed in on that device reaches it the same
    day (`_owns`). A request whose place session could not be checked runs
    without its account as well; the routes answer it before they ask here
    (`place_session_unverified`).
    """
    user = current_user()
    if user is not None:
        return _Asker(owner_id=user.id, owner_stamp=account_stamp(user), device_id=device_id)
    return _Asker(device_id=device_id)


def _owns(fav: dict, asker: _Asker) -> bool:
    """Whether `fav` was kept by whoever asks: under this account, or from
    this device without an account.

    The device id is the browser with the day (composables/useDeviceId.ts).
    What a device kept without an account is reached from that device on that
    day whether an account is signed in there or not, as it was before
    favourites had owners: a place whose sign-in ended keeps what it starred in
    between, and a leader who starred before signing in keeps it too."""
    if fav.get('owner_id') is not None:
        return (asker.owner_id is not None
                and fav.get('owner_id') == asker.owner_id
                and fav.get('owner_stamp') == asker.owner_stamp)
    return bool(asker.device_id) and fav.get('device_id') == asker.device_id


def _owner_fields(asker: _Asker) -> dict:
    """Whose a favourite kept now is: the account, or, without one, the
    device (`_asker`)."""
    return {
        'device_id': None if asker.owner_id is not None else asker.device_id,
        'owner_id': asker.owner_id,
        'owner_stamp': asker.owner_stamp,
    }


def _ownerless(fav: dict) -> bool:
    """An entry from before favourites had owners: kept under no account and
    from no device."""
    return fav.get('owner_id') is None and not fav.get('device_id')


def _may_change(fav: dict, asker: _Asker) -> bool:
    """Whose favourite is this, and may whoever asks change it?

    Each entry carries the account it was kept under, or, kept without an
    account, the `device_id` of the browser that added it (`_asker`).
    Until 2026-08-29 neither DELETE nor PATCH looked at the owner:
    both matched on `run_id` alone, so any device could remove or rename
    any other device's favourite. Only the surface was guarded — and in
    `global` view mode the strip deliberately shows everyone's favourites.
    In a workshop with twenty tablets on one server that is a button that
    takes something away from someone else.

    An entry WITHOUT an owner may be changed by anyone: it predates
    per-user favourites, and refusing it would strand it in the strip with
    no way to remove it. That does not reopen the hole — a request can
    only leave its OWN entry unowned, never someone else's.
    """
    if _ownerless(fav):
        return True
    return _owns(fav, asker)


def _answer(fav: dict, asker: _Asker) -> dict:
    """An entry as a page receives it: with whether whoever asks may change it,
    and without whom it belongs to. A device id in the listing was all another
    page needed to remove or rename that device's favourites; the account is
    nobody else's business either."""
    out = {k: v for k, v in fav.items() if k not in ('owner_id', 'owner_stamp', 'device_id')}
    out['may_change'] = _may_change(fav, asker)
    return out


@favorites_bp.route('', methods=['GET'])
def get_favorites():
    """
    List all favorites with metadata.

    Query parameters:
        - device_id: The device that asks, where no account is signed in
        - view_mode: 'per_user' (what whoever asks has kept, `_owns`) or
          'global' (show all)

    Returns:
        200: List of favorites with thumbnail URLs and metadata
        503: The place session could not be checked
        500: Server error

    Example:
        GET /api/favorites?device_id=abc123_2026-01-28&view_mode=per_user
    """
    try:
        # Query parameters for filtering
        device_id = request.args.get('device_id')
        view_mode = request.args.get('view_mode', 'per_user')  # 'per_user' or 'global'
        level = resolve_safety_level()
        if place_session_unverified():
            return jsonify(_UNCHECKED), 503
        asker = _asker(device_id)

        logger.info(f"[FAVORITES] Fetching favorites (view_mode={view_mode}, device_id={device_id})")

        data = load_favorites()
        favorites = data.get('favorites', [])

        # In per_user mode, what whoever asks has kept.
        if view_mode == 'per_user':
            favorites = [f for f in favorites if _owns(f, asker)]
            logger.info(f"[FAVORITES] Filtered to {len(favorites)} own favorites")
        else:
            logger.info(f"[FAVORITES] Returning {len(favorites)} favorites (global mode)")

        # Enrich favorites with additional metadata from run data
        enriched_favorites = []
        for fav in favorites:
            run_id = fav.get('run_id')

            # Try to load run metadata
            recorder = load_recorder(run_id, base_path=JSON_STORAGE_DIR)

            # At kids and youth the strip lists only what may be opened.
            if not _listable(fav, recorder, level):
                continue

            enriched = {
                **_answer(fav, asker),
                # A run folder that is still there says nothing about the piece
                # that was kept — the strip has to know whether it can draw one.
                'exists': _keeps_media(recorder, fav.get('media_type') or '')
            }
            # A note goes out where the level it was written at opens, as in
            # the chat's lookup_shared_favorites.
            if not run_opens_at(fav.get('note_level'), level):
                enriched['user_note'] = ''

            # The strip shows a picture at 100 px and the layer opens on the
            # picture itself; neither is what the record holds. See
            # `_picture_fields`.
            if fav.get('media_type') == 'image':
                enriched.update(_picture_fields(run_id, recorder, level))

            if recorder:
                # Add run metadata
                enriched['schema'] = recorder.metadata.get('config_name', 'unknown')
                enriched['timestamp'] = recorder.metadata.get('timestamp', '')

                # Get input text if available
                for entity in recorder.metadata.get('entities', []):
                    if entity['type'] == 'input':
                        input_file = recorder.final_folder / entity['filename']
                        if input_file.exists():
                            text = input_file.read_text(encoding='utf-8')
                            # Truncate for preview
                            enriched['input_preview'] = text[:100] + '...' if len(text) > 100 else text
                            break

                # A Latent Lab run keeps no `input` file: what was asked stands
                # in its parameters. Without this the tile of an instrument's
                # favourite would carry no words at all.
                if recorder.metadata.get('type') == 'latent_lab':
                    enriched['schema'] = recorder.metadata.get('latent_lab_tool', 'latent_lab')
                    kept = recorder.metadata.get('parameters')
                    if not kept:
                        # The same source the restore below reads, so tile and
                        # opened run say the same thing. Read from the top level
                        # alone, both stayed empty for a run that keeps its
                        # prompt only in its own parameters file. Asked only
                        # where the top level is empty: this runs once per
                        # favourite, and 40 stored runs would otherwise open a
                        # file for a block the tile never looks at.
                        kept, _ = recovered_run_data(recorder.metadata, recorder.final_folder)
                    prompt = kept.get('prompt') if isinstance(kept, dict) else None
                    if isinstance(prompt, str) and prompt and 'input_preview' not in enriched:
                        enriched['input_preview'] = prompt[:100] + '...' if len(prompt) > 100 else prompt

                # A kept Canvas workflow keeps no `input` file either: its
                # words are its name, or the prompt the board starts from.
                if fav.get('media_type') == 'canvas':
                    label = _canvas_label(recorder)
                    if label and 'input_preview' not in enriched:
                        enriched['input_preview'] = label

            enriched_favorites.append(enriched)

        logger.info(f"[FAVORITES] Returning {len(enriched_favorites)} favorites")

        return jsonify({
            'favorites': enriched_favorites,
            'total': len(enriched_favorites),
            'mode': data.get('mode', 'global')
        }), 200

    except Exception as e:
        logger.error(f"[FAVORITES] Error fetching favorites: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': 'Failed to fetch favorites',
            'details': str(e)
        }), 500


@favorites_bp.route('', methods=['POST'])
def add_favorite():
    """
    Add a new favorite.

    Request body (JSON):
        - run_id: Run ID to favorite (required)
        - media_type: Type of media ('image', 'audio', 'video', etc.) (required)
        - device_id: Device identifier (browser_id + date), the owner where
          no account is signed in (`_asker`)
        - user_id: Optional user ID (default: 'anonymous')
        - user_note: Optional note from user

    Returns:
        201: Favorite created successfully, also where an entry without
             owner stood for the run: it is replaced
        400: Invalid request (missing required fields), or neither an
             account nor a device_id to keep the favourite under
        401: The account was deleted while the request was on its way, and
             the request names no device that could keep the star
        403: The note did not pass the intake check (`safety_block`)
        409: Favorite already exists, or the run is kept by another account
             or device (a run is kept once), or the run holds nothing of
             that kind to keep
        503: The place session could not be checked
        500: Server error

    Example:
        POST /api/favorites
        {"run_id": "run_abc123", "media_type": "image"}
    """
    try:
        # Parse request
        body = request.get_json()

        if not body:
            return jsonify({'error': 'Request body required'}), 400

        run_id = body.get('run_id')
        media_type = body.get('media_type')
        device_id = body.get('device_id')  # Per-user favorites
        user_id = body.get('user_id', 'anonymous')
        user_note = body.get('user_note', '')
        source_view = body.get('source_view')  # Vue route path for correct restore routing
        level = resolve_safety_level()
        if place_session_unverified():
            return jsonify(_UNCHECKED), 503
        asker = _asker(device_id)

        # Debug logging
        logger.info(f"[FAVORITES] POST Request Body: {body}")
        logger.info(f"[FAVORITES] device_id extracted: {device_id!r} (type: {type(device_id).__name__})")

        if not run_id:
            return jsonify({'error': 'run_id is required'}), 400

        if not media_type:
            return jsonify({'error': 'media_type is required'}), 400

        # Without an account the device keeps the favourite. Kept by neither,
        # it would be an entry without owner, which anybody may take back.
        if asker.owner_id is None and not asker.device_id:
            return jsonify({'error': 'device_id is required'}), 400

        logger.info(f"[FAVORITES] Adding favorite: run_id={run_id}, media_type={media_type}, device_id={device_id}")

        # Verify run exists
        recorder = load_recorder(run_id, base_path=JSON_STORAGE_DIR)
        if not recorder:
            return jsonify({
                'error': 'Run not found',
                'run_id': run_id
            }), 404

        # And that there is something of that kind to keep. Keeping a run whose
        # piece the platform cannot serve produces a plate in the strip that can
        # neither be shown nor opened.
        if not _keeps_media(recorder, media_type):
            return jsonify({
                'error': f'Run holds no {media_type} to keep',
                'run_id': run_id,
                'media_type': media_type
            }), 409

        # Checked before the store is read, so the check does not widen the
        # time between reading the store and writing it back.
        refusal = _note_refusal(body, level)
        if refusal is not None:
            return refusal

        with editing():
            # Load existing favorites
            data = load_favorites_strict()
            favorites = data['favorites']

            # The account may have gone while this request was on its way: a
            # course deleted meanwhile has taken its favourites with it already
            # (`favorites_store.drop_owned`). Its sign-in ended with it, and the
            # device keeps the star, as it does once the page has learnt of the
            # end. Without a device the star would belong to nobody.
            if asker.owner_id is not None and was_dropped(asker.owner_id, asker.owner_stamp):
                if not asker.device_id:
                    return jsonify({
                        'error': 'The sign-in has ended; sign in again',
                        'run_id': run_id
                    }), 401
                asker = _Asker(device_id=asker.device_id)

            # An entry from before favourites had owners belongs to nobody, and
            # anybody may take it back (`_may_change`). A star takes it back and
            # keeps the run under whoever stars it; nothing of the old entry
            # stays, the note included. Refused, as from 2026-11-15 until this
            # change, the run could no longer be kept by anybody.
            favorites = [fav for fav in favorites
                         if not (isinstance(fav, dict) and fav.get('run_id') == run_id
                                 and _ownerless(fav))]

            # A run is kept once. Whose it is decides the answer: the page that
            # kept it reads its star as lit, any other page is told that somebody
            # else keeps it.
            for fav in favorites:
                if isinstance(fav, dict) and fav.get('run_id') == run_id:
                    return jsonify({
                        'error': ('Favorite already exists' if _may_change(fav, asker)
                                  else 'This run is kept by another account or device'),
                        'run_id': run_id
                    }), 409

            # Create new favorite entry
            new_favorite = {
                'run_id': run_id,
                **_owner_fields(asker),
                'added_at': datetime.now().isoformat(),
                'thumbnail_url': _get_thumbnail_url(run_id, media_type),
                'media_type': media_type,
                'user_id': user_id,
                'user_note': user_note,
                'note_level': level,
                'source_view': source_view
            }

            # Add to beginning of list (most recent first)
            favorites.insert(0, new_favorite)
            data['favorites'] = favorites

            # Save
            if not save_favorites(data):
                return jsonify({'error': 'Failed to save favorite'}), 500

        logger.info(f"[FAVORITES] Successfully added favorite: {run_id}")

        # Answered the way the listing answers, so the plate that appears the
        # moment a run is starred is the same plate a reload would give it.
        answer = _answer(new_favorite, asker)
        if media_type == 'image':
            answer.update(_picture_fields(run_id, recorder, level))
        elif media_type == 'canvas' and _canvas_label(recorder):
            answer['input_preview'] = _canvas_label(recorder)

        return jsonify({
            'success': True,
            'favorite': answer,
            'total': len(favorites)
        }), 201

    except Exception as e:
        logger.error(f"[FAVORITES] Error adding favorite: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': 'Failed to add favorite',
            'details': str(e)
        }), 500


@favorites_bp.route('/<run_id>', methods=['DELETE'])
def remove_favorite(run_id: str):
    """
    Remove a favorite by run_id.

    Args:
        run_id: Run ID to remove from favorites

    Query parameters:
        - device_id: The device that wants to remove it, where no account
          is signed in. Only whoever kept a favourite may remove it (see
          `_may_change`).

    Returns:
        200: Favorite removed successfully
        403: Belongs to another account or device
        503: The place session could not be checked
        404: Favorite not found
        500: Server error

    Example:
        DELETE /api/favorites/run_abc123?device_id=abc123_2026-01-28
    """
    try:
        # Same source as GET reads it from — a DELETE carries no body.
        device_id = request.args.get('device_id')
        if place_session_unverified():
            return jsonify(_UNCHECKED), 503
        asker = _asker(device_id)

        logger.info(f"[FAVORITES] Removing favorite: {run_id} (device_id={device_id})")

        with editing():
            # Load existing favorites
            data = load_favorites_strict()
            favorites = data['favorites']

            target = next((f for f in favorites if f.get('run_id') == run_id), None)

            if target is None:
                return jsonify({
                    'error': 'Favorite not found',
                    'run_id': run_id
                }), 404

            if not _may_change(target, asker):
                logger.warning(
                    f"[FAVORITES] REFUSED delete of {run_id}: belongs to another account or device"
                )
                return jsonify({
                    'error': 'This favorite belongs to another account or device',
                    'run_id': run_id
                }), 403

            favorites = [f for f in favorites if f.get('run_id') != run_id]

            data['favorites'] = favorites

            # Save
            if not save_favorites(data):
                return jsonify({'error': 'Failed to save favorites'}), 500

        logger.info(f"[FAVORITES] Successfully removed favorite: {run_id}")

        return jsonify({
            'success': True,
            'run_id': run_id,
            'total': len(favorites)
        }), 200

    except Exception as e:
        logger.error(f"[FAVORITES] Error removing favorite: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': 'Failed to remove favorite',
            'details': str(e)
        }), 500


@favorites_bp.route('/<run_id>/keeper', methods=['GET'])
def get_keeper(run_id: str):
    """
    Whether a run is kept, and whether whoever asks may change it.

    A run is kept once. The "Mine" listing holds whoever asks alone and cannot
    say that somebody else keeps a run. A surface that writes into a run before
    keeping it (components/canvas/OutputDrawer.vue, `beforeFavorite`) asks here
    first, so that it does not write over the plate of somebody else's
    favourite. The answer names no owner and carries no note. The store is
    read strictly: a store that cannot be read answers 500, and the surface
    writes nothing.

    Query parameters:
        - device_id: The device that asks, where no account is signed in

    Returns:
        200: {"kept": bool, "may_change": bool}
        503: The place session could not be checked
        500: Server error
    """
    try:
        device_id = request.args.get('device_id')
        if place_session_unverified():
            return jsonify(_UNCHECKED), 503
        asker = _asker(device_id)
        fav = next((f for f in load_favorites_strict()['favorites']
                    if isinstance(f, dict) and f.get('run_id') == run_id), None)
        if fav is None:
            return jsonify({'kept': False, 'may_change': False}), 200
        return jsonify({'kept': True, 'may_change': _may_change(fav, asker)}), 200
    except Exception as e:
        logger.error(f"[FAVORITES] Error reading who keeps {run_id}: {e}")
        return jsonify({
            'error': 'Failed to read favorites',
            'details': str(e)
        }), 500


@favorites_bp.route('/<run_id>/restore', methods=['GET'])
def get_restore_data(run_id: str):
    """
    Get complete session data for restoring a favorite.

    Returns all data needed to restore the session state:
    - Original input text
    - Schema/config used
    - Settings (safety level, etc.)
    - Media URLs

    Args:
        run_id: Run ID to get restore data for

    Returns:
        200: Complete restore data
        403: At kids and youth, a run made at a looser level (`_restorable`)
        404: Run not found
        500: Server error

    Example:
        GET /api/favorites/run_abc123/restore
    """
    try:
        logger.info(f"[FAVORITES] Getting restore data for: {run_id}")

        # Load run data
        recorder = load_recorder(run_id, base_path=JSON_STORAGE_DIR)

        if not recorder:
            return jsonify({
                'error': 'Run not found',
                'run_id': run_id
            }), 404

        if not _restorable(recorder, resolve_safety_level()):
            return jsonify({
                'error': 'safety_blocked',
                'safety_block': safety_block(CHECKPOINT_RESULT, REASON_UNCHECKED,
                                             'unchecked', 'run'),
                'run_id': run_id,
            }), 403

        metadata = recorder.metadata
        entities = metadata.get('entities', [])

        # Build restore data
        restore_data = {
            'run_id': run_id,
            'schema': metadata.get('config_name', 'unknown'),
            'timestamp': metadata.get('timestamp', ''),
            'current_state': metadata.get('current_state', {}),
            'expected_outputs': metadata.get('expected_outputs', []),
            'user_id': metadata.get('user_id', 'anonymous')
        }

        # A Latent Lab run is not pipeline-shaped. What it holds is the
        # instrument's own object: the parameters it ran with, the ordered parts
        # it produced (the twenty-five steps of a denoising run, the cells of a
        # grid), and what came out. It travels ALONGSIDE the pipeline fields
        # below rather than instead of them, so a gallery entry stays one kind
        # of thing no matter which surface made it; the instrument reads what it
        # knows and ignores the rest. What a part MEANS is in the part's own
        # `meta` and is the instrument's business alone.
        instrument = build_instrument_object(run_id, base_path=JSON_STORAGE_DIR)
        if instrument:
            restore_data['instrument'] = instrument
            # What was asked, in the field every other consumer of a restore
            # reads (the gallery's drag-out builds its material from it). The
            # instrument object keeps the same text under `parameters`; this is
            # the same thing said in the platform's own word, not a second copy
            # to maintain.
            prompt = (instrument.get('parameters') or {}).get('prompt')
            if isinstance(prompt, str) and prompt:
                restore_data.setdefault('input_text', prompt)
            restore_data['schema'] = instrument.get('tool') or restore_data['schema']

        # Get input text
        for entity in entities:
            if entity['type'] == 'input':
                input_file = recorder.final_folder / entity['filename']
                if input_file.exists():
                    restore_data['input_text'] = input_file.read_text(encoding='utf-8')
                break

        # Get context prompt (meta-prompt/rules - user-editable!)
        for entity in entities:
            if entity['type'] == 'context_prompt':
                ctx_file = recorder.final_folder / entity['filename']
                if ctx_file.exists():
                    restore_data['context_prompt'] = ctx_file.read_text(encoding='utf-8')
                break

        # Get transformed/intercepted text if available
        for entity in entities:
            if entity['type'] == 'interception':
                output_file = recorder.final_folder / entity['filename']
                if output_file.exists():
                    restore_data['transformed_text'] = output_file.read_text(encoding='utf-8')
                break

        # Get English translation if available
        for entity in entities:
            if entity['type'] == 'translation_en':
                trans_file = recorder.final_folder / entity['filename']
                if trans_file.exists():
                    restore_data['translation_en'] = trans_file.read_text(encoding='utf-8')
                break

        # Include models used at each stage
        if 'models_used' in metadata:
            restore_data['models_used'] = metadata['models_used']

        # Get media URLs
        media_outputs = []
        # Numbered per KIND, as the media routes number them. Without the index
        # every picture of a run answered with the URL of the first — a Latent
        # Lab run that keeps both its plate and the render behind it reported
        # two outputs at one address.
        per_type = {}
        runtime_at = {}
        from my_app.utils.media_ref import is_media_entity
        for entity in entities:
            entity_type = entity.get('type', '')
            if is_media_entity(entity_type):
                media_type = entity_type.replace('output_', '')
            elif entity_type in RUNTIME_KINDS:
                # A sketch records under its runtime's own name, so this loop
                # used to walk past it and the run reported no output at all —
                # a kept sketch had nothing for the surface to place, and the
                # gallery drew an <img> at the run's thumbnail address.
                media_type = entity_type
            else:
                continue
            index = per_type.get(media_type, 0)
            per_type[media_type] = index + 1
            output = {
                'type': media_type,
                'filename': entity.get('filename'),
                'url': _media_url(run_id, media_type, index),
                'metadata': _public(entity).get('metadata', {})
            }
            if media_type in RUNTIME_KINDS and index:
                # One address, one entry. A runtime takes no index, and the
                # media route answers with the LAST sketch of the run, so a
                # folder that recorded several (three runs landed in one on
                # 2026-06-23) would otherwise report them all at that one
                # address — a list claiming outputs that cannot be reached.
                media_outputs[runtime_at[media_type]] = output
            else:
                if media_type in RUNTIME_KINDS:
                    runtime_at[media_type] = len(media_outputs)
                media_outputs.append(output)

        restore_data['media_outputs'] = media_outputs

        # The Canvas board, where the run is a kept workflow or an output of a
        # Canvas run: the Canvas opens it again (views/canvas_workflow.vue).
        canvas_workflow = _canvas_workflow_of(run_id, recorder)
        if canvas_workflow is not None:
            restore_data['canvas_workflow'] = canvas_workflow

        # Determine target view: use stored source_view if available, else heuristic
        data = load_favorites()
        fav_entry = next((f for f in data.get('favorites', []) if f.get('run_id') == run_id), None)

        if fav_entry and fav_entry.get('source_view'):
            restore_data['target_view'] = fav_entry['source_view']
        else:
            # Old favorites carry no source_view. The three pages this used to
            # choose between were removed on 2026-08-12; the working surface
            # takes both cases, so there is nothing left to distinguish.
            restore_data['target_view'] = 'x2x-flow'

        logger.info(f"[FAVORITES] Successfully retrieved restore data for: {run_id}")

        return jsonify(restore_data), 200

    except Exception as e:
        logger.error(f"[FAVORITES] Error getting restore data: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': 'Failed to get restore data',
            'details': str(e)
        }), 500


@favorites_bp.route('/<run_id>', methods=['PATCH'])
def update_favorite(run_id: str):
    """
    Update a favorite's metadata (e.g., user_note).

    Request body (JSON):
        - user_note: New note for the favorite (optional)
        - device_id: The device that wants to change it, where no account
          is signed in. Only whoever kept a favourite may change it (see
          `_may_change`).

    Returns:
        200: Favorite updated successfully
        403: Belongs to another account or device, or the note did not pass
             the intake check (`safety_block`)
        503: The place session could not be checked
        404: Favorite not found
        500: Server error

    Example:
        PATCH /api/favorites/run_abc123
        {"user_note": "My best creation!", "device_id": "abc123_2026-01-28"}
    """
    try:
        body = request.get_json() or {}
        # Same source as POST reads it from. Also accepted as a query
        # parameter, so DELETE and PATCH can be called the same way.
        device_id = body.get('device_id') or request.args.get('device_id')
        if place_session_unverified():
            return jsonify(_UNCHECKED), 503
        asker = _asker(device_id)

        logger.info(f"[FAVORITES] Updating favorite: {run_id} (device_id={device_id})")

        # Checked before the store is read, as in add_favorite.
        level = resolve_safety_level()
        refusal = _note_refusal(body, level)
        if refusal is not None:
            return refusal

        with editing():
            # Load existing favorites
            data = load_favorites_strict()
            favorites = data['favorites']

            target = next((f for f in favorites if f.get('run_id') == run_id), None)

            if target is None:
                return jsonify({
                    'error': 'Favorite not found',
                    'run_id': run_id
                }), 404

            if not _may_change(target, asker):
                logger.warning(
                    f"[FAVORITES] REFUSED update of {run_id}: belongs to another account or device"
                )
                return jsonify({
                    'error': 'This favorite belongs to another account or device',
                    'run_id': run_id
                }), 403

            if 'user_note' in body:
                target['user_note'] = body['user_note']
                target['note_level'] = level

            # Save
            if not save_favorites(data):
                return jsonify({'error': 'Failed to save favorites'}), 500

        logger.info(f"[FAVORITES] Successfully updated favorite: {run_id}")

        return jsonify({
            'success': True,
            'run_id': run_id
        }), 200

    except Exception as e:
        logger.error(f"[FAVORITES] Error updating favorite: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': 'Failed to update favorite',
            'details': str(e)
        }), 500


