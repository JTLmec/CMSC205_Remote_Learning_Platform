# frontend/utils/backend_api.py
import streamlit as st
import requests

def get_materials():
    API_BASE = st.session_state.get("API_BASE")
    resp = requests.get(f"{API_BASE}/materials/list", timeout=5)
    resp.raise_for_status()
    return resp.json()

def upload_material(file_tuple):
    API_BASE = st.session_state.get("API_BASE")
    resp = requests.post(f"{API_BASE}/materials/upload", files=file_tuple, timeout=60)
    resp.raise_for_status()
    return resp.json()