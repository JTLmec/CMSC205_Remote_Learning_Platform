# frontend/components/modules.py
import os
import urllib.parse
import streamlit as st
import requests
import io
from typing import List, Dict

# robust import for get_auth_headers
try:
    from frontend.utils.auth import get_auth_headers
except Exception:
    from utils.auth import get_auth_headers


def _api_base() -> str:
    return st.session_state.get("API_BASE") or os.getenv(
        "API_BASE", "http://127.0.0.1:8000"
    )


def render_modules():
    API_BASE = _api_base().rstrip("/")
    st.title("📘 Modules")

    # authoritative profile (prefer 'profile' then 'user')
    profile = st.session_state.get("profile") or st.session_state.get("user") or {}
    role = (profile.get("role") or "").lower() if isinstance(profile, dict) else ""

    tab_view, tab_upload = st.tabs(["📖 View Modules", "📤 Upload Module"])

    # ------------------------
    # VIEW: everyone
    # ------------------------
    with tab_view:
        st.subheader("Available Modules")
        try:
            resp = requests.get(
                f"{API_BASE}/modules/list",
                headers=get_auth_headers(),
                timeout=10,
            )
            if resp.status_code != 200:
                st.error(f"Unable to load modules (status={resp.status_code}).")
                return
            modules = resp.json() or []
        except Exception as e:
            st.error(f"Server unreachable: {e}")
            return

        if not modules:
            st.info("No modules available.")
        else:
            grouped: Dict[str, List[Dict]] = {}
            for m in modules:
                subj = m.get("subject", "Uncategorized")
                grouped.setdefault(subj, []).append(m)

            for subject, items in grouped.items():
                st.markdown(f"### 📘 {subject}")

                for item in items:
                    display = item.get("display_name") or item.get("filename") or item.get("path")
                    path = item.get("path") or ""

                    c1, c2 = st.columns([3, 1])
                    c1.write(display)
                    key = "dl_mod_" + (path or display)

                    if c2.button("Download", key=key):
                        try:
                            encoded = urllib.parse.quote(path, safe="")
                            dl = requests.get(
                                f"{API_BASE}/modules/download/{encoded}",
                                headers=get_auth_headers(),
                                timeout=10,
                            )
                            if dl.status_code == 200:
                                url = dl.json().get("url")
                                if url:
                                    st.markdown(f"[Click to download]({url})")
                                else:
                                    st.error("Download URL missing from response.")
                            else:
                                st.error("Failed to generate download link.")
                        except Exception as e:
                            st.error(f"Download error: {e}")

                st.write("---")

    # ------------------------
    # UPLOAD: teachers only
    # ------------------------
    with tab_upload:
        st.subheader("Upload Module")

        if role != "teacher":
            st.info("Only teachers may upload modules.")
            return

        subject = st.text_input("Subject (required)", key="module_subject")
        file = st.file_uploader("Upload PDF", type=["pdf"], key="module_file")

        submitted = st.button("Upload Module", key="submit_module_btn")

        if submitted:
            if not subject:
                st.warning("Subject is required.")
                return
            if not file:
                st.warning("Please upload a file.")
                return

            # Build Authorization header safely (do not override multipart Content-Type)
            try:
                headers = get_auth_headers(content_type=None)
            except Exception:
                headers = {}

            headers.pop("Content-Type", None)

            # If no auth → user logged out
            if not (headers.get("Authorization") or headers.get("authorization")):
                st.error("You are not logged in. Please sign in again.")
                return

            # Prepare file
            file_bytes = file.getvalue()
            file_obj = io.BytesIO(file_bytes)
            try:
                file_obj.name = file.name
            except Exception:
                pass

            files = {"file": (file.name, file_obj, file.type)}
            data = {"subject": subject.strip()}

            # Send upload
            try:
                r = requests.post(
                    f"{API_BASE}/modules/upload",
                    files=files,
                    data=data,
                    headers=headers,
                    timeout=60,
                )
            except Exception as e:
                st.error(f"Upload request failed: {e}")
                return

            # Response handling (clean)
            if r.status_code in (200, 201):
                try:
                    j = r.json()
                except Exception:
                    j = {}

                uploaded_name = j.get("filename") or file.name
                uploaded_subject = j.get("subject") or subject.strip()
                uploaded_path = j.get("path")
                uploaded_url = j.get("url")

                st.success(f"Module uploaded: **{uploaded_name}** (subject: {uploaded_subject})")
                if uploaded_url:
                    st.markdown(f"[Open uploaded file]({uploaded_url})")
            elif r.status_code == 401:
                st.error("Upload failed: Unauthorized. Please sign in again.")
            elif r.status_code == 403:
                st.error("Upload failed: Forbidden. Your account is not allowed to upload modules.")
            else:
                st.error(f"Upload failed: {r.status_code} - {r.text}")