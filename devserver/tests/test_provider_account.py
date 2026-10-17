#!/usr/bin/env python3
"""
A cloud output config runs through the provider its chunk names. For Gemini 3
Pro Image through Mammouth AI the config can only be active where a key is
present, and it is off without credit as well (docs/DEVELOPMENT_DECISIONS.md).
These tests hold that rule as the code makes it -- a key the provider
refuses counts as none, the key's own budget counts beside the account's, for
a key of a team its own and its team's in place of the account's, and a
balance that could not be read leaves the config on -- without asking the
network anything.

Run: python3 -m pytest devserver/tests/test_provider_account.py -q
"""
import ast
import asyncio
import hashlib
import sys
import threading
import time
import warnings

import pytest
import requests

from file_modules import DEVSERVER

sys.path.insert(0, str(DEVSERVER))

from my_app.services import provider_account as pa  # noqa: E402


@pytest.fixture(autouse=True)
def _no_readings_across_tests():
    pa.forget()
    yield
    pa.forget()


def _mammouth(monkeypatch, reading, key="k-1"):
    """A Mammouth key (or none) and the reading its account gives; returns the
    list of keys the account was read with."""
    monkeypatch.setattr(pa, "has_key", lambda name: bool(key))
    monkeypatch.setattr(pa, "credentials", lambda name, quiet=False: ("", key))
    calls = []

    def fake(name, api_key):
        calls.append(api_key)
        return dict(reading)

    monkeypatch.setattr(pa, "read_account", fake)
    return calls


def _answer(status, body):
    """An answer of the account route, as requests hands it back."""
    class Answer:
        status_code = status

        def json(self):
            if isinstance(body, Exception):
                raise body
            return body

    return Answer()


def _unread(error):
    return {"has_key": True, "judged": True, "refused": False, "no_credit": False,
            "used_up": None, "balance": None, "error": error}


def _user_info(key, account=(1088.25, 404.5), own=(None, 32.7), team_id=None,
               team=None, first=False, listed=True):
    """/user/info as LiteLLM answers it: the account, its keys, each under the
    SHA-256 of the key, and its teams. `own` is the budget and spend of `key`,
    `team` the budget and spend of its team. The other key on the account
    carries a budget of its own that is used up, and limits of its own, so a
    reading that took the wrong entry shows it. `first` puts this key before
    the other one, and `listed=False` leaves it out."""
    this = {"token": hashlib.sha256(key.encode("utf-8")).hexdigest(), "team_id": team_id,
            "max_budget": own[0], "spend": own[1], "rpm_limit": 30, "tpm_limit": 1500000}
    other = {"token": "0" * 64, "team_id": "t-other", "max_budget": 40.0, "spend": 40.5,
             "rpm_limit": 50, "tpm_limit": 2000000}
    keys = ([this, other] if first else [other, this]) if listed else [other]
    teams = [{"team_id": "t-other", "max_budget": 5.0, "spend": 9.0}]
    if team is not None:
        teams.append({"team_id": team_id, "max_budget": team[0], "spend": team[1]})
    return {"user_info": {"max_budget": account[0], "spend": account[1],
                          "rpm_limit": None, "tpm_limit": None},
            "keys": keys, "teams": teams}


def _served(monkeypatch, answer, key="sk-1"):
    """A Mammouth key, and the account route answering with `answer` for it."""
    monkeypatch.setattr(pa, "has_key", lambda name: True)
    monkeypatch.setattr(pa, "credentials", lambda name, quiet=False: ("", key))
    monkeypatch.setattr(pa.requests, "get", lambda url, **kw: _answer(200, answer))


def test_no_key_is_not_usable(monkeypatch):
    calls = _mammouth(monkeypatch, {"remaining": 10.0, "error": None}, key="")
    assert pa.usable("mammouth") is False
    assert calls == []


def test_a_refused_key_is_not_usable(monkeypatch):
    _mammouth(monkeypatch, {"error": "HTTP 401", "status": 401})
    assert pa.usable("mammouth") is False
    assert pa.account("mammouth") == {"has_key": True, "judged": True, "refused": True,
                                      "no_credit": False, "used_up": None, "balance": None,
                                      "error": "HTTP 401"}


def test_an_expired_key_is_not_usable(monkeypatch):
    """LiteLLM's main branch answers an expired key with 401 and the type
    expired_key; the type counts under any status, which the 400 shows."""
    for status in (401, 400):
        pa.forget()
        _mammouth(monkeypatch, {"error": f"HTTP {status} (expired_key)", "status": status,
                                "error_type": pa.KEY_EXPIRED})
        assert pa.usable("mammouth") is False, status
        assert pa.account("mammouth")["refused"] is True, status


def test_a_used_up_balance_is_not_usable(monkeypatch):
    for remaining in (0.0, -3.2):
        pa.forget()
        _mammouth(monkeypatch, {"remaining": remaining, "error": None})
        assert pa.usable("mammouth") is False, remaining


def test_an_account_refused_as_over_budget_is_not_usable(monkeypatch):
    """A proxy that refuses the account route itself for want of credit sends
    no balance; the type of the refusal says it. LiteLLM's main branch sends
    such a refusal with 422."""
    _mammouth(monkeypatch, {"error": "HTTP 422 (budget_exceeded)", "status": 422,
                            "error_type": pa.NO_CREDIT})
    assert pa.usable("mammouth") is False
    a = pa.account("mammouth")
    assert a["no_credit"] is True and a["refused"] is False and a["balance"] is None
    assert a["used_up"] is None
    assert a["error"] == "HTTP 422 (budget_exceeded)"


def test_a_balance_left_is_usable(monkeypatch):
    _mammouth(monkeypatch, {"remaining": 683.62, "error": None})
    assert pa.usable("mammouth") is True
    assert pa.account("mammouth")["balance"] == pytest.approx(683.62)


def test_a_used_up_key_budget_is_not_usable(monkeypatch):
    """A key can carry a budget of its own in the Mammouth account; used up,
    it stops the key while the account still has credit. The settings row
    still shows the account's balance."""
    _served(monkeypatch, _user_info("sk-1", own=(40.0, 40.2)))
    a = pa.account("mammouth")
    assert (a["no_credit"], a["used_up"]) == (True, "key")
    assert a["balance"] == pytest.approx(683.75)
    assert pa.usable("mammouth") is False


def test_a_key_without_a_budget_of_its_own_follows_the_account(monkeypatch):
    _served(monkeypatch, _user_info("sk-1", account=(1088.25, 1090.5)))
    a = pa.account("mammouth")
    assert (a["no_credit"], a["used_up"]) == (True, "account")
    assert pa.usable("mammouth") is False


