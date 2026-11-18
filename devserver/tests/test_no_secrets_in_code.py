"""No password, key or token is written into the repository.

Three settings passwords stood in devserver/my_app/routes/settings_routes.py
as string literals: one from 2025-12-18 (6b5760e1), its successor from
2026-01-05 (77aa5635) to 2026-11-15, and the admin account's seed password
in devserver/my_app/lab/seed.py from 2026-07-05. The messages of the first
two commits named the password, the development log quoted the first, and a
test carried the second. No gate looked for any of it. This one does
(docs/DEVELOPMENT_DECISIONS.md, 2026-11-15).

Where it runs:
  * pre-commit (gate 11, `--staged`): every staged file that is text, read by
    its object id;
  * commit-msg (`--message FILE`): the message of the commit;
  * pre-push (`--push`, refs on stdin): the messages and the added lines of
    every commit the push sends, so a commit made with --no-verify, a
    cherry-pick, a rebase or a fast-forward merge is judged as well;
  * the public export (`--tree DIR`, scripts/public_export/export.sh);
  * the test suite and by hand (no argument): every tracked file.

What counts as a finding:
  * everywhere, test code and the pragma below included: a private key block,
    the token formats of the providers this platform talks to or might
    (sk-…, AKIA/ASIA…, ghp_/github_pat_…, glpat-…, gsk_…, xox…-, AIza…, hf_…,
    a JWT, a Bearer token), credentials inside a URL, one of the passwords
    that stood in the code (auth_service.PUBLISHED_PASSWORD_DIGESTS), and the
    exact value of a key file of this installation (devserver/*.key) or of an
    environment variable named like a key;
  * a password hash (pbkdf2:, scrypt:) outside test code;
  * a string literal assigned to, passed to or used as the fallback of a name
    that says password, secret, token, key, credential and the like
    (`X = "…"`, `x: "…"`, `"x": "…"`, `x("…")`, `cfg['X'] = "…"`,
    `getenv("X", "…")`, `getenv("X") or "…"`, `process.env.X || "…"`,
    `${X:-…}`); a name that only ends in key, pw or pass counts where the
    value is long and mixed (20 characters, three kinds of character);
  * in prose, configuration and shell files and in commit messages, the same
    without quotes (`password: …`, `export X_API_KEY=…`, `Environment=…`);
  * a staged file whose name is a key, a certificate, a keystore, an SSH key,
    a credentials file or an environment file.
Not counted: names of environment variables, paths and file names, URLs,
dotted keys, template placeholders and placeholders of documentation, the
labels of the language files. Test code (devserver/tests/, gpu_service/tests/,
__tests__/) keeps its throwaway values: there a value counts only where it is
twelve characters or more, of three kinds of character, and says nothing of
test, fake, example and the like.

A line that is no secret and still matches the literal rules carries
`not-a-secret:` and a reason of three words or more in a comment on the same
line. The pragma does not silence the formats, the published passwords, the
exact values, URL credentials or file names, and the number of lines that
carry it is pinned below (PRAGMA_LINES).
"""
from __future__ import annotations

import hashlib
import os
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]

# The digests of the passwords that stood in the code. The same set as
# devserver/my_app/lab/auth_service.py, written out here because this file
# runs without the platform's packages (test_the_two_lists_are_one).
PUBLISHED_PASSWORD_DIGESTS = frozenset({
    "55f2458efe5c7c179918a90bdcd695b9220e623c34dc485291210b8698a3a879",
    "792903ba6b8e6d8f6e6a0cae6a9ae9aa9dbf46fe924c50baad12f1088afd5ff7",
    "48ce26b6e0a4ee87a1b0ed1e418e8fb2ab66e6bb4c7a8cc953bb5e9b217b59fd",
})
PRAGMA_LINES = 0
LONG_LINE = 4000            # the literal rules skip longer lines (minified code)

# What a name says is judged by its last word (lib/x.py: SECRET_KEY,
# apiKey, client_secret, FIXED_PASSWORD), so passwordLabel, token_ids,
# clip_token_count and inputTokens say nothing of a secret.
STRONG_LAST = {"password", "passwords", "passwd", "passphrase", "passwort", "kennwort", "pwd",
               "secret", "secrets", "token", "credential", "credentials", "apikey"}
KEY_OF = {"secret", "api", "private", "access", "auth"}      # SECRET_KEY, api_key, AUTH_KEY
WEAK_LAST = {"key", "keys", "pw", "pass"}                    # MISTRAL_KEY, settings_pw, admin_pass
# Only a call whose name ends in one of these takes its secret as an
# argument: hash_password("…"); onToken("…") and credentials("mammouth") do not.
CALL_LAST = {"password", "passwd", "pwd", "passphrase", "passwort", "kennwort", "secret"}
SHELL_NAMES = {"PWD", "OLDPWD"}                              # the working directory


