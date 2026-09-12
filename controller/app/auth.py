import hashlib
import hmac
import re
import secrets
import uuid

from fastapi import Header, HTTPException

STUDENT_ID_RE = re.compile(r"^[A-Za-z0-9._%+\-@]{2,128}$")
AGENT_NS = uuid.UUID("8f3c1e20-6b1a-4d4f-9c3a-2e7b5a91d0aa")


def normalize_student_id(student_id: str) -> str:
    cleaned = (student_id or "").strip().lower()
    if not STUDENT_ID_RE.match(cleaned):
        raise HTTPException(status_code=400, detail="invalid student_id")
    return cleaned


def agent_id_for_student(student_id: str) -> str:
    return str(uuid.uuid5(AGENT_NS, student_id))


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_matches(token: str, token_hash: str) -> bool:
    if not token or not token_hash:
        return False
    return hmac.compare_digest(hash_token(token), token_hash)


def new_agent_token() -> str:
    return secrets.token_urlsafe(32)


def bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="missing bearer token")
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value:
        raise HTTPException(status_code=401, detail="missing bearer token")
    return value.strip()


def require_enrollment_key(settings_key: str, provided: str | None) -> None:
    if not settings_key:
        raise HTTPException(status_code=503, detail="enrollment is not configured")
    if not provided or not hmac.compare_digest(provided, settings_key):
        raise HTTPException(status_code=401, detail="invalid enrollment key")


def require_admin_token(
    settings_token: str, authorization: str | None = Header(default=None)
) -> None:
    if not settings_token:
        raise HTTPException(status_code=503, detail="admin auth is not configured")
    token = bearer_token(authorization)
    if not hmac.compare_digest(token, settings_token):
        raise HTTPException(status_code=401, detail="invalid admin token")
