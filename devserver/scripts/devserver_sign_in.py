"""
The sign-in of a script that calls the DevServer (2026-11-15).

Every route of the DevServer but the start page and the sign-in needs a
sign-in since 2026-11-15 (devserver/my_app/lab/sign_in_gate.py);
a request without one is answered 401 `sign_in_required`. The scripts that
start runs (the workshop replays in devserver/testfiles, the probes and
measurements in devserver/scripts) sign in like a browser does, with one of:

  AI4ARTSED_SIGN_IN_ID and AI4ARTSED_SIGN_IN_PASSWORD
      an account with a password (course leader or admin). The account agrees
      to the conditions of use in the browser, once, at its first sign-in;
      a script never agrees for it. The routes of the settings
      (/api/settings/...) need an admin.
  AI4ARTSED_PLACE_CODE
      the code of a place, in a course whose access is open.

A run started under a place runs at the safety level of its course; one
started under an account in its own use runs at the installation's level,
where every replay ran before 2026-11-15. Replays of different nights compare
only under the same kind of sign-in.

The values are read from the environment and go nowhere but to the server
named; nothing is printed of them.

The session cookie is sent as a header, not left to the cookie jar: the
production backend marks its cookie Secure, and Python's cookie jars hand a
Secure cookie only to https, while these scripts call http://localhost.

    from devserver_sign_in import devserver
    devserver(base_url).post(f"{base_url}/api/...", json=...)

    session = await aiohttp_session(base_url)
    async with session:
        ...

Location: devserver/scripts/devserver_sign_in.py
"""
from __future__ import annotations

import os
from http.cookies import SimpleCookie

ENV_ID = "AI4ARTSED_SIGN_IN_ID"
ENV_PASSWORD = "AI4ARTSED_SIGN_IN_PASSWORD"
ENV_PLACE_CODE = "AI4ARTSED_PLACE_CODE"


class SignInError(RuntimeError):
    """The script could not sign in; the message says why."""


def _credentials() -> tuple[str, dict]:
    ident = os.environ.get(ENV_ID, "").strip()
    password = os.environ.get(ENV_PASSWORD, "")
    code = os.environ.get(ENV_PLACE_CODE, "").strip()
    if ident and password:
        return "/api/auth/login", {"identifier": ident, "password": password}
    if code:
        return "/api/auth/participant-login", {"code": code}
    raise SignInError(
        f"The DevServer needs a sign-in. Set {ENV_ID} and {ENV_PASSWORD} "
        f"(an account with a password), or {ENV_PLACE_CODE} (the code of a place).")


def _refusal(status: int, body: object) -> SignInError:
    error = body.get("error") if isinstance(body, dict) else None
    if status == 409 and error == "terms_required":
        version = body.get("terms_version") if isinstance(body, dict) else None
        return SignInError(
            f"The account has not agreed to the conditions of use (version {version}). "
            "Sign in with it once in the browser; the sign-in page shows the conditions.")
    return SignInError(f"The sign-in was refused: HTTP {status} {error or ''}".rstrip())


def _cookie_header(set_cookies: list[str]) -> str:
    jar = SimpleCookie()
    for line in set_cookies:
        jar.load(line)
    header = "; ".join(f"{name}={morsel.value}" for name, morsel in jar.items() if morsel.value)
    if not header:
        raise SignInError("The server signed in and set no session cookie.")
    return header


_sessions: dict = {}


def devserver(base_url: str):
    """A requests.Session signed in at `base_url`, made at the first call and
    kept for the process."""
    key = base_url.rstrip("/")
    if key not in _sessions:
        import requests
        path, body = _credentials()
        session = requests.Session()
        resp = session.post(f"{key}{path}", json=body, timeout=(10, None))
        try:
            answer = resp.json()
        except ValueError:
            answer = None
        if resp.status_code != 200:
            raise _refusal(resp.status_code, answer)
        session.headers["Cookie"] = _cookie_header(resp.raw.headers.getlist("Set-Cookie"))
        _sessions[key] = session
    return _sessions[key]


async def aiohttp_session(base_url: str):
    """A new aiohttp.ClientSession signed in at `base_url`. The caller closes
    it (`async with`)."""
    import aiohttp
    path, body = _credentials()
    key = base_url.rstrip("/")
    async with aiohttp.ClientSession() as probe:
        async with probe.post(f"{key}{path}", json=body) as resp:
            try:
                answer = await resp.json(content_type=None)
            except ValueError:
                answer = None
            if resp.status != 200:
                raise _refusal(resp.status, answer)
            header = _cookie_header(resp.headers.getall("Set-Cookie", []))
    return aiohttp.ClientSession(headers={"Cookie": header})