def _words(name: str) -> list[str]:
    return [w.lower() for w in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", name)]


def name_kind(name: str) -> str | None:
    """"strong", "weak" or None: whether a name says it holds a secret."""
    words = _words(name)
    if name in SHELL_NAMES or not words:
        return None
    if words[-1] in STRONG_LAST:
        return "strong"
    if words[-1] in ("key", "keys") and len(words) > 1 and words[-2] in KEY_OF:
        return "strong"
    return "weak" if words[-1] in WEAK_LAST else None


# In code a name may carry a hyphen ("x-api-key"); in prose a hyphen joins
# words (Pad-Token, Settings-Passwort), and a name after one is no name.
_CODE_NAME = r"(?<![A-Za-z0-9_.$-])(?P<name>[A-Za-z_][A-Za-z0-9_.-]{0,63})"
_PROSE_NAME = r"(?<![A-Za-z0-9_.$-])(?P<name>[A-Za-z_][A-Za-z0-9_.]{0,63})"
_VALUE = r"(?:[rRbBuUfF]{1,2})?(?P<q>[\"'`])(?P<val>(?:(?!(?P=q))[^\n]){6,}?)(?P=q)"
_BETWEEN = r"""(?:["'`]?\])?["'`]?\s*(?::\s*[A-Za-z_][A-Za-z0-9_\[\], |.]{0,40})?\s*"""
ASSIGNMENT = re.compile(_CODE_NAME + _BETWEEN + r"(?P<op>\?\?=|\|\|=|:=|=>|=|:|\()\s*" + _VALUE)
PROSE_ASSIGNMENT = re.compile(_PROSE_NAME + _BETWEEN + r"(?P<op>=|:)\s*" + _VALUE)
# The value is read ahead and not consumed: in Environment=SECRET_KEY=… the
# next name starts where the first value would.
UNQUOTED = re.compile(
    _PROSE_NAME + r"""["'`]?\s*(?:=|:)[ \t]*[`'"]?(?=(?P<val>[^\s"'`$<{#|,;=()\[\]]{8,}))""")
ENV_FALLBACKS = [
    re.compile(r"""(?:environ\.get|getenv|environ\.setdefault)\(\s*["'](?P<name>[A-Za-z0-9_]+)["']\s*,\s*"""
               r"(?:default\s*=\s*)?" + _VALUE),
    re.compile(r"""(?:environ\.get\(|getenv\(|environ\[)\s*["'](?P<name>[A-Za-z0-9_]+)["']\s*[\])]\s*"""
               r"(?:or|\|\||\?\?)\s*" + _VALUE),
    re.compile(r"""(?:process|import\.meta)\.env(?:\.(?P<name>[A-Za-z0-9_]+)|\[["'](?P<name2>[A-Za-z0-9_]+)["']\])"""
               r"\s*(?:\|\||\?\?)\s*" + _VALUE),
    re.compile(r"\$\{(?P<name>[A-Za-z0-9_]+):?-(?P<val>[^}\s\"'$]{6,})\}"),
]
BASIC_AUTH = re.compile(r"""\bauth\s*=\s*\(\s*["'][^"'\n]*["']\s*,\s*["'](?P<val>[^"'\n]{6,})["']""")
PASSWORD_HASH = re.compile(r"\b(?:pbkdf2:sha\d+|scrypt):[0-9:]*\$[A-Za-z0-9./+]+\$[0-9a-fA-F]{32,}")

FORMATS = [
    (re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED |PGP )?PRIVATE KEY(?: BLOCK)?-----"),
     "a private key"),
    (re.compile(r"PuTTY-User-Key-File-\d"), "a PuTTY key"),
    (re.compile(r"\bsk-(?:ant-|proj-|or-)?[A-Za-z0-9_-]{20,}"), "a provider API key (sk-)"),
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "an AWS access key"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"), "a GitHub token"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}"), "a GitHub token"),
    (re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}"), "a GitLab token"),
    (re.compile(r"\bgsk_[A-Za-z0-9]{20,}"), "a Groq key"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), "a Slack token"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"), "a Google API key"),
    (re.compile(r"\bhf_[A-Za-z0-9]{30,}\b"), "a Hugging Face token"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"), "a JSON web token"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}"), "a Bearer token"),
]
URL_CREDENTIALS = re.compile(
    r"\b[a-z][a-z0-9+.-]*://(?P<user>[^/\s:@'\"<>{}]*):(?P<pw>[^/\s@'\"<>{}]{3,})@")
# A key format followed by these is a placeholder in documentation.
PLACEHOLDER = re.compile(r"your|here|example|x{4,}|\.\.\.", re.I)
URL_PLACEHOLDER = re.compile(r"^(?:\$\{?[A-Za-z_][A-Za-z0-9_]*\}?|password|pass|passwd|pwd|secret|changeme)$", re.I)

SECRET_FILE = re.compile(
    r"(?:^|/)(?:[^/]+\.(?:key|pem|p12|pfx|ppk|jks|keystore|p8|gpg|asc)"
    r"|id_(?:rsa|dsa|ecdsa|ed25519)|\.netrc|\.pgpass|\.npmrc|\.pypirc"
    r"|\.env(?:\.[^/]*)?|[^/]+\.env)$", re.I)
ALLOWED_FILE = re.compile(r"\.(?:example|sample)$", re.I)

