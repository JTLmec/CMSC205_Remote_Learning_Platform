# frontend/main.py
import os
import streamlit as st

# Try importing both ways so it works whether you run:
#   streamlit run frontend/main.py
# OR
#   cd frontend && streamlit run main.py
try:
    from frontend.components import auth as auth_comp
    from frontend.components import assignments
    from frontend.components import modules
    from frontend.components import dashboard
except Exception:
    from components import auth as auth_comp
    from components import assignments
    from components import modules
    from components import dashboard

# -----------------------------------------
# GLOBAL PAGE CONFIG
# -----------------------------------------
st.set_page_config(page_title="Remote Learning Platform", layout="wide")

# -----------------------------------------
# APP BASE URL (frontend to backend)
# -----------------------------------------
API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")
st.session_state["API_BASE"] = API_BASE

# -----------------------------------------
# ROUTING HELPER
# -----------------------------------------
def _nav():
    if "nav" not in st.session_state:
        st.session_state["nav"] = "Login"
    return st.session_state["nav"]

# -----------------------------------------
# SIDEBAR MENU
# -----------------------------------------
with st.sidebar:
    st.title("Navigation")

    # Show different menus depending on login
    profile = st.session_state.get("profile") or st.session_state.get("user")

    if profile:
        role = (profile.get("role") or "").lower()
        email = profile.get("email", "unknown")

        st.markdown(f"**User:** {email}")
        st.markdown(f"**Role:** {role.capitalize()}")

        if st.button("Logout"):
            auth_comp.logout()
            st.stop()

        st.markdown("---")

        # Navigation items (Materials removed)
        # include Dashboard for quick overview
        pages = ["Dashboard", "Assignments", "Modules"]

        # Ensure stored nav is valid for logged-in users
        current_nav = st.session_state.get("nav", "Dashboard")
        if current_nav == "Login":
            current_nav = "Dashboard"
        if current_nav not in pages:
            current_nav = "Dashboard"

        st.session_state["nav"] = st.radio("Go to:", pages, index=pages.index(current_nav))

    else:
        st.session_state["nav"] = st.radio("Go to:", ["Login"], index=0)

# -----------------------------------------
# PAGE CONTENT HANDLING
# -----------------------------------------
current = _nav()

# LOGIN PAGE
if current == "Login":
    auth_comp.render_auth()
    st.stop()

# AUTH REQUIRED PAGES
profile = st.session_state.get("profile") or st.session_state.get("user")
if not profile:
    st.warning("You must log in to continue.")
    auth_comp.render_auth()
    st.stop()

# ROUTE
if current == "Dashboard":
    dashboard.render_dashboard()
elif current == "Assignments":
    assignments.render_assignments()
elif current == "Modules":
    modules.render_modules()