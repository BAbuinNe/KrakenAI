"""Restart-safe signed HTTP-only session tokens.

Tokens are MAC-signed and expire after 14 days, even across Render restarts.
Signing key is derived from the configured secret APP_PASSWORD (or optional
APP_SESSION_SECRET). Password/secret rotation invalidates old tokens.
"""
from __future__ import annotations
import hashlib
import hmac
import os
import secrets
import time

SESSION_AGE = 14 * 24 * 60 * 60
VERSION = "v1"


def _key(password: str) -> bytes:
    extra=os.getenv("APP_SESSION_SECRET")
    # An optional independent key is recommended when available.
    if extra:
        if len(extra)<32:
            raise ValueError("APP_SESSION_SECRET must be at least 32 characters")
        secret=extra
    else:
        secret=password
    return hashlib.sha256(b"krakenai/signed-cookie/v1\0"+secret.encode("utf-8")).digest()


def create(password:str,now:float|None=None)->str:
    current=int(time.time() if now is None else now)
    expires=current+SESSION_AGE
    payload=f"{VERSION}.{expires}.{secrets.token_urlsafe(24)}"
    mac=hmac.new(_key(password),payload.encode("ascii"),hashlib.sha256).hexdigest()
    return payload+"."+mac


def valid(token:str,password:str,now:float|None=None)->bool:
    if not token or len(token)>256:
        return False
    parts=token.split(".")
    if len(parts)!=4 or parts[0]!=VERSION:return False
    try:
        expires=int(parts[1])
        nonce=parts[2]
        if not nonce or not nonce.isascii() or len(nonce)>64:return False
        current=int(time.time() if now is None else now)
        if expires<=current or expires>current+SESSION_AGE:return False
        mac=parts[3]
        if len(mac)!=64:return False
        expected=hmac.new(_key(password),".".join(parts[:3]).encode("ascii"),
                          hashlib.sha256).hexdigest()
        return hmac.compare_digest(mac,expected)
    except (ValueError,UnicodeEncodeError,OverflowError):
        return False