NOT_A_SECRET = [
    re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$"),                     # an environment variable's name
    re.compile(r"^(?:/|\./|\.\./|~/)[^+=]*$"),                           # a path
    re.compile(r"^[^+=]*\.(?:key|txt|json|pem|env|ya?ml|py|ts|js|db|log|md|html|vue|template|example)$",
               re.I),                                                    # a file name
    re.compile(r"^[a-z][a-z0-9+.-]*://"),                                # a URL
    re.compile(r"^(?!eyJ)[a-z]\w{0,40}(?:\.[\w-]{1,40})+$"),          # a dotted key (i18n, storage)
    re.compile(r"^[<{$].*[>}]$|\$\{|\$\(|\{\{|\{[A-Za-z_][^}]*\}|%\(?[A-Za-z_]"),  # a template
    re.compile(r"your|example|x{4,}|\.\.\.|…|\*{4,}", re.I),             # a placeholder in documentation
    re.compile(r"^(?:same-origin|include|omit|current-password|new-password)$"),  # fetch, autocomplete
    re.compile(r"\(.*\)|\[.*\]"),                                     # an expression of code
    re.compile(r"^(?:\\[ux]?[0-9a-fA-F]{2,4})+$"),                      # an escape sequence
]
THROWAWAY = re.compile(r"test|fake|dummy|example|sample|secret|password|passwort|wrong|right|correct|"
                       r"placeholder|fixture|invalid|bad|good|xxx|abc|123", re.I)

BINARY_PROBE = 8192
SKIP_NAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml"}
SKIP_PATHS = {"devserver/tests/test_no_secrets_in_code.py"}
PROSE_SUFFIXES = {
    ".md", ".txt", ".rst", ".sh", ".bash", ".env", ".service", ".ini", ".cfg", ".conf", ".toml",
    ".yaml", ".yml", ".properties", ".template", ".example", ".sample", ".tsv", ".csv",
}
MESSAGE = "COMMIT_MESSAGE"


# ---------------------------------------------------------------------------
# What a path is
# ---------------------------------------------------------------------------
def _is_test(rel: str) -> bool:
    """Test code: the test directories, nothing else named test_*."""
    return re.search(r"(?:^|/)(?:devserver/tests|gpu_service/tests|tests?/unit)/|/__tests__/", rel) is not None


def _carries_labels(rel: str) -> bool:
    """The language files and their work orders: their keys name fields
    (password: 'Passwort')."""
    return re.search(r"(?:^|/)i18n/[^/]+\.(?:ts|js|json|md)$", rel) is not None


def _is_prose(rel: str) -> bool:
    p = pathlib.PurePosixPath(rel)
    return (rel == MESSAGE or p.suffix.lower() in PROSE_SUFFIXES or not p.suffix
            or p.name.lower().startswith((".env", "dockerfile")) or p.name.lower().endswith(".env"))


def findings_for_path(rel: str) -> list[str]:
    if SECRET_FILE.search(rel) and not ALLOWED_FILE.search(rel):
        return [f"{rel}  a key, certificate, credentials or environment file"]
    return []


# ---------------------------------------------------------------------------
# What a value is
# ---------------------------------------------------------------------------
def _kinds(value: str) -> int:
    return sum(bool(re.search(p, value)) for p in (r"[a-z]", r"[A-Z]", r"[0-9]", r"[^A-Za-z0-9]"))


def _strong_value(value: str) -> bool:
    """Long, and of small letters, capitals and digits: a key's shape, which a
    storage key (ai4artsed:latent-lab:sittings) or an i18n key lacks."""
    return len(value) >= 20 and all(re.search(p, value) for p in (r"[a-z]", r"[A-Z]", r"[0-9]"))


def _counts(name: str, value: str, *, test: bool, minimum: int) -> bool:
    """Whether `value` under `name` looks like a secret."""
    kind = name_kind(name)
    if kind is None:
        return False
    strong = kind == "strong"
    if len(value) < minimum or any(p.search(value) for p in NOT_A_SECRET):
        return False
    if re.search(r"\s", value) and (not strong or len(value.split()) > 6):
        return False                     # a passphrase under a secret's name; any other sentence is copy
    if _words(name)[-1] == "token" and re.fullmatch(r"[a-z][a-z0-9_:.-]*", value):
        return False                     # a sentinel such as COMFYUI_DOWN_TOKEN = "comfyui_down"
    if not strong and not _strong_value(value):
        return False
    if test and (len(value) < 12 or _kinds(value) < 3 or THROWAWAY.search(value)):
        return False
    return True


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _candidates(line: str):
    for part in re.split(r"[\s\"'`]+", line):
        if 6 <= len(part) <= 64:
            yield part
    for part in re.split(r"[\s\"'`=:,;()<>\[\]{}]+", line):
        if 6 <= len(part) <= 64:
            yield part


def _main_checkout() -> pathlib.Path | None:
    try:
        common = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--path-format=absolute",
                                 "--git-common-dir"], check=True, capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    common_dir = pathlib.Path(common)
    return common_dir.parent if common_dir.name == ".git" else None


def local_secret_values() -> dict[str, str]:
    """The secrets of this installation: the key files beside the code (in this
    checkout and, from a worktree, in the main one) and the environment
    variables named like a key. Compared, never printed."""
    values: dict[str, str] = {}
    places = {REPO / "devserver"}
    main = _main_checkout()
    if main is not None:
        places.add(main / "devserver")
    for place in places:
        for key_file in sorted(place.glob("*.key")):
            try:
                value = key_file.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                continue
            if len(value) >= 12:
                values[value] = f"the content of devserver/{key_file.name}"
    for name, value in os.environ.items():
        if re.search(r"(?:API_KEY|_KEY|SECRET|TOKEN|PASSWORD)$", name) and len(value) >= 12:
            values[value.strip()] = f"the value of the environment variable {name}"
    return values


