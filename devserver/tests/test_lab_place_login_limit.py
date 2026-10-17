"""
The budget of the place login (lab/login_attempts.py).

Covers:
- The budget is 40 attempts, and one more every 30 seconds.
- An address that has spent its budget on codes that name no place is refused
  with 429, `retry_after` and the Retry-After header, before the lookup: for
  the right code, and for an entry that cannot be a code, as well. No session
  is made.
- Another address keeps its own budget; behind the tunnel (loopback peer) the
  address is Cloudflare's CF-Connecting-IP, from any other peer the header
  changes nothing; an IPv6 address counts by its /48, directly and behind the
  tunnel, an IPv4-mapped one as its IPv4. A loopback peer without a readable
  header is counted under its own address, and the log says so.
- A code that names an active place costs nothing: a success, and a right
  code of a closed course (403). A missing code (400) costs nothing either,
  and neither does an entry that cannot be a code (401), which reserves
  nothing and is looked up nowhere. A code of a removed place or of a
  deactivated account costs an attempt.
- The budget refills one attempt per interval and holds CAPACITY attempts at
  most; a wait is the whole seconds to the next attempt, rounded up, and one
  second where the level and that sum round apart, with nothing reserved.
- Parallel requests of one address cannot pass on the same last attempt,
  directly and through the route, and the logins of one address run side
  by side. A login at the last attempt waits for the lookup under way and is
  then answered from the budget: a lookup of its own where that code was
  right, the real wait where it was charged, and a lookup of its own as
  soon as the budget has regained an attempt. Another address is not held.
- A login is charged once, and a refused one never.
- A budget that has lost no attempt for CAPACITY * REFILL_SECONDS is dropped
  at the next login, the oldest first; a younger one stays.
- An app makes its budgets at its first place login and keeps them.
- No address is kept in plain or logged, and every set of budgets has a key
  of its own.

Run: python3 -m pytest devserver/tests/test_lab_place_login_limit.py -q
"""
import atexit
import os
import shutil
import sys
import datetime as _dt
import hashlib
import logging
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Redirect the lab DB to a throwaway file BEFORE importing the lab package.
_TMP_DIR = tempfile.mkdtemp(prefix="lab_limit_test_")
atexit.register(shutil.rmtree, _TMP_DIR, ignore_errors=True)
os.environ["AI4ARTSED_DB_PATH"] = str(Path(_TMP_DIR) / "lab_test.db")

import pytest
from flask import Flask

from my_app.lab.db import Base, engine, SessionLocal
from my_app.lab import models as M
from my_app.lab import login_attempts as LA
from my_app.lab.auth_service import hash_password
from my_app.routes import auth_routes
from my_app.routes.auth_routes import auth_bp
from my_app.routes.courses_routes import courses_bp
from my_app.utils.url_ids import install_row_id_converter

CAPACITY = LA.CAPACITY
REFILL = int(LA.REFILL_SECONDS)
DEVICE = "203.0.113.5"


@pytest.fixture(autouse=True)
def clean_schema():
    SessionLocal.remove()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    SessionLocal.remove()


class _Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    return _Clock()


def _bare_app():
    a = Flask(__name__)
    a.secret_key = "test-secret"
    install_row_id_converter(a)
    a.register_blueprint(auth_bp)
    a.register_blueprint(courses_bp)
    return a


@pytest.fixture
def app(clock):
    a = _bare_app()
    a.extensions[LA._EXTENSION] = LA.LoginAttempts(clock=clock)
    yield a
    SessionLocal.remove()


def _educator_with_open_course(app, places=1):
    """A signed-in educator, one open course with `places` places. Returns the
    educator's client, the course id and the codes, place 1 first."""
    db = SessionLocal()
    db.add(M.User(email="edu@example.org", role=M.Role.educator, display_name="Edu",
                  password_hash=hash_password("secret12"), is_active=True))
    db.commit()
    edu = app.test_client()
    assert edu.post("/api/auth/login", json={"identifier": "edu@example.org",
                                             "password": "secret12"}).status_code == 200
    cid = edu.post("/api/courses", json={"title": "C", "safety_level": "youth"}).get_json()["course"]["id"]
    until = _dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(hours=2)
    assert edu.put(f"/api/courses/{cid}/access", json={"until": until.isoformat()}).status_code == 200
    resp = edu.post(f"/api/courses/{cid}/places", json={"count": places})
    assert resp.status_code == 201
    issued = sorted(resp.get_json()["places"], key=lambda p: p["number"])
    return edu, cid, [p["code"] for p in issued]


