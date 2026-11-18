"""
The conditions of use, agreed to with the sign-in; the agreement is kept with
the account, and the conditions stay readable in "My area"
(docs/DEVELOPMENT_DECISIONS.md, 2026-11-15).

Who agrees: every account with a password (course leader, admin), when it
signs in. A place agrees to nothing: the conditions are addressed to the
course leader, who opens the course to its places.

What is kept: a row per agreement (models.TermsAcceptance) with the version,
the moment and the language the text stood in. The text itself is the one in
the frontend under `usageAgreement` (src/i18n/en.ts), unchanged since
2026-03-17; `TERMS_VERSION` names that day.

A new version: when the text of the conditions changes, `TERMS_VERSION` takes
the day of the change, and every account agrees to the new version at its
next sign-in. The text of the old version then has to stay readable under its
version, for the profile shows each account the text it agreed to; today there
is one version and the profile shows the text that stands.

Location: devserver/my_app/lab/terms.py
"""
from __future__ import annotations

from typing import Optional

from .models import Role, TermsAcceptance, User

TERMS_VERSION = "2026-03-17"

# The languages the frontend offers (src/i18n/index.ts, SUPPORTED_LANGUAGES):
# the one the text stood in when the account agreed.
LANGUAGES = frozenset({
    "ar", "bg", "de", "en", "es", "fr", "he", "ko", "tr", "uk", "zh-hant",
})

# What the session remembers of the agreement it signed in with
# (lab/sign_in_gate.py, `signed_in_user`).
SESSION_KEY = "terms_version"


def needs_terms(user: User) -> bool:
    """Whether this account agrees to the conditions when it signs in."""
    return user.role in (Role.admin, Role.educator)


def latest(db, user: User) -> Optional[TermsAcceptance]:
    return (
        db.query(TermsAcceptance)
        .filter(TermsAcceptance.user_id == user.id)
        .order_by(TermsAcceptance.accepted_at.desc(), TermsAcceptance.id.desc())
        .first()
    )


def has_accepted(db, user: User) -> bool:
    """Whether the account has agreed to the version that stands."""
    return db.query(
        db.query(TermsAcceptance).filter(
            TermsAcceptance.user_id == user.id,
            TermsAcceptance.version == TERMS_VERSION,
        ).exists()
    ).scalar()


def record(db, user: User, language: str) -> TermsAcceptance:
    """Keep the account's agreement to the version that stands."""
    row = TermsAcceptance(user_id=user.id, version=TERMS_VERSION, language=language)
    db.add(row)
    db.commit()
    return row