# ---------------------------------------------------------------------------
# The rules, line by line
# ---------------------------------------------------------------------------
def findings_in(rel: str, text: str, local: dict[str, str] | None = None) -> list[str]:
    out: list[str] = []
    test = _is_test(rel)
    labels = _carries_labels(rel)
    prose = _is_prose(rel)
    exact = [(v, what) for v, what in (local or {}).items() if v in text]
    for num, line in enumerate(text.splitlines(), 1):
        where = f"{rel}:{num}"
        for value, what in exact:
            if value in line:
                out.append(f"{where}  {what}")
        if any(_digest(c) in PUBLISHED_PASSWORD_DIGESTS for c in _candidates(line)):
            out.append(f"{where}  a password that stood in the code (auth_service.PUBLISHED_PASSWORD_DIGESTS)")
        for pattern, what in FORMATS:
            for m in pattern.finditer(line):
                if PLACEHOLDER.search(line[m.start():m.end() + 3]):
                    continue
                out.append(f"{where}  {what}")
                break
        for m in URL_CREDENTIALS.finditer(line):
            pw = m.group("pw")
            if not URL_PLACEHOLDER.match(pw) and "${" not in pw and not PLACEHOLDER.search(pw):
                out.append(f"{where}  credentials in a URL")
                break
        if not test and PASSWORD_HASH.search(line):
            out.append(f"{where}  a password hash")
        if labels or len(line) > LONG_LINE or _pragma(line):
            continue
        for m in (PROSE_ASSIGNMENT if prose else ASSIGNMENT).finditer(line):
            name = m.group("name")
            if prose and re.fullmatch(r"[A-Za-z_]+", m.group("val")):
                continue                 # prose names a piece of code: Token: `QwenTokenizer`
            if m.group("op") == "(" and _words(name)[-1:] != [] and _words(name)[-1] not in CALL_LAST:
                continue                 # onToken("…"), credentials("mammouth"): no secret passed
            if _counts(name, m.group("val"), test=test, minimum=6):
                out.append(f"{where}  a string literal assigned to {name}")
        for pattern in ENV_FALLBACKS:
            for m in pattern.finditer(line):
                name = m.groupdict().get("name") or m.groupdict().get("name2") or ""
                if _counts(name, m.group("val"), test=test, minimum=6):
                    out.append(f"{where}  a literal as the fallback of {name}")
        for m in BASIC_AUTH.finditer(line):
            if _counts("password", m.group("val"), test=test, minimum=6):
                out.append(f"{where}  a password in auth=(…)")
        if prose:
            for m in UNQUOTED.finditer(line):
                value = m.group("val")
                if re.fullmatch(r"[A-Za-z_]+", value):
                    continue                 # a word or a name of code: "Password: required"
                if _counts(m.group("name"), value, test=test, minimum=8):
                    out.append(f"{where}  a value written after {m.group('name')}")
    return list(dict.fromkeys(out))


# The pragma stands in a comment and gives a reason of three words or more.
PRAGMA = re.compile(r"(?:#|//|/\*|<!--)\s*not-a-secret:\s*\S+\s+\S+\s+\S+")


def _pragma(line: str) -> bool:
    return PRAGMA.search(line) is not None


# ---------------------------------------------------------------------------
# Where the rules run
# ---------------------------------------------------------------------------
def _git(*args: str, data: bytes | None = None) -> bytes:
    return subprocess.run(["git", "-C", str(REPO), *args], check=True, capture_output=True,
                          input=data).stdout


def _text_of(data: bytes) -> str | None:
    if b"\0" in data[:BINARY_PROBE]:
        return None
    return data.decode("utf-8", "replace")


def _judged(rel: str) -> bool:
    p = pathlib.PurePosixPath(rel)
    return rel not in SKIP_PATHS and p.name not in SKIP_NAMES


def _tracked() -> list[str]:
    out = _git("ls-files", "-z")
    return [r.decode("utf-8", "surrogateescape") for r in out.split(b"\0") if r]


def check_repo(local: dict[str, str] | None = None) -> list[str]:
    bad = []
    for rel in _tracked():
        bad.extend(findings_for_path(rel))
        path = REPO / rel
        if not _judged(rel) or path.is_symlink() or not path.is_file():
            continue
        text = _text_of(path.read_bytes())
        if text is not None:
            bad.extend(findings_in(rel, text, local))
    return bad


def check_tree(root: pathlib.Path, local: dict[str, str] | None = None) -> list[str]:
    bad = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if rel == ".git" or rel.startswith(".git/") or path.is_symlink() or not path.is_file():
            continue
        bad.extend(findings_for_path(rel))
        if not _judged(rel):
            continue
        text = _text_of(path.read_bytes())
        if text is not None:
            bad.extend(findings_in(rel, text, local))
    return bad


def pragma_lines() -> list[str]:
    hits = []
    for rel in _tracked():
        path = REPO / rel
        if not _judged(rel) or path.is_symlink() or not path.is_file():
            continue
        text = _text_of(path.read_bytes())
        for num, line in enumerate((text or "").splitlines(), 1):
            if _pragma(line):
                hits.append(f"{rel}:{num}")
    return hits


