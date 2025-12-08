# frontend/components/auth.py
import os
import streamlit as st
from supabase import create_client
from dotenv import load_dotenv


load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

def _set_user_from_response(res):
    """
    Normalize supabase response into a small dict and store in session_state.
    Keeps only safe fields we actually need in the UI.
    """
    user_obj = None

    # supabase python client returns either dict-like or object-like
    if isinstance(res, dict):
        # many SDK calls return {"user": {...}, ...}
        user_obj = res.get("user") or res.get("data") or res
    else:
        user_obj = getattr(res, "user", None) or res

    # Extract minimal, safe fields
    if user_obj:
        try:
            # user_obj may be a simple dict or a model-like object
            email = user_obj.get("email") if isinstance(user_obj, dict) else getattr(user_obj, "email", None)
            user_id = user_obj.get("id") if isinstance(user_obj, dict) else getattr(user_obj, "id", None)
            role = user_obj.get("role") if isinstance(user_obj, dict) else getattr(user_obj, "role", None)
            confirmed = user_obj.get("confirmed_at") if isinstance(user_obj, dict) else getattr(user_obj, "confirmed_at", None)
            last_sign_in = user_obj.get("last_sign_in_at") if isinstance(user_obj, dict) else getattr(user_obj, "last_sign_in_at", None)
        except Exception:
            email = None
            user_id = None
            role = None
            confirmed = None
            last_sign_in = None

        # Keep only the fields we need (safe to show in UI)
        st.session_state["user"] = {
            "email": email,
            "id": str(user_id) if user_id else None,
            "role": role,
            "confirmed_at": str(confirmed) if confirmed else None,
            "last_sign_in_at": str(last_sign_in) if last_sign_in else None,
        }

def login(email: str, password: str):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        # res shape may be {'data': {'session': {...}, 'user': {...}}}
        session = None
        if isinstance(res, dict) and "data" in res:
            session = res["data"].get("session") or res["data"]
        elif hasattr(res, "data"):
            session = res.data
        access_token = None
        user = None
        if session:
            access_token = session.get("access_token") or session.get("accessToken") or session.get("token")
            user = session.get("user") or session.get("user")
        # fallback: check res directly
        if not access_token and isinstance(res, dict):
            access_token = res.get("access_token") or res.get("accessToken")
            user = user or res.get("user")
        if access_token:
            st.session_state["access_token"] = access_token
        if user:
            # store at least email and id
            if isinstance(user, dict):
                st.session_state["user"] = {"email": user.get("email"), "id": user.get("id"), "role": user.get("role")}
            else:
                st.session_state["user"] = {"email": getattr(user, "email", None), "id": getattr(user, "id", None)}
        return True
    except Exception as e:
        st.error(f"Login failed: {e}")
        return False

def signup(email: str, password: str):
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        #st.write("DEBUG RESPONSE:", res)  # TEMPORARY
        st.success("Account created! Please log in.")
    except Exception as e:
        st.error(f"Signup failed: {e}")

def logout():
    try:
        # supabase python lib may not implement sign_out server-side; just clear session
        st.session_state["user"] = None
        st.rerun()
    except Exception:
        st.session_state["user"] = None

def render_auth():
    st.title("Please sign in")
    tab_login, tab_signup = st.tabs(["Login", "Sign Up"])
    with tab_login:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pw")
        if st.button("Login"):
            if login(email, password):
                st.success("Logged in")
                st.rerun()

    with tab_signup:
        new_email = st.text_input("New Email", key="sign_email")
        new_pw = st.text_input("New Password", type="password", key="sign_pw")
        if st.button("Sign Up"):
            signup(new_email, new_pw)