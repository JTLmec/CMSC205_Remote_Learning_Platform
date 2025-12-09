# frontend/components/auth.py
import os
import streamlit as st
from supabase import create_client
from dotenv import load_dotenv
import requests

# load .env for local dev (safe; backend uses service role)
load_dotenv()

# robust import for save_supabase_session to work in different run modes
try:
    from frontend.utils.auth import save_supabase_session
except Exception:
    try:
        from utils.auth import save_supabase_session
    except Exception:
        # last resort — try relative import (if package)
        try:
            from ..utils.auth import save_supabase_session  # type: ignore
        except Exception:
            # allow file to load; login will still work but saving refresh token may fail with a clear error
            def save_supabase_session(resp):
                raise RuntimeError("save_supabase_session unavailable: import failed")


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
API_BASE_FALLBACK = os.getenv("API_BASE", "http://127.0.0.1:8000")

# create supabase client with anon key (frontend safe)
supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


# ---------------------------------------------------------
# SAFE RERUN HELPER
# ---------------------------------------------------------
def _safe_rerun():
    """Streamlit rerun that works across Streamlit versions safely."""
    try:
        if hasattr(st, "experimental_rerun"):
            return st.experimental_rerun()
        if hasattr(st, "rerun"):
            return st.rerun()
    except Exception:
        pass

    # fallback: force a rerun by toggling a value
    st.session_state["_rerun_trigger"] = not st.session_state.get("_rerun_trigger", False)
    try:
        st.stop()
    except Exception:
        raise


# ---------------------------------------------------------
# INTERNAL HELPERS
# ---------------------------------------------------------
def _normalize_login_response(resp):
    """
    Return tuple (session_dict_or_none, user_dict_or_none, access_token_or_none).
    Try many common shapes returned by different supabase-py versions.
    """
    session = None
    user = None
    token = None

    # 1) dict-like responses
    if isinstance(resp, dict):
        data = resp.get("data") or resp
        if isinstance(data, dict):
            session = data.get("session") or data.get("data", {}).get("session")
            if isinstance(session, dict):
                token = token or session.get("access_token") or session.get("accessToken")
            token = token or data.get("access_token") or data.get("accessToken")
            user = data.get("user") or (data if "email" in data else None)

    # 2) object-like responses (older/newer libs)
    if not user:
        try:
            data_attr = getattr(resp, "data", None)
            if isinstance(data_attr, dict):
                session = session or data_attr.get("session")
                if isinstance(session, dict):
                    token = token or session.get("access_token") or session.get("accessToken")
                token = token or data_attr.get("access_token") or data_attr.get("accessToken")
                user = data_attr.get("user") or (data_attr if "email" in data_attr else None)

            if not user and hasattr(resp, "session"):
                possible = getattr(resp, "session", None)
                if isinstance(possible, dict):
                    session = session or possible
                    token = token or possible.get("access_token") or possible.get("accessToken")
            if not user and hasattr(resp, "user"):
                user = getattr(resp, "user", None)
        except Exception:
            pass

    # 3) direct resp.user fallback
    if not user:
        user = getattr(resp, "user", None)

    # 4) normalize user to dict
    if user and not isinstance(user, dict):
        try:
            user = {
                "id": getattr(user, "id", None),
                "email": getattr(user, "email", None),
                "role": getattr(user, "role", None),
            }
        except Exception:
            user = None

    # 5) final token fallback - some responses include token at top-level
    if not token and isinstance(resp, dict):
        token = resp.get("access_token") or resp.get("accessToken") or resp.get("token")

    # 6) ensure token is a string
    if token and not isinstance(token, str):
        try:
            token = str(token)
        except Exception:
            token = None

    return session, user, token