def _staged(local: dict[str, str]) -> list[str]:
    """Every staged file but a deletion, read by its object id."""
    raw = _git("diff", "--cached", "--raw", "-z", "--no-abbrev", "--no-renames", "--diff-filter=d")
    fields = raw.split(b"\0")
    bad = []
    for meta, name in zip(fields[0::2], fields[1::2]):
        if not meta:
            continue
        _, new_mode, _, new_oid, _ = meta.decode().lstrip(":").split(" ", 4)
        rel = name.decode("utf-8", "surrogateescape")
        bad.extend(findings_for_path(rel))
        if new_mode in ("160000", "120000") or not _judged(rel):
            continue                       # a submodule or a link: no content of its own
        text = _text_of(_git("cat-file", "blob", new_oid))
        if text is not None:
            bad.extend(findings_in(rel, text, local))
    return bad


def _added_lines(rev: str) -> dict[str, list[tuple[int, str]]]:
    diff = _git("diff-tree", "-p", "-U0", "--no-color", "--no-ext-diff", "--no-renames", "--root", "-r",
                "--diff-filter=d", rev).decode("utf-8", "replace")
    files: dict[str, list[tuple[int, str]]] = {}
    current = None
    number = 0
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else None
            if current is not None:
                files.setdefault(current, [])
        elif line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            number = int(m.group(1)) if m else 0
        elif line.startswith("+") and current is not None:
            files[current].append((number, line[1:]))
            number += 1
    return files


def _pushed(updates: str, local: dict[str, str]) -> list[str]:
    zero = "0" * 40
    bad = []
    for update in updates.splitlines():
        parts = update.split()
        if len(parts) != 4 or parts[1].strip("0") == "":
            continue                       # a deletion of a remote ref
        _, local_sha, _, remote_sha = parts
        if remote_sha == zero or remote_sha.strip("0") == "":
            revs = _git("rev-list", local_sha, "--not", "--remotes").decode().split()
        else:
            revs = _git("rev-list", f"{remote_sha}..{local_sha}").decode().split()
        for rev in revs:
            short = rev[:9]
            message = _git("log", "-1", "--format=%B", rev).decode("utf-8", "replace")
            bad.extend(f"commit {short}: {f}" for f in findings_in(MESSAGE, message, local))
            added = _git("diff-tree", "--name-only", "--no-renames", "--root", "-r", "--diff-filter=A", rev)
            for rel in added.decode("utf-8", "replace").split("\n")[1:]:
                bad.extend(f"commit {short}: {f}" for f in findings_for_path(rel) if rel)
            for rel, lines in _added_lines(rev).items():
                if not _judged(rel):
                    continue
                for number, line in lines:
                    for f in findings_in(rel, line, local):
                        bad.append(f"commit {short}: {f.replace(f'{rel}:1 ', f'{rel}:{number} ', 1)}")
    return bad


# ---------------------------------------------------------------------------
# Tests. The values are built at run time, so this file holds none of them.
# ---------------------------------------------------------------------------
def _v(*parts: str) -> str:
    return "".join(parts)


def test_the_tree_holds_no_secret():
    bad = check_repo(local_secret_values())
    assert not bad, (f"{len(bad)} place(s) look like a password, key or token in the repository:\n  "
                     + "\n  ".join(bad[:60]))


def test_the_pragma_count_is_pinned():
    hits = pragma_lines()
    assert len(hits) == PRAGMA_LINES, (
        f"{len(hits)} line(s) carry the pragma, {PRAGMA_LINES} expected; a new one is "
        "a decision, so raise PRAGMA_LINES in the same commit:\n  " + "\n  ".join(hits))


def test_the_two_lists_are_one():
    sys.path.insert(0, str(REPO / "devserver"))
    from my_app.lab.auth_service import PUBLISHED_PASSWORD_DIGESTS as server_side
    assert server_side == PUBLISHED_PASSWORD_DIGESTS


def test_the_pattern_of_january_is_caught():
    line = f'    FIXED_PASSWORD = "{_v("Qe7", "r!Lp", "0zT4")}"'
    assert findings_in("devserver/my_app/routes/settings_routes.py", line)


def test_the_placeholder_key_of_the_session_cookie_is_caught():
    line = f"app.secret_key = os.environ.get('SECRET_KEY', '{_v('dev-secret-', 'key-change-in-production')}')"
    assert findings_in("devserver/my_app/__init__.py", line)


def test_assignments_in_other_forms_are_caught():
    value = _v("Zq8", "#pLm2", "Vw")
    for line in (f'api_key: str = "{value}"', f"  password: '{value}',", f'"client_secret": "{value}"',
                 f'connect(token="{value}")', f"const authToken = '{value}'",
                 f"app.config['SECRET_KEY'] = '{value}'", f'os.environ["API_TOKEN"] = "{value}"',
                 f'hash_password("{value}")', f'password = f"{value}"', f"secret = `{value}`",
                 f'PASSWORD = "{_v("it", chr(39), "s-mine-9")}"', f'pwd = "{_v("hun", "ter2")}"',
                 f'requests.get(url, auth=("admin", "{value}"))',
                 f'admin_pass = "{_v("Zq8#pLm2Vw", "Tk4!rB7sYh")}"',
                 f'MISTRAL_KEY = "{_v("aB3dE6gH9jK2mN5p", "Q8sT1vW4yZ7")}"',
                 f'SECRET_KEY = "{_v("QE7RLP0", "ZT4X9W2")}"',
                 f'SECRET_KEY = "{_v("kT9/2xQ+", "Lm3vWp==")}"',
                 f'headers = {{"x-api-key": "{_v("aB3dE6gH9jK2mN5p", "Q8sT1vW4yZ7")}"}}',
                 f'"TunnelSecret":"{_v("kT9/2xQ+Lm3", "vWp4rT6==")}"',
                 f'password = "{_v("correct horse ", "battery staple")}"'):
        assert findings_in("src/x.ts", line), line


