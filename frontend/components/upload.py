# frontend/components/upload.py
import streamlit as st
import requests

def render_upload():
    st.header("Upload Material")
    uploaded = st.file_uploader("Upload PDF", type=["pdf"])
    if st.button("Upload"):
        if not uploaded:
            st.warning("Please choose a file first")
            return
        API_BASE = st.session_state.get("API_BASE")
        try:
            files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type)}
            r = requests.post(f"{API_BASE}/materials/upload", files=files, timeout=60)
            if r.status_code == 200:
                st.success("Upload successful")
                st.json(r.json())
            else:
                st.error(f"Upload failed ({r.status_code}) - {r.text}")
        except Exception as e:
            st.error(str(e))