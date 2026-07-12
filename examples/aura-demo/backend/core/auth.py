"""Authentication + RBAC for ASSURE backend.

Pilot design:
- JWT bearer tokens signed with AUTH_SECRET.
- Three roles: viewer (read-only), adviser (read + approve trades), admin (all).
- Users live in the same SQLite DB as the book for operational simplicity.
- A bootstrap admin is created on startup from AUTH_ADMIN_USERNAME / AUTH_ADMIN_PASSWORD
  so the first login never requires a shell.
- Advisers can be scoped to one adviser name via assigned_adviser_filter; admin can see all.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext

from core import storage
from core.data_loader import get_conn_cached

_ALGORITHM = "HS256"
_ACCESS_TOKEN_EXPIRE_DAYS = int(os.environ.get("ACCESS_TOKEN_EXPIRE_DAYS", "7"))

_security = HTTPBearer(auto_error=False)
_pwd_ctx = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def _secret() -> str:
    """Read AUTH_SECRET at call time so tests can toggle it between imports.

    When AUTH_ENFORCE is enabled (the default), a missing or empty AUTH_SECRET
    is a fatal configuration error and the backend refuses to start. Dev-only
    fallback is allowed only when AUTH_ENFORCE=0 is explicitly set.
    """
    secret = os.environ.get("AUTH_SECRET", "")
    if not secret:
        if _auth_enforce():
            raise RuntimeError(
                "AUTH_SECRET is required and must not be empty when AUTH_ENFORCE is enabled. "
                "Set AUTH_SECRET to a strong random secret, or explicitly disable enforcement "
                "for local development with AUTH_ENFORCE=0 (never in production)."
            )
        # Dev fallback: never used when enforcement is on.
        return "dev-insecure-placeholder-change-me"
    return secret


def _auth_enforce() -> bool:
    """Read AUTH_ENFORCE at call time.

    Auth enforcement is ON by default. Set AUTH_ENFORCE=0 to disable it.
    """
    return os.environ.get("AUTH_ENFORCE", "1").lower() not in ("0", "false", "off")


def hash_password(password: str) -> str:
    return _pwd_ctx.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _pwd_ctx.verify(password, hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(days=_ACCESS_TOKEN_EXPIRE_DAYS)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, _secret(), algorithm=_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, _secret(), algorithms=[_ALGORITHM])


class User:
    def __init__(
        self,
        username: str,
        role: str,
        assigned_adviser_filter: Optional[str] = None,
        disabled: bool = False,
    ):
        self.username = username
        self.role = role
        self.assigned_adviser_filter = assigned_adviser_filter
        self.disabled = disabled


def _row_to_user(row) -> User:
    return User(
        username=row["username"],
        role=row["role"],
        assigned_adviser_filter=row["assigned_adviser_filter"] if row["assigned_adviser_filter"] else None,
        disabled=bool(row["disabled"] if row["disabled"] is not None else 0),
    )


def get_user(conn, username: str) -> Optional[User]:
    row = conn.execute(
        "SELECT username, role, assigned_adviser_filter, disabled FROM users WHERE username=?",
        (username,),
    ).fetchone()
    return _row_to_user(row) if row else None


def authenticate(username: str, password: str) -> Optional[dict]:
    conn = get_conn_cached()
    row = conn.execute(
        "SELECT username, hashed_password, role, assigned_adviser_filter, disabled "
        "FROM users WHERE username=?",
        (username,),
    ).fetchone()
    if not row:
        return None
    if not verify_password(password, row["hashed_password"]):
        return None
    return {
        "username": row["username"],
        "role": row["role"],
        "assigned_adviser_filter": row["assigned_adviser_filter"],
        "disabled": bool(row["disabled"]),
    }


def create_user(
    conn,
    username: str,
    password: str,
    role: str,
    assigned_adviser_filter: Optional[str] = None,
    disabled: bool = False,
) -> User:
    """Create or replace a user. Admin-only in production."""
    conn.execute(
        "INSERT OR REPLACE INTO users(username, hashed_password, role, assigned_adviser_filter, disabled) "
        "VALUES (?, ?, ?, ?, ?)",
        (username, hash_password(password), role, assigned_adviser_filter, int(disabled)),
    )
    conn.commit()
    return get_user(conn, username)


def _token_user(token: Optional[str]) -> Optional[User]:
    if not token:
        return None
    try:
        payload = decode_token(token)
        username: Optional[str] = payload.get("sub")
        if username is None:
            return None
    except JWTError:
        return None
    conn = get_conn_cached()
    return get_user(conn, username)


def _extract_token(credentials: Optional[HTTPAuthorizationCredentials]) -> Optional[str]:
    if credentials is None:
        return None
    scheme, _, param = credentials.credentials.partition(" ")
    # Accept "Bearer <token>" or raw token for simpler curl scripts.
    token = param if scheme.lower() == "bearer" else credentials.credentials
    return token


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
) -> User:
    """Strict dependency: requires a valid bearer token in all environments."""
    token = _extract_token(credentials)
    user = _token_user(token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.disabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User disabled")
    return user


async def get_current_user_or_dev(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
) -> User:
    """Production-safe dependency: enforces tokens when AUTH_ENFORCE is set;
    in dev mode without enforcement, missing credentials return a synthetic
    admin so local demos and existing tests work unchanged.
    """
    token = _extract_token(credentials)
    user = _token_user(token)
    if user is not None:
        if user.disabled:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User disabled")
        return user
    if _auth_enforce():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Dev fallback: never in production because AUTH_SECRET is set and ideally
    # AUTH_ENFORCE is enabled.
    return User(username="dev-admin", role="admin")


async def require_admin(user: User = Depends(get_current_user_or_dev)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return user


async def require_adviser_or_admin(user: User = Depends(get_current_user_or_dev)) -> User:
    if user.role not in ("adviser", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Adviser or admin required")
    return user


async def require_mutation(user: User = Depends(get_current_user_or_dev)) -> User:
    if user.role not in ("adviser", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Mutation not permitted")
    return user


def ensure_bootstrap_admin() -> None:
    """Create the bootstrap admin user if the users table is empty.

    Runs once at startup. When AUTH_ENFORCE is enabled (the default),
    AUTH_ADMIN_PASSWORD is required and boot fails loudly if it is missing or
    empty. Dev-only fallback is allowed only when AUTH_ENFORCE=0.
    """
    # Validate AUTH_SECRET at startup so the backend refuses to boot when it is
    # missing and enforcement is enabled.
    _ = _secret()
    admin_user = os.environ.get("AUTH_ADMIN_USERNAME", "admin")
    admin_pass = os.environ.get("AUTH_ADMIN_PASSWORD", "")
    if not admin_user or not admin_pass:
        if _auth_enforce():
            raise RuntimeError(
                "AUTH_ADMIN_PASSWORD is required and must not be empty when AUTH_ENFORCE is enabled. "
                "Set AUTH_ADMIN_PASSWORD to a strong random password, or explicitly disable "
                "enforcement for local development with AUTH_ENFORCE=0 (never in production)."
            )
        return
    conn = get_conn_cached()
    count = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
    if count == 0:
        create_user(conn, admin_user, admin_pass, "admin")


def _users_schema() -> str:
    return """
    CREATE TABLE IF NOT EXISTS users (
      username TEXT PRIMARY KEY,
      hashed_password TEXT NOT NULL,
      role TEXT NOT NULL CHECK(role IN ('viewer', 'adviser', 'admin')),
      assigned_adviser_filter TEXT,
      disabled INTEGER DEFAULT 0
    );
    """


storage._SCHEMA += _users_schema()
