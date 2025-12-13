# frontend/components/assignments.py
import os
import urllib.parse
import io
import requests
import streamlit as st
from typing import List, Dict, Any, Optional

# Import auth utilities with fallback
try:
    from frontend.utils.auth import get_auth_headers
    from frontend.utils.helpers import _api_base, _sanitize_key
except ImportError:
    try:
        from utils.auth import get_auth_headers
        from utils.helpers import _api_base, _sanitize_key
    except ImportError:
        # Fallback implementations if utils module is not available
        def _api_base() -> str:
            return st.session_state.get("API_BASE") or os.getenv("API_BASE", "http://127.0.0.1:8000")
            
        def _sanitize_key(key: str) -> str:
            """Create a safe key for Streamlit components."""
            import re
            return re.sub(r'[^a-zA-Z0-9]', '_', str(key))
            
        # Fallback for get_auth_headers if not available
        def get_auth_headers(content_type: str = "application/json") -> Dict[str, str]:
         """Get authentication headers with optional content type."""
         headers = {}
         # Changed from: token = st.session_state.get("auth_token")
         token = st.session_state.get("access_token") or st.session_state.get("auth_token")
         if token:
            headers["Authorization"] = f"Bearer {token}"
         if content_type:
            headers["Content-Type"] = content_type
         return headers

def render_assignments():
    st.title("📝 Assignments")
    API_BASE = _api_base().rstrip("/")

    # Get user profile and role
    profile = st.session_state.get("profile") or st.session_state.get("user") or {}
    role = (profile.get("role") or "").lower() if isinstance(profile, dict) else ""

    # Create tabs for viewing and submitting assignments
    tab_view, tab_upload = st.tabs(["📘 View Assignments", "📤 Submit Assignment"])

    # ------------------------
    # VIEW: everyone
    # ------------------------
    with tab_view:
        st.subheader("Available Assignments")
        try:
            resp = requests.get(
                f"{API_BASE}/assignments/list",
                headers=get_auth_headers(),
                timeout=10,
            )
            if resp.status_code != 200:
                st.error(f"Unable to load assignments (status={resp.status_code}).")
                return
            assignments = resp.json() or []
        except Exception as e:
            st.error(f"Server unreachable: {e}")
            return

        if not assignments:
            st.info("No assignments available.")
        else:
            # Group assignments by subject
            grouped: Dict[str, List[Dict]] = {}
            for a in assignments:
                subj = a.get("subject", "Uncategorized")
                grouped.setdefault(subj, []).append(a)

            # Display assignments by subject
            for subject, items in grouped.items():
                st.markdown(f"### 📘 {subject}")

                for item in items:
                    display = (
                        item.get("display_name")
                        or item.get("filename")
                        or item.get("path")
                    )
                    path = item.get("path") or ""

                    # Create columns for display and download button
                    col1, col2 = st.columns([3, 1])
                    col1.write(display)
                    
                    # Create a unique key for each download button
                    download_key = f"dl_{_sanitize_key(display)}_{_sanitize_key(path)}"
                    
                    if col2.button("Download", key=download_key):
                        handle_download(API_BASE, path, display)

                st.write("---")

    # ------------------------
    # UPLOAD: students only
    # ------------------------
    with tab_upload:
        st.subheader("Submit Your Assignment")

        if role != "student":
            st.info("Only students may submit assignments.")
            return

        # Create unique keys for the upload form
        subject_key = "assignment_subject_upload"
        file_key = "assignment_file_upload"
        submit_key = "submit_assignment_btn_upload"
        
        subject = st.text_input("Subject (required)", key=subject_key)
        file = st.file_uploader("Upload PDF", type=["pdf"], key=file_key)

        if st.button("Submit", key=submit_key):
            handle_upload(API_BASE, subject, file)

def handle_download(api_base: str, path: str, display_name: str):
    """Handle file download process."""
    try:
        encoded = urllib.parse.quote(path, safe="")
        dl = requests.get(
            f"{api_base}/assignments/download/{encoded}",
            headers=get_auth_headers(),
            timeout=10,
        )
    except Exception as e:
        st.error(f"Download error: {e}")
        return

    if dl.status_code != 200:
        try:
            body = dl.json()
        except Exception:
            body = dl.text
        st.error(f"Failed to generate download link (status {dl.status_code}): {body}")
        return

    try:
        body = dl.json() or {}
    except Exception:
        body = {}
    
    signed_url = body.get("url")
    if not signed_url:
        st.error("Download URL missing from response.")
        return

    # Auto-trigger download using JavaScript
    safe_name = urllib.parse.quote(display_name or "assignment")
    js = f"""
    var a = document.createElement('a');
    a.href = "{signed_url}";
    a.download = "{safe_name}";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    """
    st.components.v1.html(f"<script>{js}</script>", height=0)

def handle_upload(api_base: str, subject: str, file):
    """Handle file upload process."""
    if not subject:
        st.warning("Subject is required.")
        return
    if not file:
        st.warning("Please upload a file.")
        return

    try:
        headers = get_auth_headers(content_type=None)
    except Exception:
        headers = {}

    headers.pop("Content-Type", None)

    if not (headers.get("Authorization") or headers.get("authorization")):
        st.error("You are not logged in. Please sign in again.")
        return

    # Prepare file for upload
    file_bytes = file.getvalue()
    file_obj = io.BytesIO(file_bytes)
    try:
        file_obj.name = file.name
    except Exception:
        pass

    files = {"file": (file.name, file_obj, file.type)}
    data = {"subject": subject.strip()}

    try:
        response = requests.post(
            f"{api_base}/assignments/upload",
            files=files,
            data=data,
            headers=headers,
            timeout=60,
        )

        if response.status_code in (200, 201):
            try:
                result = response.json()
            except Exception:
                result = {}

            uploaded_name = result.get("filename") or file.name
            uploaded_subject = result.get("subject") or subject.strip()
            uploaded_url = result.get("url")

            st.success(f"Assignment submitted: **{uploaded_name}** (subject: {uploaded_subject})")
            if uploaded_url:
                st.markdown(f"[View uploaded file]({uploaded_url})")
        elif response.status_code == 401:
            st.error("Upload failed: Unauthorized. Please sign in again.")
        else:
            st.error(f"Upload failed: {response.status_code} - {response.text}")

    except Exception as e:
        st.error(f"Upload request failed: {e}")