def test_fallbacks_from_the_environment_are_caught():
    value = _v("Zq8", "#pLm2", "Vw")
    for line in (f'os.environ.setdefault("SECRET_KEY", "{value}")',
                 f'key = os.getenv("MISTRAL_API_KEY") or "{value}"',
                 f'os.getenv("API_TOKEN", default="{value}")',
                 f'const t = process.env.API_TOKEN || "{value}"',
                 f"const t = process.env['SECRET'] ?? '{value}'",
                 f"export SECRET_KEY=${{SECRET_KEY:-{value}}}"):
        assert findings_in("devserver/x.py", line), line


def test_unquoted_values_in_prose_and_configuration_are_caught():
    value = _v("Zq8", "pLm2Vw", "Tk4")
    for rel, line in (("deploy/run.sh", f"export MISTRAL_API_KEY={_v('aB3dE6gH9jK2mN5p', 'Q8sT1vW4yZ7xC0')}"),
                      ("deploy/a.service", f"Environment=SECRET_KEY={value}"),
                      ("config.yaml", f"password: {value}"),
                      ("config.ini", f"password = {value}"),
                      ("secrets.env.example", f"MISTRAL_API_KEY={_v('aB3dE6gH9jK2mN5p', 'Q8sT1vW4yZ7xC0')}"),
                      ("Dockerfile", f"ENV API_TOKEN={value}"),
                      ("docs/NOTES.md", f"Default password: `{value}`"),
                      (MESSAGE, f"- Password: {value}")):
        assert findings_in(rel, line), (rel, line)


def test_prose_that_names_a_password_passes():
    for line in ("Password: required", "The settings password: see below.",
                 "füllt mit dem Pad-Token (`<|pad|>`, id 0)", "das Settings-Passwort (`authenticate`)",
                 "Token-Resolution: `tokenizer.encode`", "ein unbekanntes Token (`gpu_lease_id`)",
                 "per green-edged token: `labels[row].value`", "PWD=public/ai4artsed-frontend",
                 "Token: `QwenTokenizerFastWrapper`", '"api_key": os.getenv("MISTRAL_API_KEY"),',
                 "nach 50 Token: `InstanceAttributeWrapper` gebaut",
                 "Präfix-Token-Zahl = Zentrumsverdichtung",
                 "export MISTRAL_API_KEY=$(cat devserver/mistral.key)", "password: ${PASSWORD}",
                 "SECRET_KEY=<a long random value>", "| password | string |"):
        assert not findings_in("docs/x.md", line), line


def test_what_is_no_secret_passes():
    for line in ('SETTINGS_PASSWORD_FILE = DEVSERVER_DIR / "settings_password.key"',
                 'TOKEN_ENV = "MISTRAL_API_KEY"',
                 "passwordLabel: 'Enter the settings password',",
                 "tokenKey = 'ai4artsed.signInTab'",
                 'password = os.environ["AI4ARTSED_SIGN_IN_PASSWORD"]',
                 f'secret_key = "{_v("abcd", "efgh1")}"  # not-a-secret: a fixture of the docs',
                 "inputTokens: 'Eingabe-Tokens',",
                 "state.tokens = 'whitespace'",
                 'export AWS_SECRET_ACCESS_KEY="your-secret-key"',
                 f'  "openrouter": "{_v("sk-or-v1-", "YOUR_OPENROUTER_KEY_HERE")}",',
                 f'  "openrouter": "{_v("sk-or-v1-", "abcdefghijklmnopqrstuv")}..."',
                 "fetch(url, { credentials: 'same-origin' })",
                 'COMFYUI_DOWN_TOKEN = "comfyui_down"',
                 '<input type="password" autocomplete="current-password">',
                 ':key="item.id"', 'cacheKey = f"{model}-{seed}"',
                 'storageKey = "ai4artsed.flow.lastPerspective"',
                 'url = "postgres://user:password@localhost/db"',
                 'url = "redis://:${REDIS_PASSWORD}@host"',
                 "passwordLabel: 'Password',", "const n = clip_token_count('long-name-here')",
                 "onToken('\\u0000')", "API, KEY = credentials(\"mammouth\")",
                 "const SITTINGS_KEY = 'ai4artsed:latent-lab:sittings-v1'",
                 "descriptionKey: 'canvas.nodes.descriptionLong'",
                 "labelKey: 'canvas.collectorÉtiquette.variant_2'",
                 "/** One row per green-edged token: `label¦values¦rank…`. */",
                 '@update-node-random-prompt-token-limit="handleTokenLimitUpdate"',
                 "token=\"$(tr -d '[:space:]' < \"$token_file\")\""):
        assert not findings_in("devserver/my_app/x.py", line), line


