"""Security primitives: JWT tokens, password hashing, and envelope encryption.

- Passwords: bcrypt via passlib.
- API keys at rest: AES-256-GCM (envelope) encrypted with the platform master key.
- RSA keypairs: used for the simulated mutual-TLS node handshake.
"""
from __future__ import annotations

import base64
import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _master_key() -> bytes:
    """Derive the AES-256 master key from SECRET_KEY (deterministic per deployment)."""
    return hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------
def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------
def create_access_token(subject: str, claims: Optional[Dict[str, Any]] = None, expires_minutes: Optional[int] = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload: Dict[str, Any] = {"sub": subject, "exp": expire, "iat": datetime.now(timezone.utc)}
    if claims:
        payload.update(claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str) -> str:
    return create_access_token(subject, expires_minutes=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60)


def decode_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


# ---------------------------------------------------------------------------
# AES-256-GCM envelope encryption (for secrets like AI provider API keys)
# ---------------------------------------------------------------------------
def encrypt_secret(plaintext: str) -> str:
    key = _master_key()
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_secret(token: str) -> str:
    key = _master_key()
    raw = base64.b64decode(token.encode("ascii"))
    nonce, ciphertext = raw[:12], raw[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")


def mask_key(secret: str) -> str:
    """Return a masked display representation: sk-****abcd."""
    if len(secret) <= 8:
        return "****"
    return f"{secret[:3]}****{secret[-4:]}"


# ---------------------------------------------------------------------------
# AES-256-GCM payload encryption (for encrypted model updates in transit)
# ---------------------------------------------------------------------------
def encrypt_bytes(payload: bytes, key: bytes) -> bytes:
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    return nonce + aesgcm.encrypt(nonce, payload, None)


def decrypt_bytes(payload: bytes, key: bytes) -> bytes:
    nonce, ciphertext = payload[:12], payload[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


# ---------------------------------------------------------------------------
# RSA (simulated mTLS node identities)
# ---------------------------------------------------------------------------
def generate_rsa_keypair(bits: Optional[int] = None) -> Dict[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=bits or settings.RSA_KEY_BITS)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return {"private_key": private_pem, "public_key": public_pem}


def rsa_sign(private_key_pem: str, message: bytes) -> str:
    key = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
    signature = key.sign(message, padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(signature).decode("ascii")


def rsa_verify(public_key_pem: str, message: bytes, signature_b64: str) -> bool:
    try:
        key = serialization.load_pem_public_key(public_key_pem.encode())
        key.verify(base64.b64decode(signature_b64.encode()), message, padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False
