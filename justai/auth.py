#!/usr/bin/env python3
"""
JustAi — Authentication
========================
JWT-based authentication with bcrypt password hashing.

Modes:
  1. Single-user mode (default): No authentication required.
     Set JUSTAI_AUTH_ENABLED=false or leave unset.
  2. Multi-user mode: JWT tokens required for all API endpoints.
     Set JUSTAI_AUTH_ENABLED=true and configure JUSTAI_JWT_SECRET.

Usage:
    from justai.auth import AuthManager

    auth = AuthManager()
    auth.register("admin", "password123", role="admin")
    token = auth.login("admin", "password123")
    user = auth.verify(token)
    assert user.username == "admin"
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass
from pathlib import Path

# ── Config ───────────────────────────────────────────────────────────────────

AUTH_ENABLED = os.environ.get("JUSTAI_AUTH_ENABLED", "").lower() in ("1", "true", "yes")
JWT_SECRET = os.environ.get("JUSTAI_JWT_SECRET", "justai-dev-secret-change-me")
JWT_EXPIRY_SECONDS = int(os.environ.get("JUSTAI_JWT_EXPIRY", "86400"))  # 24h default
DEFAULT_DB_PATH = os.environ.get(
    "JUSTAI_AUTH_DB",
    str(Path(__file__).resolve().parent.parent / "data" / "auth.db"),
)


# ── Data Types ──────────────────────────────────────────────────────────────


@dataclass
class User:
    id: int
    username: str
    role: str  # "admin" | "operator"
    created_at: float


@dataclass
class AuthResult:
    success: bool
    token: str = ""
    user: User | None = None
    error: str = ""


# ── Password Hashing ────────────────────────────────────────────────────────
# Uses PBKDF2-HMAC-SHA256 (stdlib, no bcrypt dependency needed).

_HASH_ITERATIONS = 100_000
_SALT_LENGTH = 32


def hash_password(password: str) -> str:
    """Hash a password with PBKDF2-HMAC-SHA256. Returns 'salt:hash' string."""
    salt = os.urandom(_SALT_LENGTH)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _HASH_ITERATIONS)
    return f"{salt.hex()}:{dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Verify a password against a stored 'salt:hash' string."""
    try:
        salt_hex, hash_hex = stored.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _HASH_ITERATIONS)
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False


# ── JWT (minimal, stdlib-only) ──────────────────────────────────────────────


def _b64(data: bytes) -> str:
    return urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    padding = 4 - len(s) % 4
    return urlsafe_b64decode(s + "=" * padding)


def create_jwt(payload: dict, secret: str = JWT_SECRET, expiry: int = JWT_EXPIRY_SECONDS) -> str:
    """Create a minimal JWT (HS256)."""
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload_data = {**payload, "exp": int(time.time()) + expiry, "iat": int(time.time())}
    body = _b64(json.dumps(payload_data).encode())
    sig_input = f"{header}.{body}".encode()
    sig = _b64(hmac.new(secret.encode(), sig_input, hashlib.sha256).digest())
    return f"{header}.{body}.{sig}"


def verify_jwt(token: str, secret: str = JWT_SECRET) -> dict | None:
    """Verify a JWT token. Returns the payload dict or None if invalid."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b, body_b, sig_b = parts

        # Verify signature
        sig_input = f"{header_b}.{body_b}".encode()
        expected_sig = _b64(hmac.new(secret.encode(), sig_input, hashlib.sha256).digest())
        if not hmac.compare_digest(sig_b, expected_sig):
            return None

        # Decode payload
        payload = json.loads(_unb64(body_b))

        # Check expiry
        if payload.get("exp", 0) < time.time():
            return None

        return payload
    except Exception:
        return None


# ── Auth Manager ─────────────────────────────────────────────────────────────


class AuthManager:
    """User management and authentication."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._ensure_db()

    def _ensure_db(self) -> None:
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'operator',
                    created_at REAL NOT NULL
                )
            """)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def is_enabled() -> bool:
        """Check if authentication is enabled."""
        return AUTH_ENABLED

    def register(self, username: str, password: str, role: str = "operator") -> AuthResult:
        """Register a new user."""
        if not username or not password:
            return AuthResult(success=False, error="Username and password required")
        if len(password) < 6:
            return AuthResult(success=False, error="Password must be at least 6 characters")
        if role not in ("admin", "operator"):
            return AuthResult(success=False, error="Role must be 'admin' or 'operator'")

        pw_hash = hash_password(password)
        try:
            with self._conn() as conn:
                conn.execute(
                    "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                    (username, pw_hash, role, time.time()),
                )
            return AuthResult(success=True)
        except sqlite3.IntegrityError:
            return AuthResult(success=False, error="Username already exists")

    def login(self, username: str, password: str) -> AuthResult:
        """Authenticate a user and return a JWT token."""
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

        if not row:
            return AuthResult(success=False, error="Invalid credentials")

        if not verify_password(password, row["password_hash"]):
            return AuthResult(success=False, error="Invalid credentials")

        user = User(
            id=row["id"],
            username=row["username"],
            role=row["role"],
            created_at=row["created_at"],
        )
        token = create_jwt(
            {
                "sub": user.username,
                "role": user.role,
                "uid": user.id,
            }
        )
        return AuthResult(success=True, token=token, user=user)

    def verify(self, token: str) -> User | None:
        """Verify a JWT token and return the User, or None if invalid."""
        payload = verify_jwt(token)
        if not payload:
            return None

        with self._conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (payload.get("uid"),)).fetchone()

        if not row:
            return None

        return User(
            id=row["id"],
            username=row["username"],
            role=row["role"],
            created_at=row["created_at"],
        )

    def list_users(self) -> list[User]:
        """List all users (admin only)."""
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM users ORDER BY created_at").fetchall()
            return [
                User(id=r["id"], username=r["username"], role=r["role"], created_at=r["created_at"])
                for r in rows
            ]

    def delete_user(self, username: str) -> bool:
        """Delete a user by username."""
        with self._conn() as conn:
            cursor = conn.execute("DELETE FROM users WHERE username = ?", (username,))
            return cursor.rowcount > 0
