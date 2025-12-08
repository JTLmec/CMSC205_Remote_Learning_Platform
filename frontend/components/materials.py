# frontend/components/materials.py
import os
import streamlit as st
import requests
from typing import Dict, List

def _api_base() -> str:
    # prefer session_state (set by main.py) then env fallback
    return st.session_state.get("API_BASE") or os.getenv("API_BASE", "http://127.0.0.1:8000")

def _sanitize_key(s: str) -> str:
    # produce a safe short key for Streamlit widget ids
    if not s:
        return "none"
    k = s.replace("/", "__").replace(" ", "_").replace(".", "_")
    # truncate to avoid extremely long keys
    return k[:200]

def render_materials():
    """
    Main entry used by frontend/main.py -> materials.render_materials()
    Shows materials grouped by subject and provides upload UI with subject form field.
    """
    st.title("📚 Learning Materials")
    API_BASE = _api_base()

    tab_list, tab_upload = st.tabs(["📖 View Materials", "📤 Upload Material"])

    # ---------------------------
    # VIEW MATERIALS
    # ---------------------------
    with tab_list:
        st.subheader("Available Materials")

        try:
            resp = requests.get(f"{API_BASE}/materials/list", timeout=10)
        except Exception as e:
            st.error(f"Server unreachable: {e}")
            return

        if resp.status_code != 200:
            st.error("Failed to load materials.")
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
                        dl = requests.get(f"{API_BASE}/materials/download/{path}", timeout=10)
                        if dl.status_code == 200:
                            body = dl.json()
                            url = body.get("url") if isinstance(body, dict) else None
                            if url:
                                # Show friendly anchor instead of raw JSON
                                st.markdown(f"[⬇️ Download **{display_name}**]({url})")
                            else:
                                st.error("Download URL not returned")
                        else:
                            st.error("Unable to generate download link")
                    except Exception as e:
                        st.error(f"Error fetching download link: {e}")

            st.write("---")

    # ---------------------------
    # UPLOAD MATERIAL
    # ---------------------------
    with tab_upload:
        st.subheader("Upload New Material")

        # Use session-state-aware API_BASE in case it changes (render environment vs local)
        subject = st.text_input("Subject (required)", key="upload_subject")
        file = st.file_uploader("Upload PDF", type=["pdf"], key="upload_file")

        if st.button("Upload", key="upload_btn"):
            if not subject or not subject.strip():
                st.warning("Please enter a subject")
                st.stop()
            if not file:
                st.warning("Please choose a PDF file")
                st.stop()

            # Normal approach: send subject as form-data (data=...) and file as files=...
            files = {"file": (file.name, file.getvalue(), file.type)}
            data = {"subject": subject.strip()}

            try:
                r = requests.post(f"{API_BASE}/materials/upload", files=files, data=data, timeout=60)
                # If your FastAPI still sees a missing 'subject', you can try Option B below:
                # Option B: send subject as part of multipart as (None, value):
                # files = {
                #     "file": (file.name, file.getvalue(), file.type),
                #     "subject": (None, subject.strip())
                # }
                # r = requests.post(f"{API_BASE}/materials/upload", files=files, timeout=60)

                if r.status_code == 200:
                    st.success("Material uploaded!")
                    try:
                        resp_json = r.json()
                        url = resp_json.get("url")
                        if url:
                            st.markdown(f"[🔗 View uploaded file]({url})")
                        st.json(resp_json)
                    except Exception:
                        st.success("Upload reported success but response was not JSON.")
                else:
                    st.error(f"Upload failed: {r.status_code} - {r.text}")
            except Exception as e:
                st.error(f"Upload error: {e}")