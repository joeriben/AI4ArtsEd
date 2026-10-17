"""The account behind a provider key: whether there is one, and whether it
still holds credit.

Two places ask the same question. The availability check
(services/model_availability_service.py) reports a cloud output config as
unavailable when the provider its chunk names has no key, refuses the key, or
reports no credit left, and the Flow and the model choice of five instruments
switch it off then (docs/ARCHITECTURE PART 08). The settings page shows in
the API table whether that key is present and the account's balance
(routes/settings_routes.py, /frontier-image-accounts), the cause wherever the balance
could not be read, and which budget is used up where one is. The occasion is
Gemini 3 Pro Image, which runs through Mammouth AI whatever the external LLM
provider is set to. It can only be active where a key is present, and it is
off without credit as well (docs/DEVELOPMENT_DECISIONS.md). Both read this one
module.

Which provider's account is read, and how, stands in
config/llm_providers.json and not here: a provider whose
entry names an account API (`account_api`) is read by the reader of that API
(read_account), at the addresses its entry gives. 'litellm' is the account
route of a LiteLLM proxy (/user/info) at `credits_url`, which Mammouth AI
answers: the budget of the account for
the period, what the account has spent, what the key has spent, and the key's
own budget beside it. 'openrouter' is OpenRouter's key route (`key_url`) and
credits route (`credits_url`): what the key has spent in the current month,
and what is left of the
account's credits. Only a LiteLLM reading is judged. For a key of a
team, its own budget and its team's count in place of the account's, the
team's where the answer lists it. A key missing from a list of keys the answer
gives is held to none of these budgets; an answer without such a list holds
the key to the account's. Every other provider is judged by its key alone.
"""
import hashlib
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

import requests

from my_app.services.llm_providers import credentials, has_key, provider

logger = logging.getLogger(__name__)

# How long a reading of an account stands: the five minutes the availability
# service keeps ComfyUI's model list and the stations' state for.
READING_TTL_SECONDS = 300

# Mammouth AI answers through a LiteLLM proxy, which names the reason for a
# refusal in the body ({"error": {"type": ...}}, ProxyErrorTypes in
# litellm/proxy/_types.py). A 401 of any type counts as a refused key, and so
# does expired_key under any status; budget_exceeded says a budget is used up.
# Every other refusal leaves the balance unread and switches nothing off.
# LiteLLM's main branch (read 2026-09-24) checks neither the account's, the
# key's nor the team's budget on the account route, and answers it for a
# used-up account with 200 and a spend at or above the budget, which the
# balance catches. It does check there a budget set on the membership of the
# key's user in its team, where that budget with its active temporary increase
# is above 0, and refuses the route with budget_exceeded when it is used up,
# which the type catches; a team's default budget for its members it does not
# check there. The spend it reports is the one it last wrote to its database;
# the proxy counts a request against the budget before that, so a reading can
# still show credit for a while after the last of it was spent.
NO_CREDIT = "budget_exceeded"
KEY_EXPIRED = "expired_key"

_lock = threading.Lock()
# One reading at a time: a caller that finds another one reading waits for its
# answer, and reads again only where it asked for a fresh reading.
_reading_lock = threading.Lock()
# provider -> (when it was read, fingerprint of the key it was read with, reading)
_readings: Dict[str, Tuple[float, str, dict]] = {}


def _error_type(resp) -> str:
    """The proxy's name for a refusal, from an answer other than 200, or ''."""
    try:
        body = resp.json()
    except Exception:
        return ""
    err = body.get("error") if isinstance(body, dict) else None
    kind = err.get("type") if isinstance(err, dict) else None
    return kind if isinstance(kind, str) else ""