def _fetch_profile_from_backend(token: str):
    """Calls backend /profiles/me to fetch authoritative role & profile."""
    if not token:
        return None

    api_base = st.session_state.get("API_BASE") or API_BASE_FALLBACK
    try:
        resp = requests.get(
            f"{api_base.rstrip('/')}/profiles/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=6,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("user") if isinstance(data, dict) else data
    except Exception:
        pass

    return None


def _fetch_profile_by_user_id(user_id: str):
    """Fallback profile lookup via Supabase anon key."""
    if not user_id:
        return None

    try:
        res = supabase.table("profiles").select("*").eq("id", user_id).limit(1).execute()
        data = None
        if isinstance(res, dict):
            data = res.get("data")
        else:
            data = getattr(res, "data", None)

        if isinstance(data, list) and data:
            return data[0]
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    return None


def _set_user_from_response(resp):
    """
    Normalize and store into st.session_state:
      - st.session_state['supabase_session'] => full session dict when available
      - st.session_state['access_token'] => token string
      - st.session_state['profile'] => authoritative profile (role etc)
      - st.session_state['user'] => legacy compatibility (same as profile)
    Also maps Supabase 'authenticated' role -> 'student'.
    """
    session_obj, user_obj, token = _normalize_login_response(resp)

    # store supabase session obj if present (preserve previous if not found)
    if session_obj and isinstance(session_obj, dict):
        st.session_state["supabase_session"] = session_obj
    else:
        st.session_state["supabase_session"] = st.session_state.get("supabase_session")

    # set access token if found (preserve previous if not)
    if token:
        st.session_state["access_token"] = token
    else:
        st.session_state["access_token"] = st.session_state.get("access_token")

    # Try to fetch authoritative profile from backend first (requires token)
    profile = None
    if st.session_state.get("access_token"):
        profile = _fetch_profile_from_backend(st.session_state["access_token"])

    # Fallback to frontend anon fetch if backend not available or returned nothing
    if not profile and user_obj and isinstance(user_obj, dict):
        user_id = user_obj.get("id")
        profile = _fetch_profile_by_user_id(user_id)

    # Last fallback: construct profile from user_obj at least
    if not profile and isinstance(user_obj, dict):
        profile = {
            "id": user_obj.get("id"),
            "email": user_obj.get("email"),
            "role": user_obj.get("role"),
        }

    # Ensure profile exists as dict
    if not profile:
        profile = {"id": None, "email": None, "role": None}

    # Normalize role to lowercase string if present
    role_val = profile.get("role")
    if isinstance(role_val, str):
        role_val = role_val.lower().strip()

    # Map supabase default "authenticated" -> "student" to match your app roles
    if role_val in ("authenticated", "auth"):
        role_val = "student"

    # If role is None or empty, default to student
    if not role_val:
        role_val = "student"

    profile["role"] = role_val

    # Save authoritative profile to session_state
    st.session_state["profile"] = profile
    # Also set legacy key 'user' for backward compatibility
    st.session_state["user"] = profile


# ---------------------------------------------------------
# PUBLIC AUTH FUNCTIONS
# ---------------------------------------------------------
def login(email: str, password: str) -> bool:
    """
    Robust sign-in: tries modern and older supabase methods and extracts
    the JWT access token into st.session_state['access_token'].
    """
    resp = None
    try:
        resp = supabase.auth.sign_in_with_password({"email": email, "password": password})
    except Exception:
        try:
            resp = supabase.auth.sign_in({"email": email, "password": password})
        except Exception as e:
            st.error(f"Login failed: {e}")
            return False

    # If we got a response, persist session + tokens via save_supabase_session
    try:
        if resp:
            # Persist access + refresh tokens (handles many response shapes)
            save_supabase_session(resp)

            # Populate profile using helpers (this will use access_token stored in session_state)
            try:
                _set_user_from_response(resp)
            except Exception:
                pass

            # UI refresh
            _safe_rerun()
            return True

    except Exception:
        pass

    st.error("Login failed")
    return False


def signup(email: str, password: str):
    try:
        supabase.auth.sign_up({"email": email, "password": password})
        st.success("Account created! Please confirm email then log in.")
    except Exception as e:
        st.error(f"Signup failed: {e}")


def logout():
    # clear session state keys and attempt sign out via client (best-effort)
    st.session_state.pop("supabase_session", None)
    st.session_state.pop("access_token", None)
    st.session_state.pop("profile", None)
    st.session_state.pop("user", None)
    st.session_state.pop("refresh_token", None)

    try:
        supabase.auth.sign_out()
    except Exception:
        pass

    _safe_rerun()


# ---------------------------------------------------------
# AUTH UI
# ---------------------------------------------------------
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
                _safe_rerun()

    with tab_signup:
        new_email = st.text_input("New Email", key="sign_email")
        new_pw = st.text_input("New Password", type="password", key="sign_pw")
        if st.button("Sign Up"):
            signup(new_email, new_pw)