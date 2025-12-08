# frontend/main.py
import os
import streamlit as st

# configure API base (change to deployed backend when needed)
API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")
st.set_page_config(page_title="Remote Learning Platform", layout="wide")

# make API_BASE available to modules via session_state
st.session_state.setdefault("API_BASE", API_BASE)
st.session_state.setdefault("user", None)   # ensure user key exists

# import auth + UI modules (we import other modules lazily below to avoid import-time errors)
from components import auth, dashboard, materials, upload  # leave upload if you still use it

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
    # <-- Changed label here: Quizzes -> Assignments
    page = st.radio("Navigate", ["🏠 Home", "📘 Modules", "📝 Assignments"], index=0)
    if st.button("Logout"):
        auth.logout()
        st.rerun()

# main content switch
if page == "🏠 Home":
    dashboard.render_dashboard()

elif page == "📘 Modules":
    # old 'materials' → now shown as Modules
    # some components may have different function names; try both common names
    if hasattr(materials, "render_materials"):
        materials.render_materials()
    else:
        # fallback to older name if present
        materials.render_materials_page()

elif page == "📝 Assignments":
    # load assignments component (create frontend/components/assignments.py)
    try:
        from components import assignments
    except Exception:
        st.error("Assignments component not found. Add frontend/components/assignments.py")
    else:
        # call standardized render function name
        if hasattr(assignments, "render_assignments"):
            assignments.render_assignments()
        elif hasattr(assignments, "render_assignments_page"):
            assignments.render_assignments_page()
        else:
            st.error("assignments component does not expose render_assignments()")