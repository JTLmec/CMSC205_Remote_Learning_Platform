# backend/core/auth.py
import traceback
from typing import Optional, Callable, List, Dict, Any

from fastapi import Header, HTTPException, status
from supabase import create_client
from core import config
import logging

logger = logging.getLogger("uvicorn.error")

# Validate config early so deploy fails fast with helpful message
if not getattr(config, "SUPABASE_URL", None) or not (
    getattr(config, "SUPABASE_SERVICE_ROLE", None) or getattr(config, "SUPABASE_ANON_KEY", None)
):
    raise RuntimeError(
        "Supabase configuration missing. Ensure SUPABASE_URL and SUPABASE_SERVICE_ROLE (preferred) "
        "or SUPABASE_ANON_KEY are set in backend/.env or Render environment variables."
    )

# Use service role for server-side queries (required)
SUPABASE_KEY = config.SUPABASE_SERVICE_ROLE or config.SUPABASE_ANON_KEY
_supabase_admin = create_client(config.SUPABASE_URL, SUPABASE_KEY)


async def _get_user_id_from_token(authorization: Optional[str]) -> str:
    """
    Extract user id from the incoming Authorization header by asking Supabase's get_user.
    Expects header like: "Bearer <access_token>".
    Raises HTTPException(401) on error.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid Authorization header")

    token = authorization.split(" ", 1)[1].strip()

    # -----------------------
    # AUTH DEBUG (masked)
    # -----------------------
    try:
        if token and isinstance(token, str):
            masked_token = token[:20] + "..." + token[-8:] if len(token) > 40 else token[:10] + "..."
        else:
            masked_token = "<no-token>"
    except Exception:
        masked_token = "<mask-error>"
    print(f"[AUTH-DEBUG] incoming Authorization (masked): {masked_token}", flush=True)
    # -----------------------

    try:
        # Use supabase's auth.get_user to validate token and retrieve user info
        resp = _supabase_admin.auth.get_user(token)

        # Normalize different client return shapes
        user = None
        if isinstance(resp, dict) and "data" in resp:
            # resp may be { "data": { "user": {...} } } or { "data": {...} }
            data = resp.get("data") or {}
            user = data.get("user") or data
        elif hasattr(resp, "data"):
            # some versions return an object with .data
            data = getattr(resp, "data", None)
            if isinstance(data, dict) and "user" in data:
                user = data["user"]
            else:
                user = data
        else:
            user = resp

        # user can be dict-like or object-like
        user_id = None
        if isinstance(user, dict):
            user_id = user.get("id") or (user.get("user") and user.get("user").get("id"))
        else:
            user_id = getattr(user, "id", None)

        # -----------------------
        # AUTH DEBUG (user info)
        # -----------------------
        print(f"[AUTH-DEBUG] get_user response shape: type={type(resp).__name__}; user_id_extracted={user_id!r}", flush=True)
        # -----------------------

        if not user_id:
            raise Exception("User id not found from token")

        return user_id
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}")


def _fetch_profile(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Query the 'profiles' table (created by your SQL trigger) for the user's profile.
    Returns a dict or None.
    """
    if not user_id:
        return None
    try:
        # .execute() return shape varies by client version; normalize afterward
        res = _supabase_admin.table("profiles").select("*").eq("id", user_id).limit(1).execute()
        data = None
        if isinstance(res, dict):
            data = res.get("data")
        elif hasattr(res, "data"):
            data = getattr(res, "data", None)

        if data:
            # data might be a list (rows) or a dict (single row)
            if isinstance(data, list) and len(data) > 0:
                profile = data[0]
            elif isinstance(data, dict):
                profile = data
            else:
                profile = None
        else:
            profile = None

        # -----------------------
        # AUTH DEBUG (profile lookup)
        # -----------------------
        print(f"[AUTH-DEBUG] profile_lookup_result for user_id={user_id!r}: {profile!r}", flush=True)
        # -----------------------

        return profile
    except Exception:
        traceback.print_exc()
    return None