def _wrong(codes, n):
    """n codes of the alphabet that name none of `codes`."""
    alphabet = "ACDEFGHJKMNPQRTUVWXY34679"
    out, i = [], 0
    while len(out) < n:
        c = "".join(alphabet[(i // len(alphabet) ** k) % len(alphabet)] for k in range(5))
        if c not in codes:
            out.append(c)
        i += 1
    return out


def _enter(client, code, peer=DEVICE, cf=None):
    headers = {"CF-Connecting-IP": cf} if cf is not None else {}
    return client.post("/api/auth/participant-login", json={"code": code},
                       headers=headers, environ_base={"REMOTE_ADDR": peer})


def _spend(client, codes, peer=DEVICE, cf=None, n=CAPACITY):
    for c in _wrong(codes, n):
        assert _enter(client, c, peer, cf).status_code == 401


def test_the_budget_is_forty_attempts_and_one_more_every_thirty_seconds():
    assert (LA.CAPACITY, LA.REFILL_SECONDS) == (40, 30)


def test_a_spent_budget_refuses_even_the_right_code(app):
    _, _, codes = _educator_with_open_course(app)
    device = app.test_client()
    _spend(device, codes)

    refused = _enter(device, _wrong(codes, CAPACITY + 1)[-1])
    assert refused.status_code == 429
    body = refused.get_json()
    assert body["error"] == "too_many_attempts"
    assert body["retry_after"] == REFILL
    assert refused.headers["Retry-After"] == str(REFILL)

    right = _enter(device, codes[0])
    assert right.status_code == 429
    assert _enter(device, "ACD").status_code == 429
    me = device.get("/api/auth/me", environ_base={"REMOTE_ADDR": DEVICE}).get_json()
    assert me["user"] is None


def test_an_empty_budget_answers_before_the_lookup(app, monkeypatch):
    _, _, codes = _educator_with_open_course(app)
    _spend(app.test_client(), codes)
    looked_up = []
    real = auth_routes.find_place

    def recorded(db, raw):
        looked_up.append(raw)
        return real(db, raw)
    monkeypatch.setattr(auth_routes, "find_place", recorded)
    assert _enter(app.test_client(), codes[0]).status_code == 429
    assert looked_up == []


def test_another_address_keeps_its_own_budget(app):
    _, _, codes = _educator_with_open_course(app)
    _spend(app.test_client(), codes)
    other = app.test_client()
    assert _enter(other, codes[0], peer="203.0.113.6").status_code == 200


def test_behind_the_tunnel_the_address_is_cloudflares(app):
    _, _, codes = _educator_with_open_course(app)
    _spend(app.test_client(), codes, peer="127.0.0.1", cf="198.51.100.7")
    assert _enter(app.test_client(), codes[0], peer="127.0.0.1", cf="198.51.100.7").status_code == 429
    assert _enter(app.test_client(), codes[0], peer="::1", cf="198.51.100.7").status_code == 429
    assert _enter(app.test_client(), codes[0], peer="127.0.0.1", cf="198.51.100.8").status_code == 200


def test_the_header_from_any_other_peer_changes_nothing(app):
    _, _, codes = _educator_with_open_course(app)
    device = app.test_client()
    for i, c in enumerate(_wrong(codes, CAPACITY)):
        assert _enter(device, c, cf=f"198.51.100.{i + 1}").status_code == 401
    assert _enter(device, codes[0], cf="198.51.100.250").status_code == 429


@pytest.mark.parametrize("cf", ["not an address", None])
def test_a_loopback_login_without_a_readable_header_counts_as_the_peer(app, caplog, cf):
    _, _, codes = _educator_with_open_course(app)
    caplog.set_level(logging.WARNING)
    _spend(app.test_client(), codes, peer="127.0.0.1", cf=cf)
    assert "without a readable CF-Connecting-IP" in caplog.text
    assert _enter(app.test_client(), codes[0], peer="127.0.0.1").status_code == 429
    assert _enter(app.test_client(), codes[0], peer="127.0.0.1", cf="198.51.100.7").status_code == 200


def test_ipv6_counts_by_its_48(app):
    _, _, codes = _educator_with_open_course(app)
    _spend(app.test_client(), codes, peer="2001:db8:1:2::10")
    assert _enter(app.test_client(), codes[0], peer="2001:db8:1:ffff:ffff::99").status_code == 429
    assert _enter(app.test_client(), codes[0], peer="2001:db8:2::10").status_code == 200
    assert _enter(app.test_client(), codes[0], peer="2001:db8::10").status_code == 200


def test_ipv6_behind_the_tunnel_counts_by_its_48(app):
    _, _, codes = _educator_with_open_course(app)
    _spend(app.test_client(), codes, peer="127.0.0.1", cf="2001:db8:1:2::10")
    assert _enter(app.test_client(), codes[0], peer="127.0.0.1", cf="2001:db8:1:ffff::99").status_code == 429
    assert _enter(app.test_client(), codes[0], peer="127.0.0.1", cf="2001:db8:2::10").status_code == 200


def test_an_ipv4_mapped_address_counts_as_its_ipv4(app):
    _, _, codes = _educator_with_open_course(app)
    _spend(app.test_client(), codes, peer="127.0.0.1", cf="::ffff:198.51.100.7")
    assert _enter(app.test_client(), codes[0], peer="127.0.0.1", cf="198.51.100.7").status_code == 429


def test_a_code_that_names_a_place_costs_nothing(app):
    _, _, codes = _educator_with_open_course(app)
    wrong = _wrong(codes, CAPACITY + 1)
    device = app.test_client()
    for c in wrong[:CAPACITY - 1]:
        assert _enter(device, c).status_code == 401
    for _ in range(5):
        assert _enter(app.test_client(), codes[0]).status_code == 200
    assert _enter(device, wrong[CAPACITY - 1]).status_code == 401
    assert _enter(device, wrong[CAPACITY]).status_code == 429


def test_a_right_code_of_a_closed_course_costs_nothing(app):
    edu, cid, codes = _educator_with_open_course(app)
    assert edu.delete(f"/api/courses/{cid}/access").status_code == 200
    device = app.test_client()
    for _ in range(CAPACITY + 5):
        resp = _enter(device, codes[0])
        assert resp.status_code == 403
        assert resp.get_json()["error"] == "access_closed"


def test_a_code_of_a_removed_place_or_an_inactive_account_costs_an_attempt(app):
    _, _, codes = _educator_with_open_course(app, places=2)
    db = SessionLocal()
    removed, inactive = sorted(
        db.query(M.CourseMembership).filter(M.CourseMembership.place_number.isnot(None)),
        key=lambda m: m.place_number)
    removed.status = M.MembershipStatus.removed
    inactive.user.is_active = False
    db.commit()
    SessionLocal.remove()
    device = app.test_client()
    assert _enter(device, codes[0]).get_json()["error"] == "invalid_code"
    assert _enter(device, codes[1]).get_json()["error"] == "invalid_code"
    _spend(device, codes, n=CAPACITY - 2)
    assert _enter(device, codes[0]).status_code == 429


def test_a_missing_code_costs_nothing(app):
    _, _, codes = _educator_with_open_course(app)
    device = app.test_client()
    for _ in range(CAPACITY + 3):
        assert _enter(device, "").status_code == 400
    assert _enter(device, _wrong(codes, 1)[0]).status_code == 401


def test_an_entry_that_cannot_be_a_code_costs_nothing(app, monkeypatch):
    _, _, codes = _educator_with_open_course(app)
    device = app.test_client()
    looked_up = []
    real = auth_routes.find_place

    def recorded(db, raw):
        looked_up.append(raw)
        return real(db, raw)
    monkeypatch.setattr(auth_routes, "find_place", recorded)
    entries = ["ACD", "ACDEFG", "AC DE FG H", "ACDE0", "OACDE", "ACD1E", "SACDE",
               "ÄCDEF", "Place 1: ACDEF\nPlace 2: CDEFG"]
    for _ in range(CAPACITY // len(entries) + 2):
        for entry in entries:
            resp = _enter(device, entry)
            assert resp.status_code == 401 and resp.get_json()["error"] == "invalid_code"
    assert looked_up == []
    _spend(device, codes)
    assert _enter(device, codes[0]).status_code == 429


def test_an_entry_that_cannot_be_a_code_reserves_nothing():
    attempts = LA.LoginAttempts(capacity=1, clock=lambda: 1000.0)
    with attempts.attempt(DEVICE, reserve=False) as entry:
        assert entry.wait == 0
        assert not attempts._pending
        entry.spend()
    with attempts.attempt(DEVICE) as attempt:
        assert attempt.wait == 0


def test_the_budget_refills_one_attempt_per_interval(app, clock):
    _, _, codes = _educator_with_open_course(app)
    device = app.test_client()
    wrong = _wrong(codes, CAPACITY + 3)
    _spend(device, codes)
    assert _enter(device, wrong[CAPACITY]).status_code == 429

    clock.now += LA.REFILL_SECONDS
    assert _enter(device, wrong[CAPACITY + 1]).status_code == 401
    refused = _enter(device, wrong[CAPACITY + 2])
    assert refused.status_code == 429
    assert refused.get_json()["retry_after"] == REFILL

    clock.now += LA.REFILL_SECONDS / 2
    assert _enter(device, codes[0]).get_json()["retry_after"] == REFILL // 2


def test_a_wait_is_the_whole_seconds_to_the_next_attempt(app, clock):
    _, _, codes = _educator_with_open_course(app)
    device = app.test_client()
    wrong = _wrong(codes, CAPACITY + 1)
    _spend(device, codes)                     # empty at 1000, the next attempt at 1030
    for now, wait in ((1010, 20), (1014.8, 16), (1020, 10), (1021, 9), (1022, 8), (1029.7, 1)):
        clock.now = now
        refused = _enter(device, wrong[CAPACITY])
        assert refused.status_code == 429
        assert refused.get_json()["retry_after"] == wait
    clock.now = 1030.0
    assert _enter(device, wrong[CAPACITY]).status_code == 401


def test_a_wait_at_the_rounding_edge_is_one_second_and_reserves_nothing():
    """A level a hair below one attempt, whose sum to the next attempt
    rounds to the moment itself: charged at 242447.57628260384 of the
    monotonic clock, some 2.8 days after boot, and asked 4.2 seconds later."""
    now = 242451.82222883237
    attempts = LA.LoginAttempts(clock=lambda: now)
    key = attempts._id(DEVICE)
    attempts._budgets[key] = [0.8584684590486795, 242447.57628260384]
    assert attempts._level(key, now) < 1
    with attempts.attempt(DEVICE) as attempt:
        assert attempt.wait == 1
        assert not attempts._pending
    assert attempts._budgets[key] == [0.8584684590486795, 242447.57628260384]


def test_a_budget_holds_capacity_attempts_at_most(app, clock):
    _, _, codes = _educator_with_open_course(app)
    device = app.test_client()
    _spend(device, codes, n=1)
    clock.now += 20 * LA.REFILL_SECONDS     # 59 without the cap, and not yet dropped
    _spend(device, codes)
    assert _enter(device, _wrong(codes, 1)[0]).status_code == 429


def _together(n, target):
    """Run `target(i)` in n threads that start at the same moment."""
    barrier = threading.Barrier(n)

    def run(i):
        barrier.wait()
        try:
            target(i)
        finally:
            SessionLocal.remove()

    threads = [threading.Thread(target=run, args=(i,), daemon=True) for i in range(n)]
    for t in threads:
        t.start()
    # A login that never returns fails the test instead of holding the run.
    deadline = time.monotonic() + 10
    for t in threads:
        t.join(max(0.0, deadline - time.monotonic()))
    assert not any(t.is_alive() for t in threads)


class _Unhurried(dict):
    """The lookups under way, read and written so that the other threads
    run between the read and the reservation, and before the reservation
    is entered."""

    def get(self, key, default=None):
        value = super().get(key, default)
        time.sleep(0.0005)
        return value

    def __setitem__(self, key, value):
        time.sleep(0.0005)
        super().__setitem__(key, value)


def test_parallel_requests_cannot_pass_on_the_same_last_attempt():
    attempts = LA.LoginAttempts(capacity=1, clock=lambda: 1000.0)
    attempts._pending = _Unhurried()
    waits = []

    def one(_):
        with attempts.attempt(DEVICE) as attempt:
            waits.append(attempt.wait)
            if not attempt.wait:
                time.sleep(0.01)            # the lookup: every other login arrives meanwhile
                attempt.spend()

    _together(16, one)
    assert sorted(waits) == [0] + [REFILL] * 15
    assert not attempts._pending


def test_the_logins_of_one_address_run_side_by_side():
    attempts = LA.LoginAttempts(clock=lambda: 1000.0)
    inside = threading.Barrier(8, timeout=5)
    met = []

    def one(_):
        with attempts.attempt(DEVICE) as attempt:
            try:
                inside.wait()           # all eight are inside their lookups at once
            except threading.BrokenBarrierError:
                return
            met.append(attempt.wait)
            attempt.spend()

    _together(8, one)
    assert met == [0] * 8
    assert not attempts._pending
    assert attempts._level(attempts._id(DEVICE), 1000.0) == CAPACITY - 8


@pytest.mark.parametrize("charged, wait", [(True, REFILL), (False, 0)])
def test_a_login_at_the_last_attempt_waits_for_the_lookup_under_way(charged, wait):
    attempts = LA.LoginAttempts(capacity=1, clock=lambda: 1000.0)
    under_way, settle = threading.Event(), threading.Event()
    answers = {}

    def first():
        with attempts.attempt(DEVICE) as attempt:
            under_way.set()
            settle.wait(5)
            if charged:
                attempt.spend()

    def login(name, address):
        with attempts.attempt(address) as attempt:
            answers[name] = attempt.wait

    threads = [threading.Thread(target=first, daemon=True)]
    threads[0].start()
    assert under_way.wait(5)
    for name, address in (("same", DEVICE), ("other", "203.0.113.6")):
        threads.append(threading.Thread(target=login, args=(name, address), daemon=True))
        threads[-1].start()
    threads[2].join(5)
    time.sleep(0.05)
    assert answers == {"other": 0}          # the same address waits for the lookup under way
    settle.set()
    for t in threads:
        t.join(5)
    assert answers == {"other": 0, "same": wait}
    assert not attempts._pending


class _Counted(threading.Condition):
    """The budgets' condition, keeping the timeout of every wait on it."""

    def __init__(self):
        super().__init__(threading.Lock())
        self.timeouts = []
        self.waiting = threading.Event()

    def wait(self, timeout=None):
        self.timeouts.append(timeout)
        self.waiting.set()
        return super().wait(timeout)


def test_a_login_at_the_last_attempt_goes_on_once_the_budget_refills(clock):
    attempts = LA.LoginAttempts(capacity=2, refill_seconds=0.2, clock=clock)
    attempts._settled = _Counted()
    with attempts.attempt(DEVICE) as attempt:
        attempt.spend()                      # one attempt left
    under_way, settle, answered = threading.Event(), threading.Event(), threading.Event()
    answers = []

    def first():
        with attempts.attempt(DEVICE):
            under_way.set()
            settle.wait(5)                   # a lookup that takes long

    def login():
        with attempts.attempt(DEVICE) as attempt:
            answers.append(attempt.wait)
            answered.set()

    threads = [threading.Thread(target=first, daemon=True),
               threading.Thread(target=login, daemon=True)]
    threads[0].start()
    assert under_way.wait(5)
    threads[1].start()
    assert attempts._settled.waiting.wait(5)  # the lookup under way holds the last attempt
    assert not answered.is_set()
    clock.now += 0.2                         # the budget regains one
    assert answered.wait(5)                  # before that lookup settles
    assert answers == [0]
    # Each wait lasted until the budget holds one attempt more than the
    # lookup under way, (1 + 1 - 1) * 0.2 seconds: no spin, and no refill late.
    timeouts = attempts._settled.timeouts
    assert timeouts and all(t == pytest.approx(0.2) for t in timeouts)
    settle.set()
    for t in threads:
        t.join(5)
    assert not attempts._pending


def _slow_lookup(monkeypatch, seconds=0.05):
    real = auth_routes.find_place

    def slow(db, raw):
        time.sleep(seconds)
        return real(db, raw)
    monkeypatch.setattr(auth_routes, "find_place", slow)


def test_wrong_codes_together_at_the_last_attempt_pass_once(app, monkeypatch):
    _, _, codes = _educator_with_open_course(app)
    wrong = _wrong(codes, CAPACITY + 8)
    _spend(app.test_client(), codes, n=CAPACITY - 1)
    _slow_lookup(monkeypatch)
    answers = []
    _together(8, lambda i: answers.append(_enter(app.test_client(), wrong[CAPACITY + i])))
    assert sorted(r.status_code for r in answers) == [401] + [429] * 7
    assert all(r.get_json()["retry_after"] == REFILL for r in answers if r.status_code == 429)


def test_right_codes_together_at_the_last_attempt_all_enter(app, monkeypatch):
    _, _, codes = _educator_with_open_course(app)
    wrong = _wrong(codes, CAPACITY)
    _spend(app.test_client(), codes, n=CAPACITY - 1)
    _slow_lookup(monkeypatch)
    statuses = []
    _together(5, lambda i: statuses.append(_enter(app.test_client(), codes[0]).status_code))
    assert statuses == [200] * 5
    assert _enter(app.test_client(), wrong[-1]).status_code == 401
    assert _enter(app.test_client(), wrong[-1]).status_code == 429


def test_a_lookup_that_fails_costs_nothing(app, monkeypatch):
    _, _, codes = _educator_with_open_course(app)

    def refused(db, raw):
        raise RuntimeError("database is locked")
    real = auth_routes.find_place
    monkeypatch.setattr(auth_routes, "find_place", refused)
    app.testing = False
    for _ in range(CAPACITY + 5):
        assert _enter(app.test_client(), codes[0]).status_code == 500
    monkeypatch.setattr(auth_routes, "find_place", real)
    assert _enter(app.test_client(), codes[0]).status_code == 200
    attempts = app.extensions[LA._EXTENSION]
    assert not attempts._budgets and not attempts._pending


def test_a_login_is_charged_once_and_a_refused_one_never():
    attempts = LA.LoginAttempts(capacity=2, clock=lambda: 1000.0)
    key = attempts._id(DEVICE)
    with attempts.attempt(DEVICE) as attempt:
        attempt.spend()
        attempt.spend()
    assert attempts._level(key, 1000.0) == 1
    with attempts.attempt(DEVICE) as attempt:
        attempt.spend()
    with attempts.attempt(DEVICE) as refused:
        assert refused.wait == REFILL
        refused.spend()
    assert attempts._level(key, 1000.0) == 0
    assert not attempts._pending


def test_a_budget_untouched_for_the_whole_refill_is_dropped_the_oldest_first(clock):
    attempts = LA.LoginAttempts(clock=clock)
    full = CAPACITY * LA.REFILL_SECONDS
    for address in ("198.51.100.1", "198.51.100.2", "198.51.100.1"):
        with attempts.attempt(address) as attempt:
            attempt.spend()
        clock.now += 1
    # .2 was charged last at 1001, .1 at 1002.
    clock.now = 1001 + full - 0.5
    with attempts.attempt("203.0.113.9"):
        pass
    assert len(attempts._budgets) == 2
    clock.now = 1001 + full
    with attempts.attempt("203.0.113.9"):
        pass
    assert list(attempts._budgets) == [attempts._id("198.51.100.1")]


def test_an_app_makes_its_budgets_at_its_first_place_login_and_keeps_them():
    a = _bare_app()
    assert LA._EXTENSION not in a.extensions
    _, _, codes = _educator_with_open_course(a)
    device = a.test_client()
    _spend(device, codes)
    assert _enter(device, codes[0]).status_code == 429
    assert isinstance(a.extensions[LA._EXTENSION], LA.LoginAttempts)


def test_every_set_of_budgets_has_a_key_of_its_own():
    one, other = LA.LoginAttempts(), LA.LoginAttempts()
    assert one._id(DEVICE) != other._id(DEVICE)
    assert one._id(DEVICE) != hashlib.sha256(DEVICE.encode()).digest()


def test_no_address_is_kept_in_plain_or_logged(app, caplog):
    _, _, codes = _educator_with_open_course(app)
    caplog.set_level(logging.DEBUG)
    _spend(app.test_client(), codes)
    assert _enter(app.test_client(), codes[0]).status_code == 429
    assert DEVICE not in caplog.text
    attempts = app.extensions[LA._EXTENSION]
    assert attempts._budgets
    assert all(isinstance(k, bytes) and DEVICE.encode() not in k for k in attempts._budgets)
    assert not attempts._pending
