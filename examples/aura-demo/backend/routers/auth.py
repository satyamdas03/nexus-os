"""Authentication endpoints for ASSURE.

- POST /auth/token   — login, returns JWT access token.
- GET  /auth/me      — current user profile.
- POST /auth/users   — admin only: create/update a user.
- GET  /auth/users   — admin only: list users (no password hashes).
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.data_loader import get_conn_cached
from core.auth import (
    authenticate,
    create_access_token,
    create_user,
    get_current_user,
    require_admin,
)

router = APIRouter()


class TokenRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    role: str
    username: str


class UserCreate(BaseModel):
    username: str
    password: str
    role: str  # viewer | adviser | admin
    assigned_adviser_filter: Optional[str] = None
    disabled: bool = False


class UserOut(BaseModel):
    username: str
    role: str
    assigned_adviser_filter: Optional[str]
    disabled: bool


@router.post("/auth/token", response_model=TokenResponse)
def login(body: TokenRequest):
    user = authenticate(body.username, body.password)
    if not user or user.get("disabled"):
        raise HTTPException(status_code=401, detail="Invalid credentials or disabled account")
    token = create_access_token(
        {"sub": user["username"], "role": user["role"], "filter": user.get("assigned_adviser_filter")},
        expires_delta=timedelta(days=7),
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user["role"],
        "username": user["username"],
    }


@router.get("/auth/me", response_model=UserOut)
def me(user = Depends(get_current_user)):
    return {
        "username": user.username,
        "role": user.role,
        "assigned_adviser_filter": user.assigned_adviser_filter,
        "disabled": user.disabled,
    }


@router.post("/auth/users", response_model=UserOut)
def create(body: UserCreate, _admin=Depends(require_admin)):
    if body.role not in ("viewer", "adviser", "admin"):
        raise HTTPException(status_code=400, detail="role must be viewer, adviser, or admin")
    conn = get_conn_cached()
    u = create_user(
        conn,
        body.username,
        body.password,
        body.role,
        assigned_adviser_filter=body.assigned_adviser_filter,
        disabled=body.disabled,
    )
    return {
        "username": u.username,
        "role": u.role,
        "assigned_adviser_filter": u.assigned_adviser_filter,
        "disabled": u.disabled,
    }


@router.get("/auth/users")
def list_users(_admin=Depends(require_admin)):
    conn = get_conn_cached()
    rows = conn.execute(
        "SELECT username, role, assigned_adviser_filter, disabled FROM users ORDER BY username"
    ).fetchall()
    return [
        {
            "username": r["username"],
            "role": r["role"],
            "assigned_adviser_filter": r["assigned_adviser_filter"],
            "disabled": bool(r["disabled"]),
        }
        for r in rows
    ]
