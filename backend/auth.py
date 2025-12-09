# backend/auth.py
import os
from typing import Callable, Optional
from fastapi import Header, HTTPException, Depends, status
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE")

# create supabase client (service role key required server-side only)
supabase = create_client(SUPABASE_URL, SERVICE_ROLE_KEY)


async def get_current_user(authorization: Optional[str] = Header(None)):
    """
    Validate 'Authorization: Bearer <token>' via Supabase Auth.
    Returns dict: {id, email, role}
    Raises 401 on missing/invalid token.
    """
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")

    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Authorization header format")

    token = authorization.split(" ", 1)[1].strip()

    # Validate token via Supabase Auth (client library versions differ in return shapes)
    try:
        resp = supabase.auth.get_user(token)
        # resp may be object-like with .user or dict-like
        user_obj = None
        if isinstance(resp, dict):
            # common shapes: {"data": {"user": {...}}} or {"user": {...}}
            data = resp.get("data") or resp
            user_obj = data.get("user") or data
        else:
            # object-like; try .user then .data
            user_obj = getattr(resp, "user", None)
            if not user_obj:
                possible = getattr(resp, "data", None)
                if isinstance(possible, dict):
                    user_obj = possible.get("user") or possible

    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    # normalize user object into id/email
    if not user_obj:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token (no user)")

    user_id = getattr(user_obj, "id", None) or (user_obj.get("id") if isinstance(user_obj, dict) else None)
    email = getattr(user_obj, "email", None) or (user_obj.get("email") if isinstance(user_obj, dict) else None)

    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token (missing user id)")

    # Fetch role from profiles table (may return dict or object with .data)
    role = None
    try:
        prof = supabase.table("profiles").select("role").eq("id", user_id).maybe_single().execute()
        # prof may be dict-like or object-like
        if isinstance(prof, dict):
            data = prof.get("data") or prof
            if isinstance(data, dict):
                # data could be {"role": "..."} or {"user": {...}}
                role = data.get("role") or (data.get("data") or {}).get("role")
        else:
            # object-like
            data_attr = getattr(prof, "data", None)
            if isinstance(data_attr, dict):
                role = data_attr.get("role")
    except Exception:
        # ignore DB/profile lookup errors and default to 'student' below
        role = None

    return {"id": user_id, "email": email, "role": (role or "student")}


# -------------------------
# ROLE CHECK DEPENDENCIES
# -------------------------

def require_role(role_name: str) -> Callable:
    """
    Dependency factory that allows only users with exact role_name or 'admin'.
    Returns the profile dict from get_current_user (containing id/email/role).
    """
    async def _dep(current_user=Depends(get_current_user)):
        user_role = (current_user.get("role") or "").lower()
        if user_role != role_name.lower() and user_role != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return current_user
    return _dep


def require_any_role(*roles: str) -> Callable:
    """
    Dependency factory that allows any of the provided roles (case-insensitive) or admin.
    Usage: Depends(require_any_role("teacher", "student"))
    """
    allowed = [r.lower() for r in roles]

    async def _dep(current_user=Depends(get_current_user)):
        user_role = (current_user.get("role") or "").lower()
        if user_role == "admin" or user_role in allowed:
            return current_user
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    return _dep


def require_role_from_table(role_name: str) -> Callable:
    """
    Backwards-compatible wrapper for older code that imports require_role_from_table.
    """
    return require_role(role_name)