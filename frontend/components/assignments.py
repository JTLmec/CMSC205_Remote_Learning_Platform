# frontend/components/assignments.py
import streamlit as st
import requests

def render_assignments():
    API_BASE = st.session_state.get("API_BASE")

    st.title("📝 Assignments")

    # Check user & role
    user = st.session_state.get("user") or {}
    role = user.get("role")

    tab_view, tab_upload = st.tabs(["📘 View Assignments", "📤 Submit Assignment"])

    # ------------------------
    # STUDENTS & TEACHERS: VIEW ASSIGNMENTS AVAILABLE
    # ------------------------
    with tab_view:
        st.subheader("Available Assignments")

        try:
            resp = requests.get(f"{API_BASE}/assignments/list", timeout=10)
        except Exception as e:
            st.error(f"Server unreachable: {e}")
            return

        if resp.status_code != 200:
            st.error("Unable to load assignments.")
            return

        assignments = resp.json()
        if not assignments:
            st.info("No assignments available.")
            return

        # Group by subject
        grouped = {}
        for a in assignments:
            grouped.setdefault(a["subject"], []).append(a)

        for subject, items in grouped.items():
            st.markdown(f"### 📘 {subject}")

            for item in items:
                c1, c2 = st.columns([3, 1])
                c1.write(item["display_name"])

                if c2.button("Download", key=item["path"]):
                    dl = requests.get(f"{API_BASE}/assignments/download/{item['path']}")
                    if dl.status_code == 200:
                        st.markdown(f"[Click to download]({dl.json()['url']})")
                    else:
                        st.error("Failed to generate download link")

            st.write("---")

    # ------------------------
    # STUDENT ONLY: SUBMIT ASSIGNMENTS
    # ------------------------
    with tab_upload:
        if role != "student":
            st.info("Only students may submit assignments.")
            return

        st.subheader("Submit Your Assignment")

        subject = st.text_input("Subject (required)")
        file = st.file_uploader("Upload PDF", type=["pdf"])

        if st.button("Submit"):
            if not subject:
                st.warning("Subject is required.")
                return
            if not file:
                st.warning("Please upload a file.")
                return

            files = {"file": (file.name, file.getvalue(), file.type)}
            data = {"subject": subject}

            # Auth header
            token = st.session_state.get("access_token")
            headers = {"Authorization": f"Bearer {token}"} if token else {}

            try:
                r = requests.post(
                    f"{API_BASE}/assignments/upload",
                    files=files,
                    data=data,
                    headers=headers,
                    timeout=20,
                )
                if r.status_code == 200:
                    st.success("Assignment submitted!")
                    st.json(r.json())
                else:
                    st.error(f"Upload failed: {r.status_code} {r.text}")

            except Exception as e:
                st.error(str(e))