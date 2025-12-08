# frontend/components/upload.py
import streamlit as st
import requests
import os

def render_upload():
    """
    Upload UI for Modules (teachers) or Assignments (students).
    - Sends Authorization: Bearer <token> header if an access_token exists in session_state.
    - For Modules we require a subject field.
    - For Assignments we require an optional assignment_id.
    """
    st.header("📤 Upload")

    API_BASE = st.session_state.get("API_BASE", "http://127.0.0.1:8000")
    user = st.session_state.get("user", {}) or {}
    role = user.get("role", "").lower() if isinstance(user, dict) else ""

    # Choose what kind of upload user is allowed to do
    if role == "teacher":
        upload_target = "Modules (teacher)"
        endpoint = "modules/upload"
    elif role == "student":
        upload_target = "Assignments (student)"
        endpoint = "assignments/upload"
    else:
        # if role unknown, allow user to pick but warn
        upload_target = st.selectbox("Upload type", ["Modules (teacher)", "Assignments (student)"])
        endpoint = "modules/upload" if upload_target.startswith("Modules") else "assignments/upload"
        st.warning("No role detected — backend authorization will still enforce permissions.")

    st.write(f"**Upload target:** {upload_target}")

    # Common inputs
    uploaded = st.file_uploader("Choose a file", type=["pdf", "png", "jpg", "jpeg", "docx"])
    # Modules need subject
    subject = None
    assignment_id = None
    if upload_target.startswith("Modules"):
        subject = st.text_input("Subject (required for Modules)")
    else:
        assignment_id = st.text_input("Assignment ID (optional)")

    if st.button("Upload"):
        if not uploaded:
            st.warning("Please choose a file first")
            return

        # Validate required fields
        if upload_target.startswith("Modules") and (not subject or not subject.strip()):
            st.warning("Please enter a subject for the module.")
            return

        # Prepare multipart payload
        files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type)}
        data = {}
        if subject:
            data["subject"] = subject.strip()
        if assignment_id:
            data["assignment_id"] = assignment_id.strip()

        # Prepare headers with token if available
        token = st.session_state.get("access_token")
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        url = f"{API_BASE.rstrip('/')}/{endpoint.lstrip('/')}"

        try:
            # increase timeout for uploads; set a reasonable limit
            r = requests.post(url, files=files, data=data, headers=headers, timeout=60)

            if r.status_code in (200, 201):
                st.success("Upload successful")
                # show minimal info only (avoid leaking signed token urls if you don't want them visible)
                try:
                    j = r.json()
                    st.json(j)
                except Exception:
                    st.write("Upload response received.")
            else:
                # show backend error for debugging
                st.error(f"Upload failed ({r.status_code})")
                st.text(r.text)
        except requests.exceptions.RequestException as e:
            st.error(f"Request error: {e}")