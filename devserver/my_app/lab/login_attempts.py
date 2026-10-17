"""
The failed attempts of the place login, counted per client address.

A place is entered with its code alone, five characters from 25
(lab/place_codes.py), and without a count a script tries the next code as
fast as the server answers. Each address holds a budget: CAPACITY attempts at
most, one more every REFILL_SECONDS. Only a code that names no active place
(401 `invalid_code`) costs an attempt. A right code costs nothing, and neither
does an entry that cannot be a code at all: of another length, or with a
character no code carries (`place_codes.has_code_form`). While the budget is
empty the login answers 429 before the lookup, to a right code, a wrong one
and an entry that cannot be a code alike, and the answer says nothing about
what it was given.

A login of a code reserves an attempt before its lookup and settles it after
(`LoginAttempts.attempt`): charged for a code that names no active place,
returned otherwise, and either in one step. The logins of one address look
their codes up side by side while the budget covers every lookup under way,
so parallel requests of one address cannot pass on the same last attempt.
Where the lookups under way hold the attempts the budget still has, a login
waits. It looks again whenever one of them settles and once the budget has
regained an attempt, in no set order with the other logins that wait, and
is answered from what the budget then holds: with a lookup of its own, or
with the real wait. An entry that cannot be a code reserves nothing. A class enters
behind one router under one address, which is why the budget is large and
refills quickly.

A budget that has lost no attempt for CAPACITY * REFILL_SECONDS is full
again, and the next login drops it: after a login, the budgets held are
those of the addresses charged in the last twenty minutes.

The address is the one CF-Connecting-IP carries when the socket's peer is
loopback, and the socket's peer otherwise; the header from any other peer is
ignored, because anybody can send it. A loopback peer is the Cloudflare
tunnel on this machine, which writes the client's address there; the
frontend's development server, which writes the address of a client from
elsewhere there in place of whatever it sent (vite.config.ts); or any other
process on this machine, an SSH port forward for one, which is trusted the
same way. A login from a loopback peer without a readable address in the
header is counted under the peer's own address, and the log says so each
time. An IPv6 address counts by its /48, the block
RIPE-690 recommends for a business customer's site: counted by its /64, such
a site would hold 65,536 budgets. Customers a provider hands smaller blocks
out of one /48 (a /56 for a home line, a /64 for a phone) share one budget.
The budgets live in the app's extensions, keyed by an HMAC of the address
under a key made in this process: no address is kept, written or logged, and
the counts end with the process.

Location: devserver/my_app/lab/login_attempts.py
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import logging
import math
import secrets
import threading
import time
from collections import OrderedDict
from contextlib import contextmanager
from typing import Callable, Dict, Iterator, List, Optional, Union

logger = logging.getLogger(__name__)

CAPACITY = 40
REFILL_SECONDS = 30.0

_EXTENSION = "place_login_attempts"
# The IPv6 block that counts as one network (see the module docstring).
_IPV6_PREFIX = 48

_Address = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]


class Attempt:
    """One login of one address. `wait` is 0 when the login may go on,
    otherwise the whole seconds until the budget holds an attempt again."""

    def __init__(self, budgets: "LoginAttempts", key: bytes, wait: int, reserved: bool):
        self._budgets = budgets
        self._key = key
        self._reserved = reserved
        self.wait = wait

    def spend(self) -> None:
        """Charge the attempt: the code named no active place. Once per
        login; a login that reserved nothing is never charged."""
        self._settle(charge=True)

    def _settle(self, charge: bool) -> None:
        if self._reserved:
            self._reserved = False
            self._budgets._settle(self._key, charge)


class LoginAttempts:
    """The budgets of one app."""

    def __init__(self, capacity: int = CAPACITY, refill_seconds: float = REFILL_SECONDS,
                 clock: Callable[[], float] = time.monotonic):
        self.capacity = capacity
        self.refill_seconds = refill_seconds
        self._clock = clock
        self._key = secrets.token_bytes(32)
        # Guards everything below. A login waits on it only where the lookups
        # of its own address under way hold the attempts left.
        self._settled = threading.Condition(threading.Lock())
        # Per address: the level and the moment of the last charge, in the
        # order of the charges, the oldest first.
        self._budgets: "OrderedDict[bytes, List[float]]" = OrderedDict()
        # Per address: the lookups under way, each holding one attempt.
        self._pending: Dict[bytes, int] = {}

    @contextmanager
    def attempt(self, address: str, reserve: bool = True) -> Iterator[Attempt]:
        """One login of this address, from its reservation to its settling
        (see the module docstring). A login that does not `reserve` looks
        nothing up; it only learns whether the budget is empty."""
        key = self._id(address)
        with self._settled:
            while True:
                now = self._clock()
                self._expire(now)
                level = self._level(key, now)
                pending = self._pending.get(key, 0)
                if level - pending >= 1:
                    wait = 0
                    break
                if level < 1:
                    wait = self._wait(key, now)
                    break
                # The lookups under way hold what the budget has left; each
                # returns its attempt or is charged once its lookup is done,
                # and the budget regains attempts meanwhile.
                self._settled.wait(self._refilled_in(level, pending))
            reserved = reserve and not wait
            if reserved:
                self._pending[key] = pending + 1
        attempt = Attempt(self, key, wait, reserved)
        try:
            yield attempt
        finally:
            attempt._settle(charge=False)

    def _settle(self, key: bytes, charge: bool) -> None:
        with self._settled:
            if charge:
                now = self._clock()
                self._budgets[key] = [self._level(key, now) - 1, now]
                self._budgets.move_to_end(key)
            left = self._pending[key] - 1
            if left:
                self._pending[key] = left
            else:
                del self._pending[key]
            self._settled.notify_all()

    def _id(self, address: str) -> bytes:
        return hmac.new(self._key, address.encode("utf-8", "replace"), hashlib.sha256).digest()

    def _level(self, key: bytes, now: float) -> float:
        entry = self._budgets.get(key)
        if entry is None:
            return float(self.capacity)
        level, stamp = entry
        return min(float(self.capacity), level + (now - stamp) / self.refill_seconds)

    def _wait(self, key: bytes, now: float) -> int:
        """The whole seconds until a budget below one attempt holds one
        again, counted from its last charge, so that a whole number of
        seconds comes out whole. At least one: where the level and this sum
        round apart at the edge, a wait of 0 would reserve an attempt the
        budget does not hold."""
        level, stamp = self._budgets[key]
        return max(1, math.ceil(stamp + (1 - level) * self.refill_seconds - now))

    def _refilled_in(self, level: float, pending: int) -> Optional[float]:
        """The seconds until the budget covers one lookup more than those
        under way, or None where only a settle can free an attempt: the
        lookups under way hold all CAPACITY."""
        if pending >= self.capacity:
            return None
        return (pending + 1 - level) * self.refill_seconds

    def _expire(self, now: float) -> None:
        """Drop the budgets that have lost no attempt for CAPACITY *
        REFILL_SECONDS: they are full again. The oldest comes first, so the
        pass ends at the first younger one."""
        full = self.capacity * self.refill_seconds
        while self._budgets:
            key, (_, stamp) = next(iter(self._budgets.items()))
            if now - stamp < full:
                return
            del self._budgets[key]


def attempts_of(app) -> LoginAttempts:
    """The budgets of this app, made at its first place login."""
    return app.extensions.setdefault(_EXTENSION, LoginAttempts())


def client_address(req) -> str:
    """The address a budget is kept for (see the module docstring)."""
    peer = _parse(req.remote_addr)
    if peer is not None and peer.is_loopback:
        forwarded = _parse(req.headers.get("CF-Connecting-IP"))
        if forwarded is not None:
            return _group(forwarded)
        logger.warning("[AUTH] place login from this machine without a readable "
                       "CF-Connecting-IP: counted under the address of the connection")
    if peer is None:
        return req.remote_addr or ""
    return _group(peer)


def _parse(value: Optional[str]) -> Optional[_Address]:
    try:
        address = ipaddress.ip_address((value or "").strip())
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        return address.ipv4_mapped
    return address


def _group(address: _Address) -> str:
    if isinstance(address, ipaddress.IPv6Address):
        bits = 128 - _IPV6_PREFIX
        return str(ipaddress.IPv6Network((int(address) >> bits << bits, _IPV6_PREFIX)))
    return str(address)
