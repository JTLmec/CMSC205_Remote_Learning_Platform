# frontend/components/modules.py
import streamlit as st
import requests
from typing import Dict, List

def render_modules():
    """
    Modules UI:
      - View grouped modules (by subject)
      - Upload module (teacher only)
    """
    st.title("Modules")

    # Determine API base from session (allows switching between local/dev/prod)
    API_BASE = st.session_state.get("API_BASE", "http://127.0.0.1:8000").rstrip("/")

    tab_view, tab_upload = st.tabs(["View Modules", "Upload Module"])

    # -------------------------
    # VIEW MODULES
    # -------------------------
    with tab_view:
        try:
            resp = requests.get(f"{API_BASE}/modules/list", timeout=10)
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            st.error(f"Failed to load modules: {e}")
            return

        materials = resp.json()
        if not materials:
            st.info("No modules.")
        else:
            # group by subject
            subjects: Dict[str, List[Dict]] = {}
            for m in materials:
                subj = m.get("subject") or "Uncategorized"
                subjects.setdefault(subj, []).append(m)

            for subj, items in sorted(subjects.items(), key=lambda x: x[0].lower()):
                st.markdown(f"### {subj}")
                for it in items:
                    cols = st.columns([4, 1])
                    cols[0].write(it.get("display_name") or it.get("filename") or it.get("path"))
                    btn_key = f"dl::{it.get('path')}"
                    if cols[1].button("Download", key=btn_key):
                        try:
                            dl = requests.get(f"{API_BASE}/modules/download/{it['path']}", timeout=10)
                            dl.raise_for_status()
                            # show link returned by backend
                            url = dl.json().get("url")
                            if url:
                                st.markdown(f"[Download here]({url})")
                            else:
                                st.error("No download URL received.")
                        except requests.exceptions.RequestException as e:
                            st.error(f"Download failed: {e}")

    # -------------------------
    # UPLOAD MODULE (teachers only)
    # -------------------------
    with tab_upload:
        user = st.session_state.get("user") or {}
        role = (user.get("role") or "").lower() if isinstance(user, dict) else ""

        if role != "teacher":
            st.info("Only teachers may upload modules.")
            return

        subject = st.text_input("Subject (required)")
        file = st.file_uploader("PDF", type=["pdf"])
        if st.button("Upload Module"):
            if not subject or not subject.strip():
                st.warning("Subject is required.")
                return
            if not file:
                st.warning("Please choose a PDF file")
                return

            files = {"file": (file.name, file.getvalue(), file.type)}
            data = {"subject": subject.strip()}

            headers = {}
            token = st.session_state.get("access_token")
            if token:
                headers["Authorization"] = f"Bearer {token}"

            try:
                r = requests.post(f"{API_BASE}/modules/upload", files=files, data=data, headers=headers, timeout=60)
                if r.status_code in (200, 201):
                    st.success("Uploaded")
                    # show backend response (path/url)
                    try:
                        st.json(r.json())
                    except Exception:
                        st.write("Upload succeeded (no JSON returned).")
                else:
                    st.error(f"Upload failed: {r.status_code}")
                    st.text(r.text)
            except requests.exceptions.RequestException as e:
                st.error(f"Upload request failed: {e}")