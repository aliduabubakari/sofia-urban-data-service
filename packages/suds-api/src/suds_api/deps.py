from __future__ import annotations

from typing import Iterator, Set

from fastapi import Depends, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy.orm import Session

from suds_core.config.settings import get_settings
from suds_core.db.engine import get_session_factory

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _allowed_keys() -> Set[str]:
    settings = get_settings()
    raw = settings.api_keys or ""
    return {k.strip() for k in raw.split(",") if k.strip()}


def require_api_key(api_key: str | None = Security(_api_key_header)) -> None:
    allowed = _allowed_keys()
    if not allowed:
        raise HTTPException(status_code=500, detail="Server misconfigured: no SUDS_API_KEYS set")
    if api_key is None or api_key not in allowed:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

def get_db_session() -> Iterator[Session]:
    SessionLocal = get_session_factory()
    session = SessionLocal()
    try:
        yield session
        session.commit()         # <-- key line
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# Convenience dependency combo
AuthDep = Depends(require_api_key)
DbDep = Depends(get_db_session)