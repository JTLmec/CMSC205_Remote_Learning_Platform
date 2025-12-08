# backend/services/supabase_service.py
import logging
from typing import List, Dict, Any, Optional
from supabase import create_client
from backend.core import config

logger = logging.getLogger("supabase_service")

# Prefer service role (backend); fall back to anon for non-privileged ops (dev only)
KEY = config.SUPABASE_SERVICE_ROLE or config.SUPABASE_ANON_KEY
if not KEY:
    raise RuntimeError(
        "Supabase key missing. Set SUPABASE_SERVICE_ROLE (preferred) or SUPABASE_ANON_KEY "
        "in your environment or backend/.env"
    )

_supabase = create_client(config.SUPABASE_URL, KEY)

def upload_file(bucket: str, path: str, file_bytes: bytes, content_type: str) -> Dict[str, Any]:
    """
    Upload file to Supabase storage. Returns whatever the client returns (dict or other).
    Raises Exception on failure.
    """
    try:
        res = _supabase.storage.from_(bucket).upload(
            path=path,
            file=file_bytes,
            file_options={"content-type": content_type}
        )
        return res
    except Exception as e:
        logger.exception("upload_file error")
        raise

def list_files(bucket: str) -> List[Dict[str, Any]]:
    """
    Return a normalized list of objects with at least a 'name' key:
      [ {"name": "<path>"}, ... ]
    This hides differences between storage client versions.
    """
    try:
        raw = _supabase.storage.from_(bucket).list()
        normalized = []

        # raw may sometimes be a dict with "data" or similar depending on SDK; handle common shapes
        if isinstance(raw, dict):
            # e.g. { "data": [...], "error": None } or storage3 returns dict
            if "data" in raw and isinstance(raw["data"], list):
                items = raw["data"]
            elif "message" in raw and isinstance(raw.get("message"), list):
                items = raw["message"]
            else:
                # fallback: try to inspect the dict keys for list-like values
                items = []
                for v in raw.values():
                    if isinstance(v, list):
                        items = v
                        break
        else:
            items = raw

        # items can be list of dicts or list of strings
        for obj in items or []:
            if isinstance(obj, dict):
                # prefer 'name' (common) but accept other common keys
                name = obj.get("name") or obj.get("Key") or obj.get("path") or obj.get("id") or obj.get("key")
                if name:
                    normalized.append({"name": name, **{k: v for k, v in obj.items() if k != "name"}})
                else:
                    # no name found, serialize object
                    normalized.append({"name": str(obj)})
            elif isinstance(obj, str):
                normalized.append({"name": obj})
            else:
                normalized.append({"name": str(obj)})

        return normalized

    except Exception:
        logger.exception("list_files error")
        raise

def create_signed_url(bucket: str, path: str, expires: int = 3600) -> Dict[str, str]:
    """
    Return a dict {'signedURL': '<url>'} consistently.
    """
    try:
        res = _supabase.storage.from_(bucket).create_signed_url(path, expires)
        if isinstance(res, dict):
            # Normalize common keys
            if "signedURL" in res:
                return {"signedURL": res["signedURL"]}
            if "signed_url" in res:
                return {"signedURL": res["signed_url"]}
            if "url" in res:
                return {"signedURL": res["url"]}
            # maybe the SDK returns {"data": {"signedURL": "..."}}
            if "data" in res and isinstance(res["data"], dict) and "signedURL" in res["data"]:
                return {"signedURL": res["data"]["signedURL"]}
            # otherwise stringify fallback
            return {"signedURL": str(res)}
        elif isinstance(res, str):
            return {"signedURL": res}
        else:
            return {"signedURL": str(res)}
    except Exception:
        logger.exception("create_signed_url error")
        raise