def test_a_key_budget_with_credit_left_keeps_it_on(monkeypatch):
    _served(monkeypatch, _user_info("sk-1", own=(40.0, 10.0)))
    assert pa.account("mammouth")["used_up"] is None
    assert pa.usable("mammouth") is True


def test_a_budget_linked_to_the_key_is_its_budget(monkeypatch):
    """A key linked to a budget (budget_id) keeps max_budget null in its own
    row; LiteLLM holds it to the linked budget, and to that budget's rate
    limits where the key sets none."""
    answer = _user_info("sk-1", own=(None, 40.0))
    answer["keys"][1].update(budget_id="b-1", rpm_limit=None,
                             litellm_budget_table={"max_budget": 40.0, "rpm_limit": 20})
    _served(monkeypatch, answer)
    a = pa.account("mammouth")
    assert (a["no_credit"], a["used_up"]) == (True, "key")
    assert pa.read_account("mammouth", "sk-1")["rpm_limit"] == 20
    pa.forget()
    answer["keys"][1]["max_budget"] = 50.0
    _served(monkeypatch, answer)
    assert pa.usable("mammouth") is True


def test_a_temporary_increase_counts_until_it_expires(monkeypatch):
    """LiteLLM raises a key's budget by temp_budget_increase until
    temp_budget_expiry; an expiry without a zone is read as UTC. An expiry
    LiteLLM cannot parse, on a key with a budget and both fields in its
    metadata, makes it refuse the key with 401; one that reaches a reading adds
    no increase."""
    answer = _user_info("sk-1", own=(40.0, 45.0))
    for expiry, on in (("2999-01-01T00:00:00+00:00", True),
                       ("2999-01-01T00:00:00", True),
                       ("2000-01-01T00:00:00+00:00", False),
                       ("not a date", False)):
        pa.forget()
        answer["keys"][1]["metadata"] = {"temp_budget_increase": 10.0, "temp_budget_expiry": expiry}
        _served(monkeypatch, answer)
        assert pa.usable("mammouth") is on, expiry


def test_a_team_key_is_held_to_its_own_budget_and_its_teams(monkeypatch):
    """LiteLLM holds a team's key to its own budget and the team's, and to the
    account's only where the proxy is set to: a used-up account leaves it on,
    a used-up budget of its own or of its team does not. A team is used up
    only past its budget (spend > budget), a key at it (spend >= budget)."""
    _served(monkeypatch, _user_info("sk-1", account=(1088.25, 1090.5), team_id="t-1"))
    assert pa.usable("mammouth") is True
    pa.forget()
    _served(monkeypatch, _user_info("sk-1", own=(10.0, 10.0), team_id="t-1"))
    assert pa.usable("mammouth") is False
    pa.forget()
    _served(monkeypatch, _user_info("sk-1", team_id="t-1", team=(100.0, 100.5)))
    assert pa.usable("mammouth") is False
    pa.forget()
    _served(monkeypatch, _user_info("sk-1", team_id="t-1", team=(100.0, 100.0)))
    assert pa.usable("mammouth") is True


def test_the_budget_used_up_is_named(monkeypatch):
    """The settings row names the budget that switched the model off."""
    _served(monkeypatch, _user_info("sk-1", team_id="t-1", team=(100.0, 100.5)))
    assert pa.account("mammouth")["used_up"] == "team"
    pa.forget()
    _served(monkeypatch, _user_info("sk-1"))
    assert pa.account("mammouth")["used_up"] is None


def test_a_key_the_answer_does_not_list_is_not_held_to_the_account(monkeypatch):
    """After a rotation the proxy still takes the old key for the new one, and
    the answer lists the new one only; nothing then says whether the key
    belongs to a team, and a team's key is not held to the account's budget."""
    _served(monkeypatch, _user_info("sk-1", account=(1088.25, 1090.5), listed=False))
    a = pa.account("mammouth")
    assert (a["no_credit"], a["used_up"]) == (False, None)
    assert a["balance"] == pytest.approx(-2.25)
    assert pa.usable("mammouth") is True


def test_an_answer_without_a_list_of_keys_holds_the_key_to_the_account(monkeypatch):
    """An answer without a list of keys says nothing about this one; the
    check judges it as a key of no team, by the account's budget."""
    without_list = _user_info("sk-1", account=(1088.25, 1090.5))
    without_list["keys"] = None
    without_field = _user_info("sk-1", account=(1088.25, 1090.5))
    del without_field["keys"]
    for answer in (without_list, without_field):
        pa.forget()
        _served(monkeypatch, answer)
        a = pa.account("mammouth")
        assert (a["no_credit"], a["used_up"]) == (True, "account")
        assert pa.read_account("mammouth", "sk-1")["key_unlisted"] is False


def test_a_team_the_answer_does_not_list_is_not_judged(monkeypatch):
    _served(monkeypatch, _user_info("sk-1", team_id="t-1"))
    assert pa.read_account("mammouth", "sk-1")["team_remaining"] is None
    assert pa.usable("mammouth") is True


def test_a_key_outside_a_team_is_not_judged_by_a_team(monkeypatch):
    """The other key's team is used up; this key belongs to none."""
    _served(monkeypatch, _user_info("sk-1"))
    b = pa.read_account("mammouth", "sk-1")
    assert (b["team_key"], b["team_remaining"]) == (False, None)
    assert pa.usable("mammouth") is True


def test_a_budget_of_zero_is_a_budget(monkeypatch):
    """LiteLLM blocks at a spend at or above the budget, so a budget of 0
    stops the key; it is no missing budget."""
    _served(monkeypatch, _user_info("sk-1", account=(0, 0)))
    assert pa.usable("mammouth") is False
    pa.forget()
    _served(monkeypatch, _user_info("sk-1", own=(0, 0)))
    assert pa.usable("mammouth") is False


def test_a_used_up_key_budget_counts_on_an_account_without_one(monkeypatch):
    _served(monkeypatch, _user_info("sk-1", account=(None, 404.5), own=(40.0, 40.0)))
    a = pa.account("mammouth")
    assert (a["balance"], a["no_credit"]) == (None, True)


def test_a_fraction_of_a_cent_is_credit(monkeypatch):
    """What is left is judged unrounded: LiteLLM still serves a spend below
    the budget, however little is left."""
    _served(monkeypatch, _user_info("sk-1", account=(100.0, 99.99999)))
    assert pa.usable("mammouth") is True


def test_an_account_without_a_budget_is_usable(monkeypatch):
    _served(monkeypatch, _user_info("sk-1", account=(None, 404.5)))
    a = pa.account("mammouth")
    assert (a["balance"], a["error"], a["no_credit"]) == (None, None, False)
    assert pa.usable("mammouth") is True


