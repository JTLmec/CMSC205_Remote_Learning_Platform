# frontend/components/materials.py
import os
import urllib.parse
import streamlit as st
import requests
import io
from typing import Dict, List

# robust import for get_auth_headers (works whether you run from frontend/ or repo root)
try:
    from frontend.utils.auth import get_auth_headers
except Exception:
    from utils.auth import get_auth_headers


def _api_base() -> str:
    # prefer session_state (set by main.py) then env fallback
    return st.session_state.get("API_BASE") or os.getenv("API_BASE", "http://127.0.0.1:8000")


def _sanitize_key(s: str) -> str:
    # produce a safe short key for Streamlit widget ids
    if not s:
        return "none"
    k = s.replace("/", "__").replace(" ", "_").replace(".", "_")
    return k[:200]


def render_materials():
    """
    Materials UI: grouped view + upload (teachers only)
    """
    st.title("📚 Learning Materials")
    API_BASE = _api_base().rstrip("/")

    tab_list, tab_upload = st.tabs(["📖 View Materials", "📤 Upload Material"])

    # ---------------------------
    # VIEW MATERIALS
    # ---------------------------
    with tab_list:
        st.subheader("Available Materials")
        try:
            resp = requests.get(f"{API_BASE}/materials/list", headers=get_auth_headers(), timeout=10)
        except Exception as e:
            st.error(f"Server unreachable: {e}")
            return

        if resp.status_code != 200:
            st.error(f"Failed to load materials (status {resp.status_code}).")
            return

        try:
            materials = resp.json() or []
        except Exception:
            st.error("Malformed response from server.")
            return

        if not materials:
            st.info("No materials found.")
            return

        # Group by subject
        subjects: Dict[str, List[Dict]] = {}
        for m in materials:
            subject = m.get("subject") or "Uncategorized"
            subjects.setdefault(subject, []).append(m)

        for subject, items in subjects.items():
            st.markdown(f"### 📘 {subject}")
            for item in items:
                display_name = item.get("display_name") or item.get("filename") or item.get("path")
                path = item.get("path") or display_name or ""

                col1, col2 = st.columns([3, 1])
                col1.write(display_name)

                key = "dl_" + _sanitize_key(path)
                if col2.button("Download", key=key):
                    try:
                        encoded_path = urllib.parse.quote(path, safe="")
                        dl = requests.get(f"{API_BASE}/materials/download/{encoded_path}", headers=get_auth_headers(), timeout=10)
                        if dl.status_code == 200:
                            body = dl.json()
                            url = body.get("url") if isinstance(body, dict) else None
                            if url:
                                st.markdown(f"[⬇️ Download **{display_name}**]({url})")
                            else:
                                st.error("Download URL missing from response.")
                        else:
                            st.error(f"Unable to generate download link (status {dl.status_code})")
                    except Exception as e:
                        st.error(f"Error fetching download link: {e}")

            st.write("---")

    # ---------------------------
    # UPLOAD MATERIAL
    # ---------------------------
    with tab_upload:
        st.subheader("Upload New Material")

        profile = st.session_state.get("profile") or st.session_state.get("user") or {}
        role = (profile.get("role") or "").lower() if isinstance(profile, dict) else ""
        if role != "teacher":
            st.info("Only teachers can upload materials. If you are a teacher, make sure you are logged in with a teacher account.")
            return

        subject = st.text_input("Subject (required)", key="upload_subject")
        file = st.file_uploader("Upload PDF", type=["pdf"], key="upload_file")

        if st.button("Upload", key="upload_btn"):
            if not subject or not subject.strip():
                st.warning("Please enter a subject")
                return
            if not file:
                st.warning("Please choose a PDF file")
                return

            # Use a file-like object to ensure proper multipart behavior
            file_bytes = file.getvalue()
            file_obj = io.BytesIO(file_bytes)
            try:
                file_obj.name = file.name
            except Exception:
                pass

            files = {"file": (file.name, file_obj, file.type)}
            data = {"subject": subject.strip()}

            # IMPORTANT: do not let get_auth_headers set Content-Type for multipart; pass content_type=None
            try:
                headers = get_auth_headers(content_type=None)
            except TypeError:
                headers = get_auth_headers()

            # remove any explicit content-type so requests sets boundary
            headers.pop("Content-Type", None)

            if not (headers.get("Authorization") or headers.get("authorization")):
                st.error("No access token found. Please log in.")
                return

            try:
                r = requests.post(f"{API_BASE}/materials/upload", files=files, data=data, headers=headers, timeout=60)
            except Exception as e:
                st.error(f"Upload error: {e}")
                return

            if r.status_code in (200, 201):
                try:
                    resp_json = r.json()
                except Exception:
                    resp_json = {}

                uploaded_name = resp_json.get("filename") or file.name
                uploaded_subject = resp_json.get("subject") or subject.strip()
                uploaded_url = resp_json.get("url")

                st.success(f"Material uploaded: **{uploaded_name}** (subject: {uploaded_subject})")
                if uploaded_url:
                    st.markdown(f"[🔗 View uploaded file]({uploaded_url})")
            elif r.status_code == 401:
                st.error("Upload failed: Unauthorized. Please sign in again.")
            elif r.status_code == 403:
                # Surface server role message (clean)
                try:
                    body = r.json()
                    detail = body.get("detail") or body.get("message") or r.text
                except Exception:
                    detail = r.text
                st.error(f"Upload failed: Forbidden. {detail}")
            else:
                st.error(f"Upload failed: {r.status_code} - {r.text}")