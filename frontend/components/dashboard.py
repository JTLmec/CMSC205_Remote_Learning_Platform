# frontend/components/dashboard.py
import os
import streamlit as st
import requests
from typing import List, Dict, Any, Optional
import urllib.parse
import re

# robust import for get_auth_headers
try:
    from frontend.utils.auth import get_auth_headers
except Exception:
    from utils.auth import get_auth_headers


# Toggle this to True temporarily if you want to see raw API responses for debugging.
# Leave False in production / normal use.
SHOW_RAW_DEBUG = False


def _api_base() -> str:
    return st.session_state.get("API_BASE") or os.getenv("API_BASE", "http://127.0.0.1:8000")


def _fetch_json(path: str, headers: Optional[dict] = None, timeout: int = 10):
    API_BASE = _api_base().rstrip("/")
    try:
        r = requests.get(f"{API_BASE}/{path.lstrip('/')}", headers=headers or get_auth_headers(), timeout=timeout)
        if r.status_code == 200:
            try:
                return r.json()
            except Exception:
                return []
        return {"__error__": True, "status": r.status_code, "text": r.text}
    except Exception as e:
        return {"__error__": True, "status": "exception", "text": str(e)}


def _strip_uuid_prefix(filename: str) -> str:
    """
    If filename begins with '<uuid>_' remove that prefix and return rest.
    Otherwise return filename unchanged.
    """
    if not filename:
        return filename or ""
    # try canonical uuid + underscore removal
    m = re.match(
        r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{8}_(.+)$",
        filename,
    )
    if m:
        return m.group(1)
    # fallback: if prefix contains many hex chars (some non-standard UUIDs) remove up to first underscore
    if "_" in filename:
        prefix, rest = filename.split("_", 1)
        hex_count = sum(1 for c in prefix if c in "0123456789abcdefABCDEF")
        if len(prefix) > 8 and hex_count / max(1, len(prefix)) > 0.6:
            return rest
        return rest
    return filename


def _decode_if_encoded(s: str) -> str:
    # try URL-decoding if it looks encoded
    if not s:
        return s
    try:
        if "%" in s or "+" in s:
            return urllib.parse.unquote_plus(s)
    except Exception:
        pass
    return s


def _extract_subject_from_path(path: str) -> str:
    """
    Take path like "Subject/uuid_name.pdf" and extract Subject robustly.
    Accept paths containing backslashes or URL-encoded separators.
    Also if path is just "Subject" (no slash) return it as the subject (folder-only listing).
    """
    if not path:
        return ""
    p = path.replace("\\", "/")
    p = _decode_if_encoded(p).strip().strip("/")
    if not p:
        return ""
    # If path is a single token (no '/'), treat it as subject (folder listing)
    if "/" not in p:
        return p
    # otherwise take the first segment as subject
    candidate = p.split("/", 1)[0].strip()
    return candidate or ""


def _extract_subject_from_display(display: str) -> str:
    """
    Try to find patterns like 'Subject - filename' or 'Subject: filename' in display names.
    This is a fallback when backend doesn't return subject and path doesn't include it.
    """
    if not display:
        return ""
    for sep in [" - ", " — ", ":", "|"]:
        if sep in display:
            left = display.split(sep, 1)[0].strip()
            if left and len(left) <= 80:
                return left
    if "/" in display:
        return display.split("/", 1)[0].strip()
    return ""


def _find_path_candidate(it: dict) -> str:
    """
    Backend may use different keys for the path/name. Check common variants.
    """
    for k in ("path", "name", "Name", "Key", "key", "id"):
        v = it.get(k)
        if v:
            try:
                return str(v)
            except Exception:
                continue
    return ""


def _normalize_list(resp: Any) -> List[Dict[str, Any]]:
    """
    Turn raw response into a list of dicts with keys:
      - display_name (str)
      - subject (str)
      - path (str)
      - url (str)
    Tolerant: prefer explicit subject, else parse the first path segment (folder),
    else fallback to display_name heuristics.
    """
    out: List[Dict[str, Any]] = []
    if SHOW_RAW_DEBUG:
        try:
            st.expander("Raw API response (preview)", expanded=False).write(resp if isinstance(resp, (list, dict)) else str(resp)[:2000])
        except Exception:
            pass

    if not resp or (isinstance(resp, dict) and resp.get("__error__")):
        return out
    if not isinstance(resp, list):
        try:
            resp = list(resp)
        except Exception:
            return out

    for it in resp:
        if not isinstance(it, dict):
            continue

        # Prefer explicit subject key if present
        raw_subject = ""
        try:
            raw_subject = (it.get("subject") or it.get("Subject") or "").strip() if it.get("subject") is not None else ""
        except Exception:
            raw_subject = ""

        raw_display = it.get("display_name") or it.get("filename") or it.get("path") or ""
        raw_path = _find_path_candidate(it) or ""

        raw_path = _decode_if_encoded(raw_path)
        raw_display = _decode_if_encoded(raw_display)

        # Determine subject using prioritized heuristics
        subject = raw_subject or ""
        if not subject and raw_path:
            subject_candidate = _extract_subject_from_path(raw_path)
            if subject_candidate:
                subject = subject_candidate

        if not subject and raw_display:
            subject_candidate = _extract_subject_from_display(raw_display)
            if subject_candidate:
                subject = subject_candidate

        # Final fallback
        if not subject:
            subject = "Uncategorized"

        # Determine display name
        display = raw_display or ""
        if not display and raw_path:
            # If path appears to be folder-only (no file), use the subject as display
            if "/" not in raw_path:
                display = raw_path
            else:
                fname = raw_path.split("/")[-1]
                display = _strip_uuid_prefix(fname)
        else:
            try:
                if "/" in display:
                    display = display.split("/")[-1]
                display = _strip_uuid_prefix(display)
            except Exception:
                pass

        # URL handling (prefer signed url if present)
        url = ""
        for k in ("url", "signedURL", "signed_url", "download_url"):
            if it.get(k):
                url = it.get(k)
                break

        out.append({
            "display_name": display or raw_path or "unknown",
            "subject": subject,
            "path": raw_path,
            "url": url or ""
        })

    return out