def test_an_unread_balance_leaves_it_usable(monkeypatch):
    for failure in ({"error": "timeout"},
                    {"error": "ConnectionError"},
                    {"error": "no user_info in the answer", "status": 200},
                    {"error": "HTTP 400", "status": 400},
                    {"error": "HTTP 403", "status": 403},
                    {"error": "HTTP 429", "status": 429},
                    {"error": "HTTP 503", "status": 503}):
        pa.forget()
        _mammouth(monkeypatch, failure)
        assert pa.usable("mammouth") is True, failure
        assert pa.account("mammouth") == _unread(failure["error"])


def test_a_reading_is_kept_and_a_new_key_is_read_afresh(monkeypatch):
    calls = _mammouth(monkeypatch, {"remaining": 5.0, "error": None})
    pa.usable("mammouth")
    pa.usable("mammouth")
    assert calls == ["k-1"]
    monkeypatch.setattr(pa, "credentials", lambda name, quiet=False: ("", "k-2"))
    pa.usable("mammouth")
    assert calls == ["k-1", "k-2"]
    pa.account("mammouth", fresh=True)
    assert calls == ["k-1", "k-2", "k-2"]


def test_a_removed_key_is_not_usable_within_the_reading(monkeypatch):
    _mammouth(monkeypatch, {"remaining": 5.0, "error": None})
    assert pa.usable("mammouth") is True
    monkeypatch.setattr(pa, "has_key", lambda name: False)
    assert pa.usable("mammouth") is False


def test_a_reading_runs_out(monkeypatch):
    calls = _mammouth(monkeypatch, {"remaining": 5.0, "error": None})
    pa.usable("mammouth")
    real = time.monotonic
    monkeypatch.setattr(pa.time, "monotonic", lambda: real() + pa.READING_TTL_SECONDS + 1)
    pa.usable("mammouth")
    assert calls == ["k-1", "k-1"]


