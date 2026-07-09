
import ipaddress
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import pyotp
from jose import JWTError, jwt
from passlib.context import CryptContext

from Bot_mini_map_ai.config.settings import settings

logger = logging.getLogger(__name__)

# ─── Password ────────────────────────────────────────────────────────────────
_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain: str) -> bool:
    stored = settings.ADMIN_PASSWORD
    if stored.startswith("$2"):
        return _pwd_ctx.verify(plain, stored)
    return plain == stored


def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


# ─── TOTP ─────────────────────────────────────────────────────────────────────
_TOTP_SECRET_ENV_KEY = "ADMIN_TOTP_SECRET"


def get_or_create_totp_secret() -> str:
    secret = settings.ADMIN_TOTP_SECRET
    if not secret:
        secret = pyotp.random_base32()
        logger.warning(
            "\n⚠️ADMIN_TOTP_SECRET not set.\n"
            "Generated a new secret for this session:\n"
            "Add it to .env as ADMIN_TOTP_SECRET=%s\n"
            "Then scan the QR code at GET /admin/setup-qr\n",
            secret,
        )
        settings.__dict__["ADMIN_TOTP_SECRET"] = secret
    return secret


def get_totp_uri(secret: str) -> str:
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name="admin", issuer_name="RoadMap AI")


def verify_totp(code: str) -> bool:
    secret = get_or_create_totp_secret()
    totp = pyotp.TOTP(secret)
    return totp.verify(code.strip(), valid_window=1)


# ─── JWT ─────────────────────────────────────────────────────────────────────
_ALGORITHM = "HS256"


def create_access_token() -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ADMIN_JWT_TTL_MINUTES
    )
    payload = {"sub": "admin", "exp": expire}
    return jwt.encode(payload, settings.ADMIN_JWT_SECRET, algorithm=_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.ADMIN_JWT_SECRET, algorithms=[_ALGORITHM])
    except JWTError:
        return None


def is_token_valid(token: str) -> bool:
    return decode_token(token) is not None


# ─── IP whitelist ─────────────────────────────────────────────────────────────
def is_ip_allowed(client_ip: str) -> bool:
    whitelist = settings.ip_whitelist
    if not whitelist:
        return True

    try:
        addr = ipaddress.ip_address(client_ip)
    except ValueError:
        return False

    for entry in whitelist:
        try:
            if "/" in entry:
                if addr in ipaddress.ip_network(entry, strict=False):
                    return True
            else:
                if addr == ipaddress.ip_address(entry):
                    return True
        except ValueError:
            logger.warning("Invalid IP in whitelist: %s", entry)

    return False
