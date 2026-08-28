from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import timedelta

from sqlalchemy import delete, select

from .config import settings
from .database import SessionLocal, SessionToken, User, utcnow

PBKDF2_ITERATIONS = 600_000
SESSION_COOKIE = "teaguard_session"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(user_id: int) -> tuple[str, str]:
    raw = secrets.token_urlsafe(48)
    csrf = secrets.token_urlsafe(32)
    expires = utcnow() + timedelta(hours=settings.session_hours)
    with SessionLocal() as db:
        db.add(SessionToken(token_hash=_token_hash(raw), csrf_token=csrf, user_id=user_id, expires_at=expires))
        db.commit()
    return raw, csrf


def resolve_session(raw_token: str | None) -> tuple[User | None, str | None]:
    if not raw_token:
        return None, None
    now = utcnow()
    with SessionLocal() as db:
        row = db.execute(select(SessionToken).where(SessionToken.token_hash == _token_hash(raw_token))).scalar_one_or_none()
        if not row:
            return None, None
        expires = row.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=now.tzinfo)
        if expires <= now:
            db.delete(row)
            db.commit()
            return None, None
        user = db.get(User, row.user_id)
        if not user or not user.is_active:
            return None, None
        db.expunge(user)
        return user, row.csrf_token


def delete_session(raw_token: str | None) -> None:
    if not raw_token:
        return
    with SessionLocal() as db:
        db.execute(delete(SessionToken).where(SessionToken.token_hash == _token_hash(raw_token)))
        db.commit()
