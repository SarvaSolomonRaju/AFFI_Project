from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

_KEY_FILE = Path(os.environ.get("AFFI_API_KEYS_FILE", "config/api_keys.json"))

_KEYS: dict[str, dict] = {}


def _load_keys() -> dict[str, dict]:
    global _KEYS
    if _KEYS:
        return _KEYS
    if _KEY_FILE.exists():
        import json
        raw = json.loads(_KEY_FILE.read_text())
        _KEYS = {entry["key_hash"]: entry for entry in raw.get("keys", [])}
    return _KEYS


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_api_key(owner: str, role: str = "readonly") -> dict:
    raw_key = f"affi_{secrets.token_urlsafe(32)}"
    key_hash = hash_api_key(raw_key)
    record = {
        "key_hash": key_hash,
        "owner": owner,
        "role": role,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "active": True,
    }
    return {"raw_key": raw_key, "record": record}


async def validate_api_key(
    api_key: Optional[str] = Security(API_KEY_HEADER),
) -> dict:
    if os.environ.get("AFFI_AUTH_DISABLED", "").lower() in ("1", "true", "yes"):
        return {"owner": "dev-mode", "role": "admin"}

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    keys = _load_keys()
    key_hash = hash_api_key(api_key)
    entry = keys.get(key_hash)

    if entry is None or not entry.get("active", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or revoked API key",
        )
    return entry


def require_role(required: str):
    async def _check(user: dict = Depends(validate_api_key)):
        role_hierarchy = {"readonly": 0, "operator": 1, "admin": 2}
        if role_hierarchy.get(user.get("role", ""), -1) < role_hierarchy.get(required, 99):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {required}",
            )
        return user
    return _check