def test_the_pragma_needs_a_reason_and_does_not_silence_a_format():
    value = _v("Zq8", "#pLm2", "Vw")
    assert findings_in("x.py", f'secret_key = "{value}"  # not-a-secret:')
    assert not findings_in("x.py", f'secret_key = "{value}"  # not-a-secret: a documented fixture')
    assert findings_in("x.py", f'KEY = "{_v("sk-ant-api03-", "a1B2" * 10)}"  # not-a-secret: a documented fixture')


def test_the_language_files_keep_their_field_names():
    assert not findings_in("public/ai4artsed-frontend/src/i18n/de.ts", "    password: 'Passwort',")
    assert not findings_in("public/ai4artsed-frontend/src/i18n/uk.ts", "    apiKey: 'API-ключ',")
    assert not findings_in("_design/frontend/i18n/en.additions.ts", "    password: 'Password',")
    assert findings_in("public/ai4artsed-frontend/src/views/x.vue", f"const password = '{_v('Hk4', '!mw9Pq')}'")


def test_test_code_keeps_its_throwaway_values_but_no_real_ones():
    for line in ('a.secret_key = "test-secret"', 'password="secret12"', 'NEW = "a-new-password-17"',
                 'hash_password("the-old-settings-pw")', 'h = "pbkdf2:sha256:1$ab$' + "0" * 64 + '"'):
        assert not findings_in("devserver/tests/test_x.py", line), line
    assert findings_in("devserver/tests/test_x.py", f'KEY = "{_v("sk-ant-", "a" * 24)}"')
    assert findings_in("devserver/tests/test_x.py", f'password = "{_v("Qe7r!Lp0", "zT4mW")}"')
    assert findings_in("devserver/testfiles/test_mistral.py",
                       f'MISTRAL_API_KEY = "{_v("aB3dE6gH9jK2mN5p", "Q8sT1vW4yZ7")}"')


def test_a_password_hash_outside_tests_is_caught():
    line = 'SETTINGS_PASSWORD_HASH = "pbkdf2:sha256:1000000$' + _v("r1K4k3", "McfLJq") + "$" + "a1" * 32 + '"'
    assert findings_in("devserver/my_app/x.py", line)


def test_the_published_passwords_are_caught_anywhere(monkeypatch):
    value = _v("pub", "lished-test-value")
    monkeypatch.setattr(sys.modules[__name__], "PUBLISHED_PASSWORD_DIGESTS", frozenset({_digest(value)}))
    for rel, line in (("devserver/tests/test_x.py", f'for attempt in ("", "{value}"):'),
                      ("docs/NOTES.md", f"the password {value} stood in the code"),
                      (MESSAGE, f"Default password: '{value}'")):
        assert findings_in(rel, line), (rel, line)


def test_the_exact_secrets_of_this_installation_are_caught():
    value = _v("aB3dE6gH9jK2", "mN5pQ8sT1vW4")
    local = {value: "the content of devserver/mistral.key"}
    found = findings_in("devserver/x.py", f'client = Mistral("{value}")', local)
    assert found == ["devserver/x.py:1  the content of devserver/mistral.key"]
    assert value not in "".join(found)


def test_provider_formats_and_url_credentials_are_caught():
    for line in (_v("-----BEGIN ", "PRIVATE KEY-----"), _v("-----BEGIN PGP ", "PRIVATE KEY BLOCK-----"),
                 _v("PuTTY-User-", "Key-File-3: ssh-ed25519"), _v("AKIA", "ABCDEFGHIJKLMNOP"),
                 _v("ASIA", "ABCDEFGHIJKLMNOP"), _v("ghp_", "a" * 36), _v("github_pat_", "A1b2" * 8),
                 _v("glpat-", "a1B2" * 6), _v("gsk_", "a1B2" * 8), _v("hf_", "b" * 34),
                 _v("eyJhbGciOiJI", "UzI1NiJ9.eyJzdWIiOiIx", "MjM0In0.dozjgNryP4J3jVmNHl0w5N"),
                 _v('"Authorization": "Bearer ', "a1B2c3D4e5F6g7H8i9", '"'),
                 _v("https://user:", "hunter22@example.org/x"), _v("redis://:", "s3cr3tpw@host"),
                 _v("ftp://u:", "pa$sw0rd@host")):
        assert findings_in("docs/x.md", line), line


def test_key_files_are_caught_by_name():
    for rel in ("devserver/mistral.key", "devserver/settings_password.key", "certs/x.pem", ".env",
                "devserver/.env.local", "secrets.env", "server.KEY", "deploy/id_ed25519", ".netrc",
                ".npmrc", "x.ppk", "release.jks", "a/.pypirc"):
        assert findings_for_path(rel), rel
    for rel in (".env.example", "secrets.env.example", "devserver/key_config.py", "docs/keys.md",
                "deploy/id_ed25519.pub"):
        assert not findings_for_path(rel), rel


def test_a_long_line_costs_little():
    import time
    start = time.monotonic()
    findings_in("x.html", "a" * 100_000 + " = 'b'")
    findings_in("x.py", "x = 'y' " + "abcdefgh" * 2_000)
    assert time.monotonic() - start < 2