def test_one_reading_at_a_time(monkeypatch):
    """Callers that arrive while the account is being read wait for that
    reading instead of asking the provider again."""
    monkeypatch.setattr(pa, "has_key", lambda name: True)
    monkeypatch.setattr(pa, "credentials", lambda name, quiet=False: ("", "k-1"))
    calls = []

    def slow(name, api_key):
        calls.append(api_key)
        time.sleep(0.2)
        return {"remaining": 5.0, "error": None}

    monkeypatch.setattr(pa, "read_account", slow)
    threads = [threading.Thread(target=pa.usable, args=("mammouth",)) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert calls == ["k-1"]


def test_other_providers_are_judged_by_the_key_alone(monkeypatch):
    """Judged by an account reading is a provider whose entry names the
    LiteLLM account API; OpenRouter's entry names an account API of its own,
    whose reading the API Management tab shows and nothing judges."""
    monkeypatch.setattr(pa, "has_key", lambda name: name in ("openai", "openrouter"))
    monkeypatch.setattr(pa, "read_account",
                        lambda name, k: pytest.fail(f"an account reading for {name}"))
    assert pa.usable("openai") is True
    assert pa.usable("openrouter") is True
    assert pa.usable("ionos") is False


def test_which_account_is_read_stands_in_the_provider_table(monkeypatch):
    """read_account takes the account API and its address from the
    provider's entry in config/llm_providers.json."""
    seen = []
    monkeypatch.setattr(pa, "_READERS", {"litellm": lambda url, k: seen.append(url) or {"error": None}})
    entries = {"a": {"account_api": "litellm", "credits_url": "https://a.example/user/info"},
               "b": {"account_api": "litellm"},
               "c": {"credits_url": "https://c.example/credits"},
               "d": {"account_api": "unknown", "credits_url": "https://d.example"}}
    monkeypatch.setattr(pa, "provider", lambda name: entries.get(name))
    assert pa.read_account("a", "k") == {"error": None}
    assert seen == ["https://a.example/user/info"]
    assert pa.read_account("b", "k") == {"error": "no credits_url for b in config/llm_providers.json"}
    for name in ("c", "d", "e"):
        assert pa.read_account(name, "k") is None, name
    assert seen == ["https://a.example/user/info"]


def test_the_provider_table_names_the_account_apis_it_has_readers_for():
    from my_app.services.llm_providers import names, provider
    named = {n: provider(n).get("account_api") for n in names() if provider(n).get("account_api")}
    assert set(named.values()) <= set(pa._READERS)
    for n, api in named.items():
        for field in pa._ADDRESSES[api]:
            assert provider(n).get(field), (n, field)
    assert named.get("mammouth") == pa.LITELLM


def _openrouter(key=(200, {"data": {"usage_monthly": 1.25, "usage": 9.0}}),
                credits=(200, {"data": {"total_credits": 10, "total_usage": 2.5}})):
    """OpenRouter's key route and credits route, answering as given; returns
    the list of (address, headers) asked."""
    asked = []

    def get(url, **kw):
        asked.append((url, kw))
        status, body = key if url.endswith("/key") else credits
        return _answer(status, body)

    return asked, get


def test_an_openrouter_reading_gives_the_keys_month_and_the_balance(monkeypatch):
    asked, get = _openrouter()
    monkeypatch.setattr(pa.requests, "get", get)
    assert pa.read_account("openrouter", "k") == {"key_spend": 1.25, "remaining": 7.5, "error": None}
    assert [url.rsplit("/", 1)[1] for url, _ in asked] == ["key", "credits"]
    assert all(kw["headers"]["Authorization"] == "Bearer k" and "params" not in kw for _, kw in asked)


def test_an_openrouter_balance_refused_to_the_key_is_named(monkeypatch):
    """OpenRouter's reference answers the credits route to a management key
    only; the key's own figure stays."""
    refusal = {"error": {"code": 403, "message": "Only management keys can\n perform this operation"}}
    _, get = _openrouter(credits=(403, refusal))
    monkeypatch.setattr(pa.requests, "get", get)
    assert pa.read_account("openrouter", "k") == {
        "key_spend": 1.25, "error": None,
        "account_error": "HTTP 403 (Only management keys can perform this operation)"}
    for body in ({"data": {"total_credits": 10}}, {"data": None}, {}, []):
        _, get = _openrouter(credits=(200, body))
        monkeypatch.setattr(pa.requests, "get", get)
        b = pa.read_account("openrouter", "k")
        assert "remaining" not in b and b["key_spend"] == 1.25, body
        assert b["account_error"] in ("no credits in the answer", "no data in the answer"), body


def test_an_openrouter_credits_route_that_times_out_keeps_the_keys_figure(monkeypatch):
    def get(url, **kw):
        if url.endswith("/credits"):
            raise requests.exceptions.ReadTimeout("read timed out, Bearer sk-secret")
        return _answer(200, {"data": {"usage_monthly": 1.25}})

    monkeypatch.setattr(pa.requests, "get", get)
    assert pa.read_account("openrouter", "k") == {
        "key_spend": 1.25, "error": None, "account_error": "timeout"}


def test_only_a_judged_account_shows_a_balance_row(monkeypatch):
    """account() says whether it judged the provider's account, so that the
    settings row does not read "unlimited" for one it never read."""
    monkeypatch.setattr(pa, "has_key", lambda name: True)
    monkeypatch.setattr(pa, "read_account", lambda name, k: pytest.fail(f"read {name}"))
    assert pa.account("openrouter", fresh=True)["judged"] is False
    _mammouth(monkeypatch, {"remaining": 5.0, "error": None})
    assert pa.account("mammouth", fresh=True)["judged"] is True
    monkeypatch.setattr(pa, "has_key", lambda name: False)
    assert pa.account("mammouth")["judged"] is True
    assert pa.account("openai")["judged"] is False


def test_an_openrouter_key_route_that_gives_nothing_is_no_reading(monkeypatch):
    asked, get = _openrouter(key=(401, {"error": {"code": 401, "message": "No auth credentials found"}}))
    monkeypatch.setattr(pa.requests, "get", get)
    assert pa.read_account("openrouter", "k") == {
        "error": "HTTP 401 (No auth credentials found)", "status": 401}
    assert len(asked) == 1
    _, get = _openrouter(key=(200, ValueError("no JSON")))
    monkeypatch.setattr(pa.requests, "get", get)
    assert pa.read_account("openrouter", "k") == {"error": "ValueError", "status": 200}
    _, get = _openrouter(key=(200, {"data": {"usage": 3}}))
    monkeypatch.setattr(pa.requests, "get", get)
    assert pa.read_account("openrouter", "k")["key_spend"] is None

    def leaky(url, **kw):
        raise requests.exceptions.InvalidHeader("in header value: 'Bearer sk-secret\\n'")

    monkeypatch.setattr(pa.requests, "get", leaky)
    assert pa.read_account("openrouter", "sk-secret\n") == {"error": "InvalidHeader"}


def test_billing_gives_the_period_of_the_key(monkeypatch):
    answer = _user_info("sk-1", own=(None, 12.0))
    answer["keys"][1].update(budget_duration="30d", budget_reset_at="2026-10-01T00:00:00Z")
    monkeypatch.setattr(pa.requests, "get", lambda url, **kw: _answer(200, answer))
    b = pa.read_account("mammouth", "sk-1")
    assert (b["key_budget_duration"], b["key_budget_reset_at"]) == ("30d", "2026-10-01T00:00:00Z")
    assert b["key_spend"] == pytest.approx(12.0)
    monkeypatch.setattr(pa.requests, "get", lambda url, **kw: _answer(
        200, _user_info("sk-1", own=(None, 12.0))))
    b = pa.read_account("mammouth", "sk-1")
    assert (b["key_budget_duration"], b["key_budget_reset_at"]) == (None, None)


def test_billing_reads_the_account_not_the_key(monkeypatch):
    seen = {}

    def get(url, **kw):
        seen["url"] = url
        seen["kw"] = kw
        return _answer(200, {"user_info": {"spend": 404.5, "max_budget": 1088.25,
                                           "budget_reset_at": "2026-10-01T00:00:00Z",
                                           "budget_duration": "30d"}})

    monkeypatch.setattr(pa.requests, "get", get)
    b = pa.read_account("mammouth", "k")
    assert b["error"] is None
    assert b["remaining"] == pytest.approx(683.75)
    assert seen["url"].endswith("/user/info")
    # The key travels in the header, never in the address.
    assert seen["kw"]["headers"]["Authorization"] == "Bearer k"
    assert "params" not in seen["kw"]


def test_billing_finds_this_key_among_the_accounts_keys(monkeypatch):
    for first in (False, True):
        monkeypatch.setattr(pa.requests, "get", lambda url, **kw: _answer(
            200, _user_info("sk-1", own=(40.0, 38.5), first=first)))
        b = pa.read_account("mammouth", "sk-1")
        assert b["remaining"] == pytest.approx(683.75), first
        assert b["key_remaining"] == pytest.approx(1.5), first
        # What this key has spent, not the account's spend or the other key's.
        assert b["key_spend"] == pytest.approx(38.5), first
        assert b["team_key"] is False, first
        # The limits are this key's, not those of the other key on the account.
        assert (b["rpm_limit"], b["tpm_limit"]) == (30, 1500000), first


def test_billing_without_this_key_in_the_list_reads_the_account(monkeypatch):
    answer = _user_info("sk-1", listed=False)
    answer["user_info"].update(rpm_limit=60, tpm_limit=900000)
    monkeypatch.setattr(pa.requests, "get", lambda url, **kw: _answer(200, answer))
    b = pa.read_account("mammouth", "sk-1")
    assert (b["key_remaining"], b["key_spend"], b["team_key"], b["team_remaining"]) == (
        None, None, False, None)
    assert b["key_unlisted"] is True
    assert (b["rpm_limit"], b["tpm_limit"]) == (60, 900000)
    assert b["remaining"] == pytest.approx(683.75)


def test_billing_gives_the_tightest_limits(monkeypatch):
    """LiteLLM holds a key to its own rate limits, the account's and its
    team's at once; the lowest of each binds."""
    answer = _user_info("sk-1")
    answer["user_info"].update(rpm_limit=60, tpm_limit=900000)
    monkeypatch.setattr(pa.requests, "get", lambda url, **kw: _answer(200, answer))
    b = pa.read_account("mammouth", "sk-1")
    assert b["key_unlisted"] is False
    assert (b["rpm_limit"], b["tpm_limit"]) == (30, 900000)
    answer = _user_info("sk-1", team_id="t-1", team=(100.0, 1.0))
    answer["teams"][-1].update(rpm_limit=10, tpm_limit=None)
    monkeypatch.setattr(pa.requests, "get", lambda url, **kw: _answer(200, answer))
    b = pa.read_account("mammouth", "sk-1")
    assert (b["rpm_limit"], b["tpm_limit"]) == (10, 1500000)


def test_billing_takes_the_accounts_limits_where_the_key_sets_none(monkeypatch):
    answer = _user_info("sk-1")
    answer["keys"][1].update(rpm_limit=None, tpm_limit=None)
    answer["user_info"].update(rpm_limit=60, tpm_limit=900000)
    monkeypatch.setattr(pa.requests, "get", lambda url, **kw: _answer(200, answer))
    b = pa.read_account("mammouth", "sk-1")
    assert (b["rpm_limit"], b["tpm_limit"]) == (60, 900000)


def test_billing_reads_the_account_past_malformed_entries(monkeypatch):
    """A field that holds no number, or a list that is none, is no figure; the
    account's balance is read all the same."""
    for keys in (5, "keys", {"token": "x"}, None):
        answer = _user_info("sk-1")
        answer["keys"] = keys
        monkeypatch.setattr(pa.requests, "get", lambda url, **kw: _answer(200, answer))
        b = pa.read_account("mammouth", "sk-1")
        assert b["error"] is None, keys
        assert b["remaining"] == pytest.approx(683.75), keys
        assert b["key_remaining"] is None, keys
        assert b["key_spend"] is None, keys
        assert b["key_unlisted"] is False, keys
    answer = _user_info("sk-1", own=("40", "50"), team_id="t-1", team=("5", 9.0))
    monkeypatch.setattr(pa.requests, "get", lambda url, **kw: _answer(200, answer))
    b = pa.read_account("mammouth", "sk-1")
    assert (b["key_remaining"], b["key_spend"], b["team_remaining"]) == (None, None, None)
    assert b["remaining"] == pytest.approx(683.75)


def test_billing_reads_a_spend_past_the_budget(monkeypatch):
    monkeypatch.setattr(pa.requests, "get", lambda url, **kw: _answer(
        200, {"user_info": {"spend": 1090.5, "max_budget": 1088.25}}))
    assert pa.read_account("mammouth", "k")["remaining"] == pytest.approx(-2.25)


def test_billing_carries_the_code_of_a_refusal(monkeypatch):
    """A key the proxy does not know, as LiteLLM's main branch answers it."""
    monkeypatch.setattr(pa.requests, "get", lambda url, **kw: _answer(
        401, {"error": {"message": "Authentication Error, Invalid proxy server token passed.",
                        "type": "token_not_found_in_db", "param": "key", "code": "401"}}))
    b = pa.read_account("mammouth", "k")
    assert b["status"] == 401
    assert b["error"] == "HTTP 401 (token_not_found_in_db)"


def test_billing_names_the_proxys_refusal(monkeypatch):
    monkeypatch.setattr(pa.requests, "get", lambda url, **kw: _answer(
        422, {"error": {"message": "Budget has been exceeded!", "type": "budget_exceeded",
                        "param": None, "code": "422"}}))
    b = pa.read_account("mammouth", "k")
    assert b["status"] == 422
    assert b["error_type"] == pa.NO_CREDIT
    assert b["error"] == "HTTP 422 (budget_exceeded)"


def test_billing_without_a_readable_refusal_keeps_the_code(monkeypatch):
    monkeypatch.setattr(pa.requests, "get", lambda url, **kw: _answer(503, ValueError("no JSON")))
    b = pa.read_account("mammouth", "k")
    assert b == {"error": "HTTP 503", "status": 503}


def test_billing_of_an_answer_that_is_no_json_keeps_the_code(monkeypatch):
    monkeypatch.setattr(pa.requests, "get", lambda url, **kw: _answer(200, ValueError("no JSON")))
    assert pa.read_account("mammouth", "k") == {"error": "ValueError", "status": 200}
    _mammouth(monkeypatch, {"error": "ValueError", "status": 200})
    assert pa.usable("mammouth") is True


def test_billing_without_user_info_is_no_reading(monkeypatch):
    for body in ({"user_info": None}, {}, []):
        monkeypatch.setattr(pa.requests, "get", lambda url, **kw: _answer(200, body))
        b = pa.read_account("mammouth", "k")
        assert b["error"] == "no user_info in the answer", body
        assert "remaining" not in b


def test_billing_never_carries_the_exception_text(monkeypatch):
    """requests writes the header it could not send into its exception, and
    that header holds the key."""
    def get(url, **kw):
        raise requests.exceptions.InvalidHeader(
            "Invalid leading whitespace, reserved character(s), or return character(s) "
            "in header value: 'Bearer sk-secret\\n'")

    monkeypatch.setattr(pa.requests, "get", get)
    b = pa.read_account("mammouth", "sk-secret\n")
    assert b == {"error": "InvalidHeader"}

    def slow(url, **kw):
        raise requests.exceptions.ReadTimeout("read timed out, Bearer sk-secret")

    monkeypatch.setattr(pa.requests, "get", slow)
    assert pa.read_account("mammouth", "sk-secret") == {"error": "timeout"}


def test_force_refresh_leaves_the_account_reading(monkeypatch):
    """The unauthenticated ?force_refresh=true on /api/models/availability
    clears the local caches, and the account reading stays. The route runs as
    it is; the checks it makes are faked, so nothing is asked of ComfyUI or
    the GPU service."""
    from flask import Flask

    from my_app.routes.config_routes import config_bp
    from my_app.services.model_availability_service import ModelAvailabilityService

    calls = _mammouth(monkeypatch, {"remaining": 5.0, "error": None})

    async def check_all_configs(self):
        pa.usable("mammouth")
        return {}

    async def get_gpu_service_status(self, force_refresh=False):
        return {"gpu_service_reachable": False}

    monkeypatch.setattr(ModelAvailabilityService, "check_all_configs", check_all_configs)
    monkeypatch.setattr(ModelAvailabilityService, "get_gpu_service_status", get_gpu_service_status)
    monkeypatch.setattr(ModelAvailabilityService, "_is_comfyui_reachable", lambda self: False)
    app = Flask(__name__)
    app.register_blueprint(config_bp)
    client = app.test_client()
    for _ in range(2):
        assert client.get("/api/models/availability?force_refresh=true").status_code == 200
    assert calls == ["k-1"]


# What any module may use of provider_account besides the calls is_open
# judges (usable(), and account() without a fresh reading): reading the names
# of two refusals. Every other name is refused.
_OPEN = {"NO_CREDIT", "KEY_EXPIRED"}
# What a module may bind at its top: a name bound there can be imported from
# that module under any other, and the check would lose it. Neither function
# is among them: a fresh reading is one argument of account() away, and the
# module's own names are one attribute of either away.
_MODULE_LEVEL = {"NO_CREDIT", "KEY_EXPIRED"}
# The routes that may read on demand, behind the settings login.
_GUARDED_USES = {
    ("my_app/routes/settings_routes.py", "api_usage", "read_account"),
    ("my_app/routes/settings_routes.py", "frontier_image_accounts", "account"),
}
_MODULE = "provider_account"
# The decorators by which Flask takes a function as a view.
_ROUTE_DECORATORS = ("route", "get", "post", "put", "patch", "delete", "endpoint")


def _server_modules():
    """The modules read: those at the top of devserver, and every module in
    my_app and schemas."""
    yield from sorted(DEVSERVER.glob("*.py"))
    for part in ("my_app", "schemas"):
        yield from sorted((DEVSERVER / part).rglob("*.py"))


def _is_settings_route(fn) -> bool:
    """A route behind the settings login. Flask registers a function as the
    decorators below its route decorator have made it, and a decorator below
    the guard receives it unguarded, so the guard is the lowest decorator and
    every route decorator stands above it."""
    names = [ast.unparse(d.func if isinstance(d, ast.Call) else d) for d in fn.decorator_list]
    routes = [i for i, n in enumerate(names) if n.split(".")[-1] in _ROUTE_DECORATORS]
    guards = [i for i, n in enumerate(names) if n.split(".")[-1] == "require_settings_auth"]
    return bool(routes) and bool(guards) and max(routes) < max(guards) == len(names) - 1


def _module_uses(source: str):
    """Each use of provider_account in one module beyond what is open to
    every module (a call of account() without a fresh reading, a call of
    usable(), a reading of the two names of a refusal): (what, the settings
    route whose body holds it, or None). The module is found under whatever
    name it is imported, under its own name wherever that stands (a star
    import of its package binds it), through any attribute of that name, its
    package's among them, and in a string handed to a call, a subscript or a
    keyword, alone or as the literal part of an f-string, whose path, dotted
    or with a colon, runs through it. A star import, the module handed on as
    a value, arguments unpacked into account(), usable or account taken
    otherwise than called, a name of a refusal written or deleted on the
    module, and an import of the module or of any of its names but those in
    _MODULE_LEVEL at the top of the module read ('import <name>') are uses
    too; an import in a function stands at the top where a global statement
    anywhere in the module lists the name it binds.

    Out of its sight are a name computed at run time, a module path in a
    string that reaches a call, a subscript or a keyword otherwise than
    directly (held in a name or a default argument, packed in a tuple, a list
    or a dict, assembled by an expression: +, %, format(), join()), code in a
    string (exec, eval), a file path (runpy.run_path), a name reached through
    locals(), globals() or vars(), an object reached through the attributes
    of an object other than the module and its names (another function's
    __globals__, a view's __wrapped__), a route registered without a
    decorator (add_url_rule), and a guard of that name that guards nothing;
    where one of these hands the module's name, or a path through it written
    with dots or a colon, as a string directly to a call, a subscript or a
    keyword, it is found all the same. A local name that shadows an imported
    one counts as the imported one, and an alias bound to two names of the
    module, or to the module and one of its names, counts as the module."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        tree = ast.parse(source)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}

    def in_function(node) -> bool:
        while node in parents:
            node = parents[node]
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                return True
        return False

    # A name a function declares global and imports is bound at the top.
    declared = {name for node in ast.walk(tree) if isinstance(node, ast.Global) for name in node.names}

    def at_top(node, bound) -> bool:
        return not in_function(node) or bound in declared

    names, modules, found = {}, {_MODULE}, []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if (node.module or "").split(".")[-1] == _MODULE:
                    if alias.name == "*":
                        found.append(("*", node))
                        continue
                    bound = alias.asname or alias.name
                    names[bound] = alias.name if names.get(bound, alias.name) == alias.name else _MODULE
                    if alias.name not in _MODULE_LEVEL and at_top(node, bound):
                        found.append((f"import {alias.name}", node))
                elif alias.name == _MODULE:
                    modules.add(alias.asname or alias.name)
                    if at_top(node, alias.asname or alias.name):
                        found.append((f"import {_MODULE}", node))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[-1] == _MODULE:
                    modules.add(alias.asname or alias.name)
                    if at_top(node, alias.asname or alias.name.split(".")[0]):
                        found.append((f"import {_MODULE}", node))
    # A local name bound both to the module and to one of its names counts as
    # the module.
    for bound in modules & names.keys():
        names[bound] = _MODULE

    def is_module(node) -> bool:
        return ((isinstance(node, ast.Name) and node.id in modules)
                or (isinstance(node, ast.Attribute) and node.attr == _MODULE))

    def fresh(call) -> bool:
        """Whether a call of account() asks for a fresh reading, or may."""
        if any(k.arg is None for k in call.keywords) or any(isinstance(a, ast.Starred) for a in call.args):
            return True
        given = [k.value for k in call.keywords if k.arg == "fresh"] + call.args[1:2]
        return any(not (isinstance(v, ast.Constant) and not v.value) for v in given)

    def is_open(node, what) -> bool:
        if isinstance(node, ast.Attribute) and not isinstance(node.ctx, ast.Load):
            return False
        parent = parents.get(node)
        if what == "account":
            return isinstance(parent, ast.Call) and parent.func is node and not fresh(parent)
        if what == "usable":
            return isinstance(parent, ast.Call) and parent.func is node
        return what in _OPEN

    def handed_to(node):
        """What a string stands in: its parent, or for the literal part of an
        f-string the f-string's parent."""
        parent = parents.get(node)
        return parents.get(parent) if isinstance(parent, ast.JoinedStr) else parent

    for node in ast.walk(tree):
        what = None
        if isinstance(node, ast.Name) and node.id in names:
            what = names[node.id]
        elif isinstance(node, ast.Attribute) and is_module(node.value):
            what = node.attr
        elif is_module(node):
            parent = parents.get(node)
            if not (isinstance(parent, ast.Attribute) and parent.value is node):
                what = _MODULE
        elif (isinstance(node, ast.Constant) and isinstance(node.value, str)
              and _MODULE in node.value.replace(":", ".").split(".")
              and isinstance(handed_to(node), (ast.Call, ast.Subscript, ast.keyword))):
            what = _MODULE
        if what and not is_open(node, what):
            found.append((what, node))

    def route(node):
        """The settings route whose body holds the node; a default argument
        or a decorator runs at import and belongs to none."""
        child = node
        while child in parents:
            parent = parents[child]
            if (isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and child in parent.body and _is_settings_route(parent)):
                return parent.name
            child = parent
        return None

    return [(what, route(node)) for what, node in found]


def test_only_settings_routes_read_the_account_on_demand():
    """A reading stands five minutes so that nobody can make this server call
    Mammouth AI with the operator's key at will. A fresh reading, a call of
    forget(), or a hand in the module's own state, behind a route anyone can
    reach or at import, would undo that. So a module may call usable() and
    account() without a fresh reading and read the two refusals; it calls
    forget() nowhere, whatever else it uses of the module stands in a route
    behind the settings login (frontier_image_accounts, and api_usage, which
    reads the accounts on every call), and at its top it binds nothing of the module but
    the two refusals. Every module in my_app and schemas and at the top of
    devserver is read; provider_account itself is held by the tests above."""
    guarded, loose = set(), []
    for path in _server_modules():
        rel = path.relative_to(DEVSERVER).as_posix()
        if rel == "my_app/services/provider_account.py":
            continue
        for what, route in _module_uses(path.read_text(encoding="utf-8")):
            if what == "forget" or route is None:
                loose.append((rel, what))
            else:
                guarded.add((rel, route, what))
    assert loose == []
    assert guarded == _GUARDED_USES


def test_the_policy_check_sees_what_it_guards_against():
    """The check above, on modules made up for it."""
    uses = _module_uses

    assert uses("from my_app.services.provider_account import forget as f\nf()\n") == [
        ("import forget", None), ("forget", None)]
    assert uses("import my_app.services.provider_account as pa\npa.forget()\n") == [
        ("import provider_account", None), ("forget", None)]
    assert uses("def v():\n    from my_app.services import provider_account as p\n"
                "    p.account('mammouth', True)\n") == [("account", None)]
    assert uses("def v():\n    from my_app.services import provider_account\n"
                "    provider_account.account('mammouth', fresh=False)\n"
                "    provider_account.account('mammouth')\n"
                "    provider_account.usable('mammouth')\n"
                "    return provider_account.NO_CREDIT, provider_account.KEY_EXPIRED\n") == []
    # At its top a module binds the two refusals, and nothing else.
    assert uses("from my_app.services.provider_account import NO_CREDIT, KEY_EXPIRED\n"
                "def v():\n    from my_app.services.provider_account import usable\n"
                "    return usable('mammouth'), NO_CREDIT, KEY_EXPIRED\n") == []
    assert uses("from my_app.services import provider_account\n") == [("import provider_account", None)]
    assert uses("from my_app.services.provider_account import account\n") == [("import account", None)]
    assert uses("from my_app.services.provider_account import usable\n") == [("import usable", None)]
    # A function that declares the name global imports it to the top.
    assert uses("def s():\n    global account\n"
                "    from my_app.services.provider_account import account\n") == [("import account", None)]
    assert uses("def s():\n    global pa\n"
                "    import my_app.services.provider_account as pa\n") == [("import provider_account", None)]
    assert uses("from my_app.services.provider_account import read_account as fetch\n") == [
        ("import read_account", None)]
    # Handed on instead of called, as api_usage hands it to a thread pool.
    assert uses("def v(pool):\n    from my_app.services.provider_account import read_account as ra\n"
                "    pool.submit(ra, 'mammouth', 'k')\n") == [("read_account", None)]
    # Reached otherwise than by a name imported from it.
    assert uses("from my_app.services.provider_account import *\nforget()\n") == [("*", None)]
    assert uses("import my_app.services\nmy_app.services.provider_account.forget()\n") == [("forget", None)]
    assert uses("from my_app.services import *\nprovider_account.forget()\n") == [("forget", None)]
    # One alias for two names of the module counts as the module.
    assert uses("def a():\n    from my_app.services.provider_account import forget as f\n    f()\n"
                "def b():\n    from my_app.services.provider_account import usable as f\n"
                "    return f('mammouth')\n") == [("provider_account", None), ("provider_account", None)]
    # One alias for the module and one of its names counts as the module too.
    assert uses("from my_app.services.provider_account import KEY_EXPIRED\n"
                "def v():\n    import my_app.services.provider_account as KEY_EXPIRED\n"
                "    x = KEY_EXPIRED\n    x.forget()\n") == [("provider_account", None)]
    # Writing or deleting a refusal's name on the module is a use.
    assert uses("def v():\n    from my_app.services import provider_account as pa\n"
                "    pa.NO_CREDIT = 'x'\n    del pa.KEY_EXPIRED\n") == [
        ("NO_CREDIT", None), ("KEY_EXPIRED", None)]
    assert uses("def v():\n    import my_app.services.provider_account\n"
                "    my_app.services.provider_account.READING_TTL_SECONDS = 0\n") == [
        ("READING_TTL_SECONDS", None)]
    assert uses("def v():\n    from my_app.services import provider_account as pa\n"
                "    getattr(pa, 'forget')()\n") == [("provider_account", None)]
    assert uses("import importlib\n"
                "importlib.import_module('my_app.services.provider_account').forget()\n") == [
        ("provider_account", None)]
    assert uses("import importlib\n"
                "importlib.import_module(name='my_app.services.provider_account').forget()\n") == [
        ("provider_account", None)]
    assert uses("import pkgutil\n"
                "pkgutil.resolve_name('my_app.services.provider_account:forget')()\n") == [
        ("provider_account", None)]
    assert uses("import pkgutil\n"
                "pkgutil.resolve_name('my_app.services.provider_account.forget')()\n") == [
        ("provider_account", None)]
    assert uses("import pkgutil\n"
                "pkgutil.resolve_name('my_app.services:provider_account.forget')()\n") == [
        ("provider_account", None)]
    assert uses("import importlib\n"
                "importlib.import_module(f'my_app.services.provider_account').forget()\n") == [
        ("provider_account", None)]
    assert uses("import sys\nsys.modules['my_app.services.provider_account'].forget()\n") == [
        ("provider_account", None)]
    assert uses("def v():\n    from my_app.services import provider_account as pa\n"
                "    pa._readings.clear()\n") == [("_readings", None)]
    assert uses("def v():\n    from my_app.services.provider_account import account\n"
                "    account('mammouth', **{'fresh': True})\n") == [("account", None)]
    # The judgement taken otherwise than called reaches the module's own names.
    assert uses("def v():\n    from my_app.services.provider_account import usable\n"
                "    usable.__globals__['forget']()\n") == [("usable", None)]
    assert uses("def v():\n    from my_app.services.provider_account import usable\n"
                "    getattr(usable, '__globals__')['forget']()\n") == [("usable", None)]
    assert uses("def v():\n    from my_app.services import provider_account as pa\n"
                "    pa.account.__globals__['forget']()\n") == [("account", None)]
    # Where the use stands: in the body of a route behind the settings login.
    guarded = ("@bp.route('/x')\n@require_settings_auth\ndef v():\n"
               "    from my_app.services.provider_account import account\n"
               "    def inner():\n        return account('mammouth', fresh=True)\n    return inner()\n")
    assert uses(guarded) == [("account", "v")]
    for decorator in ("@bp.get('/x')", "@bp.patch('/x')", "@bp.endpoint('x')"):
        assert uses(guarded.replace("@bp.route('/x')", decorator)) == [("account", "v")], decorator
    # The guard below the route decorator only: Flask registers the unguarded function.
    swapped = guarded.replace("@bp.route('/x')\n@require_settings_auth\n",
                              "@require_settings_auth\n@bp.route('/x')\n")
    assert uses(swapped) == [("account", None)]
    assert uses(swapped.replace("@bp.route('/x')", "@bp.patch('/x')")) == [("account", None)]
    # A second route decorator below the guard registers the unguarded function too.
    second = guarded.replace("@require_settings_auth\n", "@require_settings_auth\n@bp.route('/y')\n")
    assert uses(second) == [("account", None)]
    # A decorator below the guard receives the unguarded function.
    hooked = guarded.replace("@require_settings_auth\n", "@require_settings_auth\n@bp.before_app_request\n")
    assert uses(hooked) == [("account", None)]
    # A guard below the lowest route decorator covers every route above it.
    covered = guarded.replace("@bp.route('/x')\n", "@require_settings_auth\n@bp.route('/x')\n")
    assert uses(covered) == [("account", "v")]
    # A default argument runs at import, in no route.
    default = ("from my_app.services.provider_account import account\n"
               "@bp.route('/x')\n@require_settings_auth\n"
               "def v(a=account('mammouth', fresh=True)):\n    return a\n")
    assert uses(default) == [("import account", None), ("account", None)]
    # A comment or an unrelated name is no use.
    assert uses("# provider_account.forget()\ndef get_account(fresh=True):\n    pass\n"
                "get_account(fresh=True)\n") == []


def test_the_gemini_config_goes_off_without_an_account(monkeypatch):
    """The config the rows in the settings are about is judged by the account
    of the provider its chunk names, and the availability answer says so."""
    from my_app.services.model_availability_service import ModelAvailabilityService

    monkeypatch.setattr(pa, "usable", lambda name: False)
    off = ModelAvailabilityService(comfyui_base_url="http://127.0.0.1:1")
    assert off.api_provider("gemini_3_pro_image") == "mammouth"
    assert asyncio.run(off.check_config_availability("gemini_3_pro_image")) is False
    assert off.account_missing == {"gemini_3_pro_image"}

    monkeypatch.setattr(pa, "usable", lambda name: True)
    on = ModelAvailabilityService(comfyui_base_url="http://127.0.0.1:1")
    assert asyncio.run(on.check_config_availability("gemini_3_pro_image")) is True
    assert on.account_missing == set()


def test_the_gemini_config_goes_off_when_the_account_has_no_credit(monkeypatch):
    """account() and usable() run as they are; only the network reading is
    faked."""
    from my_app.services.model_availability_service import ModelAvailabilityService

    _mammouth(monkeypatch, {"error": "HTTP 422 (budget_exceeded)", "status": 422,
                            "error_type": pa.NO_CREDIT})
    svc = ModelAvailabilityService(comfyui_base_url="http://127.0.0.1:1")
    assert asyncio.run(svc.check_config_availability("gemini_3_pro_image")) is False
    assert svc.account_missing == {"gemini_3_pro_image"}


def test_the_availability_answer_names_the_provider_of_a_config_that_is_off(monkeypatch):
    """The sentence a surface shows for a config that is off names the
    provider its chunk sends to, from this answer."""
    from flask import Flask

    from my_app.routes.config_routes import config_bp
    from my_app.services.model_availability_service import ModelAvailabilityService

    monkeypatch.setattr(pa, "usable", lambda name: False)

    async def check_all_configs(self):
        return {"gemini_3_pro_image": await self.check_config_availability("gemini_3_pro_image")}

    async def get_gpu_service_status(self, force_refresh=False):
        return {"gpu_service_reachable": False}

    monkeypatch.setattr(ModelAvailabilityService, "check_all_configs", check_all_configs)
    monkeypatch.setattr(ModelAvailabilityService, "get_gpu_service_status", get_gpu_service_status)
    monkeypatch.setattr(ModelAvailabilityService, "_is_comfyui_reachable", lambda self: False)
    app = Flask(__name__)
    app.register_blueprint(config_bp)
    body = app.test_client().get("/api/models/availability").get_json()
    assert body["account_missing"] == ["gemini_3_pro_image"]
    assert body["account_provider"] == {"gemini_3_pro_image": "mammouth"}


def _settings_client():
    from flask import Flask

    from my_app.routes import settings_routes
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(settings_routes.settings_bp)
    return app.test_client()


def test_the_frontier_rows_come_from_the_configs(monkeypatch):
    """The rows under the key fields list every output config marked as a
    frontier image model, with the provider its chunk names; the account of
    each provider is read once."""
    asked = []

    def account(name, fresh=False):
        asked.append((name, fresh))
        return {"has_key": True, "judged": True, "refused": False, "no_credit": False,
                "used_up": None, "balance": 12.5, "error": None}

    monkeypatch.setattr(pa, "account", account)
    body = _settings_client().get("/api/settings/frontier-image-accounts").get_json()
    rows = {c["config_id"]: c for c in body["configs"]}
    assert "gemini_3_pro_image" in rows
    row = rows["gemini_3_pro_image"]
    assert row["provider"] == "mammouth"
    assert row["name"]["en"].startswith("Gemini 3 Pro Image")
    assert (row["has_key"], row["judged"], row["balance"], row["used_up"], row["error"]) == (
        True, True, 12.5, None, None)
    assert sorted(set(asked)) == sorted(asked)
    assert all(fresh for _, fresh in asked)


def test_the_api_usage_lists_an_account_for_every_key_in_a_key_file(monkeypatch):
    from my_app.routes import settings_routes as sr

    held = {"mammouth": "k-m", "openrouter": "k-o", "mistral": "k-x"}
    monkeypatch.setattr(sr, "key_in_file", lambda name: held.get(name, ""))
    readings = {"mammouth": {"spend": 1.0, "remaining": 9.0, "key_spend": 0.5, "error": None},
                "openrouter": {"remaining": 3.25, "error": None}}
    seen = []

    def read_account(name, key):
        seen.append((name, key))
        return readings.get(name)

    monkeypatch.setattr(pa, "read_account", read_account)
    body = _settings_client().get("/api/settings/api-usage").get_json()
    order = [n for n in sr.provider_names() if n in held and sr.key_file_path(n) is not None]
    assert [a["provider"] for a in body["accounts"]] == order
    assert {a["provider"]: a["reading"] for a in body["accounts"]} == {
        n: readings.get(n) for n in order}
    assert sorted(seen) == sorted((n, held[n]) for n in order)
    assert body["providers"]["mammouth"]["credits"] == {"remaining": 9.0}
    assert body["providers"]["openrouter"]["credits"] == {"remaining": 3.25}
    assert body["providers"]["mistral"] == {**body["providers"]["mistral"],
                                            "key_configured": True, "credits": None}
    assert all(not p["key_configured"] for n, p in body["providers"].items() if n not in held)
    assert "mammouth_billing" not in body


def test_a_config_without_a_provider_is_not_judged_by_an_account(monkeypatch):
    from my_app.services.model_availability_service import ModelAvailabilityService

    monkeypatch.setattr(pa, "usable", lambda name: pytest.fail(f"asked about {name}"))
    svc = ModelAvailabilityService(comfyui_base_url="http://127.0.0.1:1")
    assert svc.api_provider("p5js_code") is None
    assert asyncio.run(svc.check_config_availability("p5js_code")) is True
