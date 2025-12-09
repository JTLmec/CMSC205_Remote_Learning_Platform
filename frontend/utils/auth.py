# frontend/utils/auth.py

import os
import time
import json
import base64
import requests
import streamlit as st
from typing import Optional, Dict, Any

# ===============================================================
# CONFIG HELPERS
# ===============================================================

def _supabase_config():
    """
    Reads Supabase URL + ANON key from session_state or environment.
    """
    url = st.session_state.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
    anon = st.session_state.get("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_ANON_KEY")
    return url, anon


# ===============================================================
# SESSION SAVE AFTER LOGIN
# ===============================================================

def save_supabase_session(auth_response: Any) -> None:
    """
    Store Supabase session + user in Streamlit session_state.
    Works with dict or object responses.
    """
    try:
        session = None
        user = None

        if isinstance(auth_response, dict):
            data = auth_response.get("data") or auth_response
            session = data.get("session") or data.get("supabase_session") or data
            user = data.get("user") or data.get("user")

            # Normalize object
            if isinstance(session, dict) and not session.get("access_token"):
                if session.get("accessToken"):
                    session["access_token"] = session["accessToken"]

        else:
            session = getattr(auth_response, "session", None) or getattr(auth_response, "data", None)
            user = getattr(auth_response, "user", None)

        if session:
            st.session_state["supabase_session"] = session

            # Extract access token
            token = session.get("access_token") if isinstance(session, dict) else getattr(session, "access_token", None)
            if token:
                st.session_state["access_token"] = token

            # Extract refresh token
            refresh = session.get("refresh_token") if isinstance(session, dict) else getattr(session, "refresh_token", None)
            if refresh:
                st.session_state["refresh_token"] = refresh

        if user:
            st.session_state["user"] = user

    except Exception:
        pass


# ===============================================================
# JWT PAYLOAD DECODE (no signature verification)
# ===============================================================

def _jwt_payload(token: str) -> Optional[Dict[str, Any]]:
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return None
        payload_b64 = parts[1]
        rem = len(payload_b64) % 4
        if rem:
            payload_b64 += "=" * (4 - rem)
        decoded = base64.urlsafe_b64decode(payload_b64.encode("utf-8"))
        return json.loads(decoded.decode("utf-8"))
    except Exception:
        return None


def _token_expired(token: str, leeway: int = 30) -> bool:
    """
    Returns True if expired or exp cannot be read.
    """
    if not token:
        return True

    payload = _jwt_payload(token)
    if not payload:
        return True

    exp = payload.get("exp")
    if not exp:
        return True

    now = int(time.time())
    return now >= (int(exp) - leeway)


# ===============================================================
# REFRESH SESSION VIA REFRESH TOKEN
# ===============================================================

def refresh_supabase_session() -> bool:
    """
    Attempts to refresh token with stored refresh_token.
    Returns True → session updated
    Returns False → refresh failed
    """
    refresh_token = st.session_state.get("refresh_token")
    SUPABASE_URL, SUPABASE_ANON = _supabase_config()

    if not refresh_token or not SUPABASE_URL or not SUPABASE_ANON:
        return False

    url = f"{SUPABASE_URL.rstrip('/')}/auth/v1/token?grant_type=refresh_token"
    headers = {
        "apikey": SUPABASE_ANON,
        "Content-Type": "application/json",
    }
    body = {"refresh_token": refresh_token}

    try:
        r = requests.post(url, headers=headers, json=body, timeout=8)
    except Exception:
        return False

    if r.status_code != 200:
        return False

    try:
        data = r.json()
    except Exception:
        return False

    access_token = data.get("access_token") or data.get("accessToken")
    refresh_token = data.get("refresh_token") or data.get("refreshToken")

    session = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "raw": data,
    }

    st.session_state["supabase_session"] = session

    if access_token:
        st.session_state["access_token"] = access_token
    if refresh_token:
        st.session_state["refresh_token"] = refresh_token

    return True


# ===============================================================
# PUBLIC API: GET AUTH HEADERS WITH AUTO REFRESH
# ===============================================================

def get_auth_headers(content_type: Optional[str] = "application/json") -> Dict[str, str]:
    """
    Provides:
        { "Authorization": "Bearer <token>", "Content-Type": ... }

    Auto-refreshes when token expired.
    Notes:
        - Pass content_type=None for multipart uploads
        - Returns {} if refresh fails → user must log in again
    """
    headers = {}
    token = st.session_state.get("access_token")

    # Maybe session stored token
    if not token:
        sess = st.session_state.get("supabase_session") or {}
        if isinstance(sess, dict):
            token = sess.get("access_token") or sess.get("accessToken")

            # Sync refresh token
            if not st.session_state.get("refresh_token"):
                rt = sess.get("refresh_token") or sess.get("refreshToken")
                if rt:
                    st.session_state["refresh_token"] = rt

    # If expired, try refresh
    if token and _token_expired(token):
        if refresh_supabase_session():
            token = st.session_state.get("access_token")
        else:
            # Clear session
            for key in ("access_token", "refresh_token", "supabase_session", "user"):
                st.session_state.pop(key, None)
            return {}

    # Build headers if valid token
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # Add content-type if not disabled (multipart uploads must NOT set)
    if content_type:
        headers["Content-Type"] = content_type

    return headers