def require_role(required_role: str) -> Callable:
    """
    Returns a FastAPI dependency that requires the authenticated user to have `required_role`.
    Admin role is treated as a super-role (allowed for all).
    Usage:
        @router.post("/upload")
        async def upload(..., profile = Depends(require_role("teacher"))):
            # 'profile' is the profile dict from 'profiles' table
    """
    async def _dependency(authorization: Optional[str] = Header(None)):
        user_id = await _get_user_id_from_token(authorization)
        profile = _fetch_profile(user_id)
        if not profile:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User profile not found")

        user_role = (profile.get("role") or "").lower()

        if user_role == required_role.lower() or user_role == "admin":
            return profile

        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")

    return _dependency


def require_any_role(allowed_roles: List[str]) -> Callable:
    """
    Dependency that allows any role in allowed_roles (case-insensitive).
    Admin is always allowed.
    Example: Depends(require_any_role(["teacher","student"]))
    """
    allowed_lower = [r.lower() for r in allowed_roles]

    async def _get_user_id_from_token(authorization: Optional[str]) -> str:
        """
         Extract user id from the incoming Authorization header by asking Supabase's get_user.
         Expects header like: "Bearer <access_token>".
         Raises HTTPException(401) on error.
         """
    import sys

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid Authorization header")

    token = authorization.split(" ", 1)[1].strip()

    # -----------------------
    # AUTH DEBUG (masked) - log to both logger and stderr to guarantee visibility
    # -----------------------
    try:
        if token and isinstance(token, str):
            masked_token = token[:20] + "..." + token[-8:] if len(token) > 40 else token[:10] + "..."
        else:
            masked_token = "<no-token>"
    except Exception:
        masked_token = "<mask-error>"

    # logger (normal)
    logger.warning(f"[AUTH-DEBUG] incoming Authorization (masked): {masked_token}")
    # guaranteed stderr write
    try:
        sys.stderr.write(f"[AUTH-DEBUG] incoming Authorization (masked): {masked_token}\n")
        sys.stderr.flush()
    except Exception:
        pass
    # -----------------------

    try:
        # Use supabase's auth.get_user to validate token and retrieve user info
        resp = _supabase_admin.auth.get_user(token)

        # Normalize different client return shapes
        user = None
        if isinstance(resp, dict) and "data" in resp:
            data = resp.get("data") or {}
            user = data.get("user") or data
        elif hasattr(resp, "data"):
            data = getattr(resp, "data", None)
            if isinstance(data, dict) and "user" in data:
                user = data["user"]
            else:
                user = data
        else:
            user = resp

        # user can be dict-like or object-like
        user_id = None
        if isinstance(user, dict):
            user_id = user.get("id") or (user.get("user") and user.get("user").get("id"))
        else:
            user_id = getattr(user, "id", None)

        # -----------------------
        # AUTH DEBUG (user info)
        # -----------------------
        logger.warning(f"[AUTH-DEBUG] get_user response shape: type={type(resp).__name__}; user_id_extracted={user_id!r}")
        try:
            sys.stderr.write(f"[AUTH-DEBUG] get_user response shape: type={type(resp).__name__}; user_id_extracted={user_id!r}\n")
            sys.stderr.flush()
        except Exception:
            pass
        # -----------------------

        if not user_id:
            raise Exception("User id not found from token")

        return user_id
    except HTTPException:
        raise
    except Exception as e:
        # attempt to surface more detail to stderr as well
        traceback.print_exc()
        try:
            sys.stderr.write(f"[AUTH-DEBUG] get_user exception: {e}\n")
            sys.stderr.flush()
        except Exception:
            pass
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}")


# Convenience small wrappers
def require_teacher() -> Callable:
    """Dependency: only allow teachers (or admin)."""
    return require_role("teacher")

def require_student() -> Callable:
    """Dependency: only allow students (or admin)."""
    return require_role("student")


# -------------------------------------------------------------------
# Compatibility wrapper for older imports
# -------------------------------------------------------------------
def require_role_from_table(role: str):
    """
    Backwards-compatible wrapper so old routers expecting
    require_role_from_table() continue working.
    Internally this now uses require_role().
    """
    return require_role(role)