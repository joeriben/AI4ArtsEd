#!/usr/bin/env python3
"""Which providers reach which of the platform's models.

The platform names its models once, bare, in config/model_register.json -- bare
because the same model arrives here through whichever provider is configured.
This script asks every provider that has a credential on this machine for its
catalogue and writes down which of those names each one can reach, as
config/model_providers.json.

The answer is COMMITTED. A provider's catalogue URL does not change, and neither
does the id it gives a model that is already published, so an installation does
not have to ask anybody anything before it can offer a model list. Running this
script is how the file is brought forward when a model enters the register or a
provider renames one; it is not a step in anybody's setup.

Two halves, and the script only ever writes one of them:

  reach    -- what the catalogues answered, rewritten on every run.
  declared -- what a catalogue cannot answer, kept by hand and never touched
              here. A provider that gives a model an id the register's name does
              not match stands there with the SOURCE that says the two are the
              same model. Mistral calls Mistral Large 3 "mistral-large-2512",
              and nothing in its catalogue says so; the model card does.

A provider that did not answer is recorded WITH its reason, so a short list says
why it is short instead of reading as a provider that offers nothing -- and it
KEEPS what the last run that reached it wrote for it, with that run's date
(`kept_from`). The file is brought forward from whichever machine runs this,
and no machine holds every key: a run with one key on it would otherwise empty
the file for the other providers.
"""
import json
import sys
from datetime import date
from pathlib import Path

DEVSERVER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DEVSERVER))

import requests  # noqa: E402

from my_app.services.llm_providers import (  # noqa: E402
    MESSAGES, credentials, names as provider_names, provider as provider_entry,
)

REGISTER = DEVSERVER / "config" / "model_register.json"
TARGET = DEVSERVER / "config" / "model_providers.json"

# Every provider that keeps a key, from the provider table. The OpenAI-style
# ones answer /v1/models beside /v1/chat/completions and wrap the list in
# "data"; Anthropic answers /v1/models as well but authenticates with x-api-key
# and its own version header. Bedrock keeps no key file and has no catalogue
# of this shape, so it is not asked.
PROVIDERS = [n for n in provider_names() if (provider_entry(n) or {}).get("key_file")]

# No read limit. A catalogue is a fixed document rather than a generation, but a
# cap here would still be a cap, and the platform sets none on a provider call
# anywhere.
CONNECT_TIMEOUT = 10


def catalogue(provider: str) -> tuple:
    """(ids, reason). ids is None where the catalogue did not arrive."""
    dialect = (provider_entry(provider) or {}).get("dialect")
    try:
        api_url, key = credentials(provider, quiet=True)
    except Exception as e:
        return None, f"credentials unreadable: {e}"
    if not key:
        return None, "no credential on this machine"

    if dialect == MESSAGES:
        url = api_url.rsplit("/messages", 1)[0] + "/models"
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
    else:
        url = api_url.rsplit("/chat/completions", 1)[0] + "/models"
        headers = {"Authorization": f"Bearer {key}"}

    try:
        r = requests.get(url, headers=headers, timeout=(CONNECT_TIMEOUT, None))
    except Exception as e:
        return None, f"catalogue unreachable: {e}"
    if not r.ok:
        return None, f"catalogue answered HTTP {r.status_code}"
    try:
        data = r.json()
    except Exception as e:
        return None, f"catalogue is not JSON: {e}"

    items = data.get("data") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return None, "catalogue carries no list"
    ids = []
    for it in items:
        i = it.get("id") if isinstance(it, dict) else it
        if isinstance(i, str) and i:
            ids.append(i)
    return ids, ""


def main() -> int:
    register = json.loads(REGISTER.read_text())
    names = list(register.get("models", {}))

    previous = {}
    read_at = None
    if TARGET.exists():
        previous = json.loads(TARGET.read_text())
        read_at = TARGET.stat().st_mtime_ns
    # Never rewritten here. What a catalogue cannot say is somebody's reading of
    # a model card, and a script that regenerated it would drop that reading on
    # every run.
    declared = previous.get("declared", {})

    previous_reach = previous.get("reach") if isinstance(previous.get("reach"), dict) else {}
    previous_state = previous.get("providers") if isinstance(previous.get("providers"), dict) else {}

    reach = {name: {} for name in names}
    providers_state = {}

    for provider in PROVIDERS:
        ids, reason = catalogue(provider)
        if ids is None:
            # What the last run that reached this provider wrote stands, for the
            # register's models of today; the date it stands from travels with it.
            kept = 0
            for name in names:
                prev = previous_reach.get(name)
                path = prev.get(provider) if isinstance(prev, dict) else None
                if isinstance(path, str) and path:
                    reach[name][provider] = path
                    kept += 1
            state = previous_state.get(provider)
            kept_from = ((state.get("kept_from") if isinstance(state, dict) else None)
                         or previous.get("generated") or "")
            providers_state[provider] = {"answered": False, "reason": reason}
            if kept:
                providers_state[provider]["kept"] = kept
                if kept_from:
                    providers_state[provider]["kept_from"] = kept_from
            if kept:
                print(f"{provider}: {reason}; {kept} of the register kept from "
                      f"{kept_from or 'an earlier run without a date'}")
            else:
                print(f"{provider}: {reason}")
            continue
        providers_state[provider] = {"answered": True, "catalogue_size": len(ids)}
        by_bare = {}
        for i in ids:
            by_bare.setdefault(i.split("/")[-1].lower(), i)
        found = 0
        for name in names:
            hit = by_bare.get(name.lower())
            if hit:
                reach[name][provider] = hit
                found += 1
        print(f"{provider}: {len(ids)} entries, {found} of the register reached")

    out = {
        "_note": [
            "Which provider reaches which of the platform's models. Generated by",
            "scripts/build_model_providers.py and committed, so an installation",
            "offers the list without asking any provider anything.",
            "",
            "Keys under 'reach' are the BARE model names of model_register.json.",
            "The value is the id THAT provider wants, verbatim -- the prefix in",
            "front of it is what makes it a platform model id.",
            "",
            "'declared' is kept by hand and no run of the script touches it: a",
            "provider whose id the register's name cannot match stands there with",
            "the source that says the two are the same model.",
            "",
            "A provider under 'providers' with answered: false did not answer on",
            "the day this file was generated. Its reason is recorded, so a short",
            "list says why it is short -- and its entries under 'reach' are what",
            "the last run that reached it wrote, from the day 'kept_from' names.",
        ],
        "generated": date.today().isoformat(),
        "providers": providers_state,
        "reach": {k: v for k, v in reach.items() if v},
        "declared": declared,
    }
    # The checkout is shared. 'declared' and the kept entries come from the
    # file as it was read at the top; a file that changed since was written
    # by somebody else, and this run refuses rather than writes over it.
    now = TARGET.stat().st_mtime_ns if TARGET.exists() else None
    if now != read_at:
        print(f"\n{TARGET} changed while this ran; nothing written. Run it again.")
        return 1
    TARGET.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(f"\n-> {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