def _number(value) -> Optional[float]:
    """A figure of the answer, or None where the field holds none: LiteLLM
    writes budgets and spend as numbers, and anything else is no figure."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _left(budget, spend) -> Optional[float]:
    """What is left of a budget, unrounded, or None where no budget is set."""
    budget = _number(budget)
    if budget is None:
        return None
    return budget - (_number(spend) or 0.0)


def _linked(entry: dict, field: str):
    """A field of a key as LiteLLM applies it: the key's own value, else that
    of the budget linked to the key (litellm_budget_table), as
    LiteLLM_VerificationTokenView.__init__ in litellm/proxy/_types.py merges
    them."""
    value = entry.get(field)
    table = entry.get("litellm_budget_table")
    if value is None and isinstance(table, dict):
        value = table.get(field)
    return value


def _key_budget(entry: dict) -> Optional[float]:
    """The key's own budget as LiteLLM holds the key to it: its own or its
    linked budget's, raised by a temporary increase until that increase
    expires (temp_budget_increase and temp_budget_expiry in the key's
    metadata, _get_temp_budget_increase in
    litellm/proxy/auth/user_api_key_auth.py). An expiry LiteLLM cannot parse,
    on a key with a budget and both fields in its metadata, makes it refuse
    the key with 401, the account route included; one that reaches a reading
    adds no increase."""
    budget = _number(_linked(entry, "max_budget"))
    meta = entry.get("metadata")
    if budget is None or not isinstance(meta, dict):
        return budget
    increase = _number(meta.get("temp_budget_increase"))
    expiry = meta.get("temp_budget_expiry")
    if not increase or not isinstance(expiry, str):
        return budget
    try:
        until = datetime.fromisoformat(expiry)
    except ValueError:
        return budget
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    return budget + increase if until > datetime.now(timezone.utc) else budget


def _tightest(*limits) -> Optional[int]:
    """The lowest of the rate limits that are set, or None where none is."""
    given = [v for v in limits if isinstance(v, int) and not isinstance(v, bool)]
    return min(given) if given else None


def _litellm_reading(url: str, api_key: str) -> dict:
    """What the account behind a key on a LiteLLM proxy has spent, its budget
    for the period, what is left, and when the period starts again; what the
    key itself has spent, and when its own period starts again, where it has
    one; what is left of the key's own budget and of its team's, where one is
    set; and the lowest of the key's, the account's and its team's rate
    limits.

    Read from the account route (/user/info) at `url`. The Mammouth AI key
    this installation holds had no budget of its own when /key/info was read
    on 2026-09-23 (max_budget,
    budget_id and litellm_budget_table null), so the settings routes, which
    read /key/info until that day, showed no balance while the account had
    one. The account's answer lists its keys as well, each under the SHA-256
    of the key, which is how LiteLLM stores a key, and the teams of the
    account. The entry of this key gives what it has spent (`key_spend`, None
    where the answer lists no entry for it or the entry holds no figure), its
    own budget, its team and its rate limits; the entry of its team gives the
    team's budget, where the answer lists the team. The API Management tab
    shows `key_spend` as the spend: the account's spend covers every key on
    the account. LiteLLM sets a key's spend back to zero
    where the key has a budget period of its own, when that period starts
    again; that period can differ from the account's. `key_unlisted` is True
    where the answer lists the account's keys and this one is not among them,
    as after a rotation, while the proxy still takes the old key for the new
    one; an answer without a list of keys leaves it False. LiteLLM holds a key
    to its own rate limits, the account's and its team's at once, so the
    lowest of these three is the one given.

    What is left is kept unrounded, so that a balance of a fraction of a cent
    still counts as one; the pages round it for display.

    `status` carries the HTTP code of an answer that gave no reading: the code
    of a refusal, or 200 for an answer that was no JSON or had no account in
    it. `error_type` carries the proxy's name for a refusal where the body
    names one, so that a refused key and a used-up account can be told from a
    reading that failed on the way. `error` never carries an exception's text:
    requests writes the header it could not send into it, and that header
    holds the key.
    """
    try:
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        if resp.status_code != 200:
            reading = {"error": f"HTTP {resp.status_code}", "status": resp.status_code}
            kind = _error_type(resp)
            if kind:
                reading["error"] += f" ({kind})"
                reading["error_type"] = kind
            return reading

        try:
            body = resp.json()
        except ValueError as e:
            return {"error": type(e).__name__, "status": 200}
        info = body.get("user_info") if isinstance(body, dict) else None
        if not isinstance(info, dict):
            return {"error": "no user_info in the answer", "status": 200}
        token = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
        keys = body.get("keys")
        own = next((k for k in (keys if isinstance(keys, list) else [])
                    if isinstance(k, dict) and k.get("token") == token), {})
        team_id = own.get("team_id")
        teams = body.get("teams")
        team = next((t for t in (teams if isinstance(teams, list) else [])
                     if team_id and isinstance(t, dict) and t.get("team_id") == team_id), {})
        spend = _number(info.get("spend")) or 0.0
        key_spend = _number(own.get("spend"))
        key_budget = _key_budget(own)
        return {
            "spend": round(spend, 4),
            "max_budget": _number(info.get("max_budget")),
            "remaining": _left(info.get("max_budget"), spend),
            "key_spend": None if key_spend is None else round(key_spend, 4),
            "key_budget_reset_at": own.get("budget_reset_at"),
            "key_budget_duration": own.get("budget_duration"),
            "key_remaining": _left(key_budget, own.get("spend")),
            "key_unlisted": isinstance(keys, list) and not own,
            "team_key": bool(team_id),
            "team_remaining": _left(team.get("max_budget"), team.get("spend")),
            "budget_reset_at": info.get("budget_reset_at"),
            "budget_duration": info.get("budget_duration"),
            "rpm_limit": _tightest(_linked(own, "rpm_limit"), info.get("rpm_limit"), team.get("rpm_limit")),
            "tpm_limit": _tightest(_linked(own, "tpm_limit"), info.get("tpm_limit"), team.get("tpm_limit")),
            "error": None,
        }
    except requests.Timeout:
        return {"error": "timeout"}
    except Exception as e:
        return {"error": type(e).__name__}


def _refusal_message(resp) -> str:
    """The provider's sentence for a refusal, from an answer other than 200
    ({"error": {"message": ...}}, as OpenRouter writes it), on one line, or
    ''."""
    try:
        body = resp.json()
    except Exception:
        return ""
    err = body.get("error") if isinstance(body, dict) else None
    message = err.get("message") if isinstance(err, dict) else None
    return " ".join(message.split())[:200] if isinstance(message, str) else ""


def _openrouter_get(url: str, api_key: str):
    """One of OpenRouter's two routes: (its `data`, None), or (None, a
    reading that names why there is none). An exception is named by its
    class alone: requests writes the header it could not send into its
    text, and that header holds the key."""
    try:
        resp = requests.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=10)
    except requests.Timeout:
        return None, {"error": "timeout"}
    except Exception as e:
        return None, {"error": type(e).__name__}
    if resp.status_code != 200:
        failed = {"error": f"HTTP {resp.status_code}", "status": resp.status_code}
        message = _refusal_message(resp)
        if message:
            failed["error"] += f" ({message})"
        return None, failed
    try:
        body = resp.json()
    except ValueError as e:
        return None, {"error": type(e).__name__, "status": 200}
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        return None, {"error": "no data in the answer", "status": 200}
    return data, None


def _openrouter_reading(key_url: str, credits_url: str, api_key: str) -> dict:
    """What the key has spent in the current UTC month (`key_spend`, from
    data.usage_monthly of the key route at `key_url`), and what is left of
    the credits the account has bought (`remaining`, data.total_credits less
    data.total_usage of the credits route at `credits_url`, unrounded).
    OpenRouter's API reference, read on 2026-09-26, answers the key route to
    the key itself and the credits route to a management key only; where the
    credits route refuses the key or gives no figures, `account_error` names
    why and `remaining` is left out. Only the balance is given of the
    account: what was bought and what was used over its lifetime are account
    internals and stay off the platform's pages. `error` and `status` name
    why the key route gave no reading, as for a LiteLLM reading, with
    OpenRouter's sentence for a refusal where it gives one; `error` never
    carries an exception's text. On 2026-09-26 the credits route answered
    the key held here, which the key route marks `is_management_key` false,
    on the eu host."""
    own, failed = _openrouter_get(key_url, api_key)
    if failed:
        return failed
    reading = {"key_spend": _number(own.get("usage_monthly")), "error": None}
    account, failed = _openrouter_get(credits_url, api_key)
    if failed:
        reading["account_error"] = failed["error"]
        return reading
    bought = _number(account.get("total_credits"))
    used = _number(account.get("total_usage"))
    if bought is None or used is None:
        reading["account_error"] = "no credits in the answer"
    else:
        reading["remaining"] = bought - used
    return reading


# The account APIs a provider's entry can name (`account_api` in
# config/llm_providers.json): the reader of each, and the addresses from the
# entry it reads.
LITELLM = "litellm"
_READERS = {LITELLM: _litellm_reading, "openrouter": _openrouter_reading}
_ADDRESSES = {LITELLM: ("credits_url",), "openrouter": ("key_url", "credits_url")}


def read_account(name: str, api_key: str) -> Optional[dict]:
    """What a provider reports about the account behind a key, and about the
    key, read by the reader of the account API its entry names; None for a
    provider whose entry names none this module reads. A reading carries
    only the fields the provider's API reports; a field it holds as None is
    reported empty (an account without a budget, say)."""
    entry = provider(name) or {}
    api = entry.get("account_api")
    reader = _READERS.get(api)
    if reader is None:
        return None
    urls = [entry.get(field) for field in _ADDRESSES[api]]
    for field, url in zip(_ADDRESSES[api], urls):
        if not url:
            return {"error": f"no {field} for {name} in config/llm_providers.json"}
    return reader(*urls, api_key)


def _fingerprint(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _kept(name: str, fp: str) -> Optional[dict]:
    """The reading that still stands for this key, or None."""
    with _lock:
        kept = _readings.get(name)
    if kept and kept[1] == fp and time.monotonic() - kept[0] < READING_TTL_SECONDS:
        return kept[2]
    return None


def account(name: str, fresh: bool = False) -> dict:
    """{'has_key', 'judged', 'refused', 'no_credit', 'used_up', 'balance',
    'error'} for a provider.

    `has_key` is presence, as llm_providers.has_key says it, looked at every
    time; the key is taken where the run takes it, the environment variable
    first and then the key file. `refused` is True where the provider answered
    the key with 401 or named it expired. `no_credit` is True where it named
    a budget used up, and where a budget that binds this key is used up, as
    LiteLLM's main branch checks them (litellm/proxy/auth/auth_checks.py, read
    2026-09-24): the account's budget and the key's own at a spend at or above
    the budget, a team's at a spend above it. `used_up` names the first of the
    three that binds the key and is used up, in that order ('account', 'key',
    'team'), for the settings row, and is None otherwise. A key that belongs
    to a team is held to its own budget and its team's, and to the account's
    only where the proxy is set to, which is off by default. A key missing
    from the keys the answer lists is not held to the account's budget, since
    nothing says whether it belongs to a team; an answer without a list of
    keys says nothing of the key either, and the check judges it as a key of
    no team, by the account's budget. A team the answer does not list is not
    judged. A key set to be throttled past its budget
    (throttle_on_budget_exceeded) counts as used up here: the answer carries
    no throttle percentage.

    Not judged are the budgets LiteLLM checks beside these three: those for a
    time window (budget_limits, whose spend within the window the answer does
    not carry), those per model (model_max_budget, which LiteLLM matches to
    the model a request names through several spellings; the key's own can
    answer with a fallback model instead of a refusal), that of a model access
    group, those of an organisation, a project, a tag, an end user and the
    proxy itself, which the answer does not carry, and those of a provider or
    a deployment in LiteLLM's router (litellm/router_strategy/budget_limiter.py).
    Not judged either is the budget of the key's user as a member of its team,
    though the answer carries one set on the membership
    (teams[].team_memberships[].litellm_budget_table): LiteLLM refuses the
    account route itself when such a budget, with its active temporary
    increase, is above 0 and used up, and `no_credit` follows the refusal; one
    that with its active temporary increase is 0 or less, and a team's default
    budget for its members (team_member_budget_id in the team's metadata), it
    does not check on the account route.

    Judged (`judged`) is only a provider whose entry names the LiteLLM
    account API; every other provider is judged by its key alone. `balance`
    is what is left on the account, for the settings row. It is None without
    a key, for a provider that is not judged, for an account without a
    budget, and wherever the reading failed; `error` then names why: the HTTP
    status, with the proxy's name for the refusal where it gives one,
    "timeout", the class of an exception, or an English sentence of
    read_account or of the LiteLLM reader (no address in the provider table,
    no account in the answer).

    The reading goes over the network and stands for READING_TTL_SECONDS while
    the key stays the same. One reading is kept per provider: a new key is
    read at the next question, and so is the old one when it comes back. A key
    saved in the settings goes into the key file, and the environment
    variable, where it is set, comes before it, for the run as for this check.
    One reading runs at a time. `fresh` reads regardless, for the settings
    page, where the operator looks at the balance.
    """
    judged = (provider(name) or {}).get("account_api") == LITELLM
    if not has_key(name):
        return {"has_key": False, "judged": judged, "refused": False, "no_credit": False,
                "used_up": None, "balance": None, "error": None}
    if not judged:
        return {"has_key": True, "judged": False, "refused": False, "no_credit": False,
                "used_up": None, "balance": None, "error": None}

    key = credentials(name, quiet=True)[1]
    fp = _fingerprint(key)
    reading = None if fresh else _kept(name, fp)
    if reading is None:
        with _reading_lock:
            # Another caller may have read it while this one waited.
            reading = None if fresh else _kept(name, fp)
            if reading is None:
                reading = read_account(name, key)
                with _lock:
                    _readings[name] = (time.monotonic(), fp, reading)
                if reading.get("error"):
                    logger.warning(f"[PROVIDER-ACCOUNT] {name}: balance not read ({reading['error']})")
                elif reading.get("key_unlisted"):
                    logger.warning(f"[PROVIDER-ACCOUNT] {name}: the account's answer does not list this "
                                   "key; no budget is judged for it")
    kind = reading.get("error_type")
    error = reading.get("error")
    used_up = None
    if not error:
        held_to_account = not reading.get("team_key") and not reading.get("key_unlisted")
        account_left = reading.get("remaining") if held_to_account else None
        key_left = reading.get("key_remaining")
        team_left = reading.get("team_remaining")
        if account_left is not None and account_left <= 0:
            used_up = "account"
        elif key_left is not None and key_left <= 0:
            used_up = "key"
        elif team_left is not None and team_left < 0:
            used_up = "team"
    return {
        "has_key": True,
        "judged": True,
        "refused": reading.get("status") == 401 or kind == KEY_EXPIRED,
        "no_credit": kind == NO_CREDIT or used_up is not None,
        "used_up": used_up,
        "balance": None if error else reading.get("remaining"),
        "error": error,
    }


def usable(name: str) -> bool:
    """Whether a cloud config that sends its request to this provider can run:
    a key is present, the provider has neither refused it nor named a budget
    used up, and none of the budgets account() judges is used up. A balance
    that could not be read for another reason leaves the config usable; a run
    against an account without credit then fails at the provider, and the
    backend reports the provider's HTTP status
    (schemas/engine/backend_router.py)."""
    a = account(name)
    return a["has_key"] and not a["refused"] and not a["no_credit"]


def forget() -> None:
    """Drop every reading, so that the next question reads again. The tests
    use it. ?force_refresh=true on /api/models/availability leaves the
    readings alone: anyone can send it, and it must not make this server call
    a provider with the operator's key at will."""
    with _lock:
        _readings.clear()
