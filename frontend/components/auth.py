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
    Normalize different supabase return shapes.
    Sets:
      st.session_state['user'] = { 'email': ..., 'id': ..., ... }  (a dict)
      st.session_state['access_token'] = "<token>"  (string) if available
    """
    user = None
    token = None

    # common dict shape: { "data": { "user": {...}, "session": {...} }, "error": None }
    if isinstance(res, dict):
        data = res.get("data") or res
        # nested 'user' in 'data'
        if isinstance(data, dict):
            # session-based response
            session = data.get("session") or data.get("data", {}).get("session")
            if session and isinstance(session, dict):
                token = session.get("access_token") or session.get("accessToken")
            # direct user object
            user = data.get("user") or data.get("user", None)
            # sometimes user is directly in 'data'
            if not user and "email" in data:
                user = {k: data.get(k) for k in ("id", "email", "role") if k in data}
    else:
        # object-like responses (older libs)
        user = getattr(res, "user", None) or getattr(res, "data", None)

    # fallback: if user is nested in session->user
    if not user and isinstance(data, dict):
        sess = data.get("session")
        if isinstance(sess, dict):
            maybe_user = sess.get("user")
            if maybe_user:
                user = maybe_user
                token = token or sess.get("access_token")

    # final fallback: if res has .data and that .data has .user
    if not user:
        try:
            data_attr = getattr(res, "data", None)
            if isinstance(data_attr, dict):
                user = data_attr.get("user") or data_attr
            elif hasattr(data_attr, "user"):
                user = getattr(data_attr, "user", None)
        except Exception:
            pass

    # write into session_state in minimal safe form
    if isinstance(user, dict):
        st.session_state["user"] = {"email": user.get("email"), "id": user.get("id"), "role": user.get("role")}
    elif user:
        # object-like user
        st.session_state["user"] = {"email": getattr(user, "email", None), "id": getattr(user, "id", None)}
    else:
        st.session_state["user"] = None

    if token:
        st.session_state["access_token"] = token

def login(email: str, password: str):
    try:
        # supabase-py modern API
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        # set session vars
        _set_user_from_response(res)
        return True
    except Exception as e:
        st.error(f"Login failed: {e}")
        return False

def signup(email: str, password: str):
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        st.success("Account created! Please log in.")
    except Exception as e:
        st.error(f"Signup failed: {e}")

def logout():
    # clear state and rerun
    st.session_state["user"] = None
    st.session_state["access_token"] = None
    # use current API to rerun
    try:
        st.rerun()
    except Exception:
        pass

def render_auth():
    st.title("Please sign in")
    tab_login, tab_signup = st.tabs(["Login", "Sign Up"])
    with tab_login:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pw")
        if st.button("Login"):
            ok = login(email, password)
            if ok:
                st.success("Logged in")
                # Force a rerun so main.py sees st.session_state['user']
                st.rerun()

    with tab_signup:
        new_email = st.text_input("New Email", key="sign_email")
        new_pw = st.text_input("New Password", type="password", key="sign_pw")
        if st.button("Sign Up"):
            signup(new_email, new_pw)