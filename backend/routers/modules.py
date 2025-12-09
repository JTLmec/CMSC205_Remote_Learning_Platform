# backend/routers/modules.py
import os
import uuid
import re
import traceback
from typing import List, Dict, Any, Optional

import requests
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Header

from services.supabase_service import upload_file, list_files, create_signed_url

router = APIRouter(prefix="/modules", tags=["Modules"])
BUCKET_NAME = "modules"  # ensure this bucket exists in Supabase


def _sanitize_subject(subject: str) -> str:
    if not subject:
        return ""
    clean = "".join(c for c in subject if c.isalnum() or c in (" ", "-", "_"))
    clean = " ".join(clean.split())
    return clean.strip()


def pretty_name_from_path(path: str) -> str:
    if not path:
        return ""
    basename = os.path.basename(path)
    if "_" in basename:
        return basename.split("_", 1)[1]
    return basename


def split_subject_and_filename(path: str):
    if not path:
        return ("Uncategorized", "")
    if "/" in path:
        subject, rest = path.split("/", 1)
        return (subject, pretty_name_from_path(rest))
    return ("Uncategorized", pretty_name_from_path(path))


# -------------------------
# Helper: validate token via Supabase /auth/v1/user
# -------------------------
def _get_user_from_token(authorization: Optional[str]):
    """
    Validates the incoming Bearer token by calling Supabase /auth/v1/user
    using the server-side SUPABASE_SERVICE_ROLE as 'apikey'. Returns the user dict.
    Raises HTTPException(401) on failure.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = authorization.split(" ", 1)[1].strip()

    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE = os.environ.get("SUPABASE_SERVICE_ROLE")
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE:
        raise HTTPException(status_code=500, detail="Server misconfiguration: missing Supabase keys")

    url = f"{SUPABASE_URL.rstrip('/')}/auth/v1/user"
    headers = {
        "Authorization": f"Bearer {token}",
        "apikey": SUPABASE_SERVICE_ROLE,
    }

    try:
        r = requests.get(url, headers=headers, timeout=8)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Auth verification failed: {e}")

    if r.status_code != 200:
        try:
            body = r.json()
            msg = body.get("message") or body.get("detail") or r.text
        except Exception:
            msg = r.text
        raise HTTPException(status_code=401, detail=f"Invalid token: {msg}")

    try:
        user = r.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Invalid auth response: {e}")

    if not user.get("id"):
        raise HTTPException(status_code=401, detail="Invalid token: User id not found")

    return user


# -------------------------
# Upload endpoint (server-side token verification + storage upload)
# -------------------------
@router.post("/upload")
async def upload_module(
    file: UploadFile = File(...),
    subject: str = Form(...),
    authorization: str = Header(None),
):
    """
    Upload a module (teacher-only).
    - Validates Bearer token via Supabase (server-side)
    - Enforces teacher role (or admin)
    - Uploads file bytes to storage via upload_file helper
    """
    try:
        # Validate subject
        if not subject or not subject.strip():
            raise HTTPException(status_code=400, detail="Subject is required")
        subject_safe = _sanitize_subject(subject)
        if not subject_safe:
            raise HTTPException(status_code=400, detail="Invalid subject")

        # Verify token and fetch user via Supabase (server-side)
        user = _get_user_from_token(authorization)

        # Extract role information (tolerant to various shapes)
        user_role = ""
        # supabase /auth/v1/user returns a top-level 'role' in some shapes
        if isinstance(user.get("role"), str):
            user_role = user.get("role").lower()
        else:
            # fallback to app_metadata.role or user_metadata or other common places
            app_meta = user.get("app_metadata") or {}
            user_role = (app_meta.get("role") or "").lower() if isinstance(app_meta.get("role"), str) else user_role
            if not user_role:
                # sometimes role may be in 'user_metadata' or other fields
                user_meta = user.get("user_metadata") or {}
                user_role = (user_meta.get("role") or "").lower() if isinstance(user_meta.get("role"), str) else user_role

        # Accept if teacher OR admin
        if user_role not in ("teacher", "admin", "authenticated"):
            # If your "authenticated" means a student, adjust as needed.
            # Here we require explicitly 'teacher' (admin allowed too).
            raise HTTPException(status_code=403, detail="Only teachers may upload modules")

        # read file contents
        data = await file.read()
        # create a safe filename and storage path
        safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", file.filename)
        filename = f"{uuid.uuid4()}_{safe_name}"
        storage_path = f"{subject_safe}/{filename}"

        # Upload using your existing helper
        upload_file(BUCKET_NAME, storage_path, data, file.content_type)

        # create signed url if available (your existing helper)
        try:
            signed = create_signed_url(BUCKET_NAME, storage_path)
            url = signed.get("signedURL") if isinstance(signed, dict) else signed
        except Exception:
            traceback.print_exc()
            url = None

        return {
            "path": storage_path,
            "url": url,
            "subject": subject_safe,
            "filename": pretty_name_from_path(filename),
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------
# Listing & download endpoints
# -------------------------
@router.get("/list")
def modules_list() -> List[Dict[str, Any]]:
    try:
        raw = list_files(BUCKET_NAME)
        normalized = []
        for obj in raw:
            path = None
            if isinstance(obj, dict):
                path = obj.get("name") or obj.get("Key") or obj.get("path") or obj.get("id")
            elif isinstance(obj, str):
                path = obj
            if not path:
                continue
            signed = None
            try:
                signed = create_signed_url(BUCKET_NAME, path, expires=3600)
            except Exception:
                signed = None
            url = None
            if isinstance(signed, dict):
                url = signed.get("signedURL") or signed.get("signed_url") or signed.get("url")
            elif isinstance(signed, str):
                url = signed
            subject, filename = split_subject_and_filename(path)
            normalized.append({"path": path, "url": url, "display_name": filename, "subject": subject, "filename": filename})
        normalized.sort(key=lambda x: (x.get("subject",""), x.get("filename","")))
        return normalized
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{path:path}")
def download(path: str):
    try:
        if not path:
            raise HTTPException(status_code=400, detail="Path required")
        signed = create_signed_url(BUCKET_NAME, path)
        url = signed.get("signedURL") if isinstance(signed, dict) else signed
        return {"url": url}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))