def _aggregate_by_subject(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Group items by subject and return list of {subject, count, sample_link}.
    """
    buckets: Dict[str, Dict[str, Any]] = {}
    for it in items:
        subj = (it.get("subject") or "Uncategorized").strip() or "Uncategorized"
        rec = buckets.setdefault(subj, {"subject": subj, "count": 0, "sample_link": ""})
        rec["count"] += 1
        if not rec["sample_link"]:
            candidate = it.get("url") or it.get("path") or ""
            rec["sample_link"] = candidate
    out = list(buckets.values())
    out.sort(key=lambda x: (-x["count"], x["subject"].lower()))
    return out


def _render_subject_table(rows: List[Dict[str, Any]], api_base: str, endpoint: str):
    """
    Render a small markdown table where 'File Download Link' is clickable.
    """
    if not rows:
        st.info("No data.")
        return

    md = ["| Subject | Count | File Download Link |", "|---|---:|---|"]
    for r in rows:
        subj = r.get("subject") or "Uncategorized"
        count = r.get("count") or 0
        link = r.get("sample_link") or ""
        if link and not (link.startswith("http://") or link.startswith("https://")):
            encoded = urllib.parse.quote(link, safe="")
            link = f"{api_base.rstrip('/')}/{endpoint}/download/{encoded}"
        link_md = f"[Download]({link})" if link else ""
        subj = subj.replace("|", "\\|")
        md.append(f"| {subj} | {count} | {link_md} |")

    st.markdown("\n".join(md))


def render_dashboard():
    st.title("📊 Dashboard")

    profile = st.session_state.get("profile") or st.session_state.get("user") or {}
    role = (profile.get("role") or "").lower() if isinstance(profile, dict) else ""

    st.caption(f"Signed in as: {profile.get('email') or 'unknown'} — role: {role or 'unknown'}")

    if "_dashboard_refresh_counter" not in st.session_state:
        st.session_state["_dashboard_refresh_counter"] = 0

    colr1, colr2 = st.columns([1, 5])
    with colr1:
        if st.button("Refresh"):
            st.session_state["_dashboard_refresh_counter"] += 1
            st.experimental_rerun()
    with colr2:
        st.write("")

    headers = get_auth_headers(content_type=None)

    # Materials intentionally omitted per request; fetch assignments and modules
    raw_assignments = _fetch_json("/assignments/list", headers=headers)
    raw_modules = _fetch_json("/modules/list", headers=headers)

    if isinstance(raw_assignments, dict) and raw_assignments.get("__error__"):
        st.error(f"Unable to fetch assignments: {raw_assignments.get('status')} - {raw_assignments.get('text')}")
        assignments_list = []
    else:
        assignments_list = _normalize_list(raw_assignments)

    if isinstance(raw_modules, dict) and raw_modules.get("__error__"):
        st.error(f"Unable to fetch modules: {raw_modules.get('status')} - {raw_modules.get('text')}")
        modules_list = []
    else:
        modules_list = _normalize_list(raw_modules)

    # Aggregate by subject
    assignments_by_subject = _aggregate_by_subject(assignments_list)
    modules_by_subject = _aggregate_by_subject(modules_list)

    # Top metrics (number of distinct subjects)
    col1, col2 = st.columns(2)
    col1.metric("Assignment subjects", value=len(assignments_by_subject))
    col2.metric("Module subjects", value=len(modules_by_subject))

    st.markdown("---")

    # Assignment table
    st.subheader("Assignment counts by subject")
    API_BASE = _api_base().rstrip("/")
    _render_subject_table(assignments_by_subject, API_BASE, "assignments")

    st.markdown("---")

    # Modules table
    st.subheader("Module counts by subject")
    _render_subject_table(modules_by_subject, API_BASE, "modules")

    st.markdown("---")

    if role in ("teacher", "admin"):
        st.success("You have teacher access: you may upload or manage modules from the Modules page.")
    else:
        st.info("Read-only modules view: students can see modules here but cannot upload or manage them.")