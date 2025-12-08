# backend/backend/routers/materials.py
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
import uuid
import os
import traceback
from typing import List, Dict, Any
from services.supabase_service import upload_file, list_files, create_signed_url

# storage3-specific exception class
from storage3.utils import StorageException

router = APIRouter(prefix="/materials", tags=["Materials"])
BUCKET_NAME = "materials"  # ensure this bucket exists in Supabase

def _sanitize_subject(subject: str) -> str:
    """
    Very small sanitizer: keep alnum, spaces, dash, underscore.
    Trim and replace multiple spaces with single space.
    """
    if not subject:
        return ""
    clean = "".join(c for c in subject if c.isalnum() or c in (" ", "-", "_"))
    clean = " ".join(clean.split())  # collapse whitespace
    return clean.strip()

def pretty_name_from_path(path: str) -> str:
    """Return a human-friendly filename: drop any leading folder and the uuid_ prefix."""
    if not path:
        return ""
    # path may be "<subject>/uuid_filename.ext" or "uuid_filename.ext"
    basename = os.path.basename(path)
    # strip uuid_ if present
    if "_" in basename:
        return basename.split("_", 1)[1]
    return basename

def split_subject_and_filename(path: str):
    """
    Return (subject, filename) where subject is the folder prefix if present.
    If no folder, subject == 'Uncategorized'.
    """
    if not path:
        return ("Uncategorized", "")
    if "/" in path:
        subject, rest = path.split("/", 1)
        return (subject, pretty_name_from_path(rest))
    return ("Uncategorized", pretty_name_from_path(path))

@router.post("/upload")
async def upload_material(
    file: UploadFile = File(...),
    subject: str = Form(...),   # required form field
):
    """
    Upload a material. 'subject' is required and used to group files in storage.
    Stored path = "<subject_safe>/<uuid>_<original_filename>"
    """
    try:
        if not subject or not subject.strip():
            raise ValueError("Subject is required")

        subject_safe = _sanitize_subject(subject)
        if not subject_safe:
            raise ValueError("Invalid subject value")

        data = await file.read()
        filename = f"{uuid.uuid4()}_{file.filename}"
        storage_path = f"{subject_safe}/{filename}"

        # upload_file should raise on error; return value ignored here
        upload_file(BUCKET_NAME, storage_path, data, file.content_type)

        # Try to create signed url; if it fails return url=None (do not crash)
        url = None
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
            "filename": pretty_name_from_path(filename)
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list")
def materials_list() -> List[Dict[str, Any]]:
    """
    Return normalized list:
      [{ "path": "...", "url": "...", "display_name": "...", "subject": "...", "filename": "..." }, ...]
    Only include real files (i.e. ones we can create a signed URL for). Skip folder placeholders.
    """
    try:
        raw = list_files(BUCKET_NAME)  # library returns list of dicts (or strings)
        normalized: List[Dict[str, Any]] = []

        for obj in raw:
            # resolve candidate path
            path = None
            if isinstance(obj, dict):
                path = obj.get("name") or obj.get("Key") or obj.get("path") or obj.get("id") or obj.get("key")
            elif isinstance(obj, str):
                path = obj

            if not path:
                continue

            # skip known placeholder names or empty folder markers
            if path.strip() in (".emptyFolderPlaceholder", "", None):
                # this is not a real file
                continue

            # If the object looks like a folder name (no slash and no dot extension),
            # try to create a signed URL — if it fails, treat as folder and skip.
            try:
                signed = create_signed_url(BUCKET_NAME, path, expires=3600)
            except Exception:
                # Could be a folder entry rather than a file — skip it.
                continue

            # normalize the signed URL (storage library sometimes returns dict or str)
            url = None
            if isinstance(signed, dict):
                url = signed.get("signedURL") or signed.get("signed_url") or signed.get("url")
            elif isinstance(signed, str):
                url = signed

            # If url is None/invalid, skip
            if not url:
                continue

            subject, filename = split_subject_and_filename(path)
            normalized.append({
                "path": path,
                "url": url,
                "display_name": filename,
                "subject": subject,
                "filename": filename
            })

        # Optionally sort by subject then filename
        normalized.sort(key=lambda x: (x.get("subject", ""), x.get("filename", "")))
        return normalized

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/download/{path:path}")
def download(path: str):
    """
    Return signed URL for a given storage path. 'path' may include slashes (subject/...).
    """
    try:
        if not path:
            raise ValueError("Path is required")
        signed = create_signed_url(BUCKET_NAME, path)
        url = signed.get("signedURL") if isinstance(signed, dict) else signed
        return {"url": url}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))