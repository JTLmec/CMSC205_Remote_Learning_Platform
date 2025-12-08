# backend/core/auth.py
from fastapi import Header, HTTPException
from typing import Optional, Callable
from supabase import create_client
from core import config

_supabase_admin = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_ROLE)

async def _get_user_id_from_token(authorization: Optional[str]) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split(" ", 1)[1].strip()
    try:
        resp = _supabase_admin.auth.get_user(token)
        user = None
        if isinstance(resp, dict) and "data" in resp:
            user = resp["data"]
        else:
            user = resp
        user_id = None
        if isinstance(user, dict):
            user_id = user.get("id")
        else:
            user_id = getattr(user, "id", None)
        if not user_id:
            raise Exception("User id not found")
        return user_id
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

def require_role_from_table(wanted_role: str) -> Callable:
    """
    Dependency: requires Authorization header Bearer <token>.
    Checks user_roles table using service-role key.
    Returns dict { "user_id": ..., "role": ... } on success.
    """
    async def _require(authorization: Optional[str] = Header(None)):
        user_id = await _get_user_id_from_token(authorization)
        # query user_roles table
        # note: depending on supabase lib version, response shape differs
        res = _supabase_admin.table("user_roles").select("role").eq("user_id", user_id).single().execute()
        # normalize:
        data = None
        if isinstance(res, dict):
            data = res.get("data")
        elif hasattr(res, "data"):
            data = res.data
        if not data:
            raise HTTPException(status_code=403, detail="Role not assigned")
        role = data.get("role") if isinstance(data, dict) else None
        if role != wanted_role:
            raise HTTPException(status_code=403, detail=f"Requires role '{wanted_role}'")
        return {"user_id": user_id, "role": role}
    return _require