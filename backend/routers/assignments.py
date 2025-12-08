# backend/routers/assignments.py
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
import uuid, os, traceback
from typing import List, Dict, Any
from services.supabase_service import upload_file, list_files, create_signed_url

router = APIRouter(prefix="/assignments", tags=["Assignments"])
BUCKET_NAME = "assignments"  # ← create this bucket in Supabase

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

@router.post("/upload")
async def upload_assignment(
    file: UploadFile = File(...),
    subject: str = Form(...)
):
    try:
        if not subject or not subject.strip():
            raise ValueError("Subject is required")
        subject_safe = _sanitize_subject(subject)
        if not subject_safe:
            raise ValueError("Invalid subject")

        data = await file.read()
        filename = f"{uuid.uuid4()}_{file.filename}"
        storage_path = f"{subject_safe}/{filename}"

        upload_file(BUCKET_NAME, storage_path, data, file.content_type)

        try:
            signed = create_signed_url(BUCKET_NAME, storage_path)
            url = signed.get("signedURL") if isinstance(signed, dict) else signed
        except Exception:
            traceback.print_exc()
            url = None

        return {"path": storage_path, "url": url, "subject": subject_safe, "filename": pretty_name_from_path(filename)}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list")
def assignments_list() -> List[Dict[str, Any]]:
    try:
        raw = list_files(BUCKET_NAME)
        normalized = []
        for obj in raw:
            path = None
            if isinstance(obj, dict):
                path = obj.get("name") or obj.get("Key") or obj.get("path") or obj.get("id") or obj.get("key")
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
            normalized.append({
                "path": path,
                "url": url,
                "display_name": filename,
                "subject": subject,
                "filename": filename
            })
        normalized.sort(key=lambda x: (x.get("subject",""), x.get("filename","")))
        return normalized
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/download/{path:path}")
def download(path: str):
    try:
        if not path:
            raise ValueError("Path required")
        signed = create_signed_url(BUCKET_NAME, path)
        url = signed.get("signedURL") if isinstance(signed, dict) else signed
        return {"url": url}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))