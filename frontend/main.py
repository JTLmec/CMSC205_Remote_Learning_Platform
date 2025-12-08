# frontend/main.py
import os
import streamlit as st
from components import auth, dashboard, materials, upload

# configure API base (change to deployed backend when needed)
API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")
st.set_page_config(page_title="Remote Learning Platform", layout="wide")

# make API_BASE available to modules via session_state
st.session_state.setdefault("API_BASE", API_BASE)
st.session_state.setdefault("user", None)   # ensure user key exists

# If not logged in, show auth UI and halt
if not st.session_state.get("user"):
    auth.render_auth()
    st.stop()

# sidebar: show minimal user info & logout + navigation
with st.sidebar:
    user = st.session_state.get("user")
    st.markdown("### 👤 Account")
    if user:
        st.write(f"**Email:** {user.get('email')}")
        if user.get("role"):
            st.write(f"**Role:** {user.get('role')}")
        if user.get("last_sign_in_at"):
            st.write(f"**Last signed in:** {user.get('last_sign_in_at')}")
    else:
        st.info("Not signed in")

    st.write("---")
    page = st.radio("Navigate", ["🏠 Home", "📘 Modules", "📝 Quizzes"], index=0)
    if st.button("Logout"):
        auth.logout()
        st.rerun()

# main content switch
if page == "🏠 Home":
    dashboard.render_dashboard()

elif page == "📘 Modules":
    # old 'materials' → now shown as Modules
    if hasattr(materials, "render_materials"):
        materials.render_materials()
    else:
        materials.render_materials_page()

elif page == "📝 Quizzes":
    # old 'Upload' → now shown as Quizzes
    if hasattr(upload, "render_upload"):
        upload.render_upload()
    else:
        upload.render_upload_page()