def test_every_text_file_is_read_whatever_its_name(tmp_path):
    value = _v("Zq8", "#pLm2", "Vw")
    for name in ("x.tsx", "notes.ipynb", "config.json.bak", "CONFIG.JSON", "Dockerfile", "x.DEPRECATED"):
        (tmp_path / name).write_text(f'password = "{value}"\n')
    (tmp_path / "picture.png").write_bytes(b"\x89PNG\0\0" + f'password = "{value}"'.encode())
    found = check_tree(tmp_path)
    assert len(found) == 6, found


def _scratch_repo(tmp_path):
    repo = tmp_path / "repo"
    gate = repo / "devserver" / "tests" / "test_no_secrets_in_code.py"
    gate.parent.mkdir(parents=True)
    gate.write_text(pathlib.Path(__file__).read_text())
    for args in (["init", "-q"], ["config", "user.email", "t@example.org"], ["config", "user.name", "t"]):
        subprocess.run(["git", "-C", str(repo), *args], check=True)
    return repo, gate


def _gate(gate, *args, stdin=""):
    return subprocess.run([sys.executable, str(gate), *args], capture_output=True, text=True, input=stdin,
                          env={k: v for k, v in os.environ.items()
                               if not re.search(r"(?:API_KEY|_KEY|SECRET|TOKEN|PASSWORD)$", k)})


def test_the_staged_mode_reads_every_name_and_fails_closed(tmp_path):
    repo, gate = _scratch_repo(tmp_path)
    value = _v("Zq8", "#pLm2", "Vw")
    (repo / "1:a.py").write_text("x = 1\n")
    (repo / "plain.py").write_text(f'PASSWORD = "{value}"\n')
    subprocess.run(["git", "-C", str(repo), "add", "1:a.py", "plain.py"], check=True)
    answer = _gate(gate, "--staged")
    assert answer.returncode == 1 and "plain.py:1" in answer.stderr
    assert value not in answer.stderr


def test_a_message_is_checked(tmp_path):
    repo, gate = _scratch_repo(tmp_path)
    message = tmp_path / "MSG"
    message.write_text(f"feat: a default\n\n- Password: {_v('Zq8', 'pLm2Vw', 'Tk4')}\n")
    assert _gate(gate, "--message", str(message)).returncode == 1
    message.write_text("fix(auth): the password is set by a command\n")
    assert _gate(gate, "--message", str(message)).returncode == 0


def test_a_push_judges_every_commit_it_sends(tmp_path):
    repo, gate = _scratch_repo(tmp_path)
    git = ["git", "-C", str(repo)]
    (repo / "a.py").write_text("x = 1\n")
    subprocess.run(git + ["add", "a.py"], check=True)
    subprocess.run(git + ["commit", "-q", "-m", "base"], check=True)
    base = subprocess.run(git + ["rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    (repo / "a.py").write_text(f'x = 1\nsecret = "{_v("Zq8", "#pLm2", "Vw")}"\n')
    subprocess.run(git + ["add", "a.py"], check=True)
    subprocess.run(git + ["commit", "-q", "--no-verify", "-m", "more"], check=True)
    head = subprocess.run(git + ["rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    answer = _gate(gate, "--push", stdin=f"refs/heads/main {head} refs/heads/main {base}\n")
    assert answer.returncode == 1 and "a.py:2" in answer.stderr
    assert _gate(gate, "--push", stdin=f"refs/heads/main {base} refs/heads/main {base}\n").returncode == 0


# ---------------------------------------------------------------------------
def _report(bad: list[str], what: str) -> int:
    if not bad:
        return 0
    print(f"\n{what} BLOCKED -- it holds what looks like a password, key or token:\n  "
          + "\n  ".join(bad)
          + "\n\nA secret goes into a file outside the repository or into the environment, "
          "never into the code or a commit message.\nA line that is no secret carries "
          "`not-a-secret:` and a reason of three words or more in a comment (PRAGMA_LINES).\n"
          "Rule and reasoning: devserver/tests/test_no_secrets_in_code.py\n", file=sys.stderr)
    return 1


def _cli(argv: list[str]) -> int:
    local = local_secret_values()
    if "--staged" in argv:
        return _report(_staged(local), "COMMIT")
    if "--message" in argv:
        text = pathlib.Path(argv[argv.index("--message") + 1]).read_text(encoding="utf-8", errors="replace")
        return _report(findings_in(MESSAGE, text, local), "COMMIT MESSAGE")
    if "--push" in argv:
        return _report(_pushed(sys.stdin.read(), local), "PUSH")
    if "--tree" in argv:
        root = pathlib.Path(argv[argv.index("--tree") + 1]).resolve()
        return _report(check_tree(root, local), "EXPORT")
    bad = check_repo(local)
    print("\n".join(bad) if bad else "secrets: none found")
    print(f"lines carrying the pragma: {len(pragma_lines())} (pinned: {PRAGMA_LINES})")
    return 1 if bad else 0


if __name__ == "__main__":
    try:
        raise SystemExit(_cli(sys.argv[1:]))
    except SystemExit:
        raise
    except Exception as error:                               # noqa: BLE001 - fails closed
        print(f"secrets gate could not judge ({type(error).__name__}: {error}); blocked until it can. "
              "Fix the cause; --no-verify is for a broken gate only.", file=sys.stderr)
        raise SystemExit(1)
