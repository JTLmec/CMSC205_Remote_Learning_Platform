# frontend/components/dashboard.py
import os
import streamlit as st
import requests
from typing import Dict, List

def _api_base() -> str:
    return st.session_state.get("API_BASE") or os.getenv("API_BASE", "http://127.0.0.1:8000")

def _sanitize_key(*parts) -> str:
    s = "__".join([str(p).replace(" ", "_").replace("/", "__") for p in parts if p])
    return s[:180]

def _get_materials() -> List[Dict]:
    API_BASE = _api_base()
    try:
        resp = requests.get(f"{API_BASE}/materials/list", timeout=10)
        if resp.status_code == 200:
            return resp.json() or []
        else:
            st.error(f"Failed to fetch materials: {resp.status_code}")
            return []
    except Exception as e:
        st.error(f"Materials request error: {e}")
        return []

def _init_checklist_for_subject(subject: str):
    key = "checklist__" + _sanitize_key(subject)
    if key not in st.session_state:
        st.session_state[key] = {
            "attendance": False,
            "read_materials": False,
            "submitted_assignment": False
        }
    return key

# debug - temporary: show raw materials in the sidebar
st.sidebar.subheader("DEBUG: raw materials response")
try:
    resp_debug = requests.get(f"{_api_base()}/materials/list", timeout=5)
    st.sidebar.write("status", resp_debug.status_code)
    st.sidebar.write(resp_debug.json() if resp_debug.status_code == 200 else resp_debug.text)
except Exception as e:
    st.sidebar.write("request error:", str(e))


def render_dashboard():
    st.header("📋 Dashboard — Your Subjects & Tasks")

    materials = _get_materials()

    # group materials by subject
    subjects: Dict[str, List[dict]] = {}
    for m in materials:
        subj = m.get("subject") or "Uncategorized"
        subjects.setdefault(subj, []).append(m)

    # hide Uncategorized by default, but keep available
    subjects_visible = {k: v for k, v in subjects.items() if k != "Uncategorized"}
    uncategorized_items = subjects.get("Uncategorized", [])

    if not subjects_visible and not uncategorized_items:
        st.info("No subjects/materials found. Upload modules in the Modules tab.")
        return

    # Layout: two columns - left: Checklist table per subject, right: Unread materials table
    left_col, right_col = st.columns([1, 2])

    # ---------- LEFT: Checklist table ----------
    with left_col:
        st.subheader("✅ Quick Checklist (per subject)")
        # Build a table-like display
        for subject in sorted(subjects_visible.keys(), key=lambda s: s.lower()):
            key = _init_checklist_for_subject(subject)
            checklist = st.session_state[key]

            with st.expander(f"{subject}", expanded=False):
                col1, col2 = st.columns([2, 1])
                with col1:
                    checked_att = st.checkbox("Attendance", key=_sanitize_key(subject, "attendance"), value=checklist["attendance"])
                    checked_read = st.checkbox("Read materials", key=_sanitize_key(subject, "read"), value=checklist["read_materials"])
                    checked_sub = st.checkbox("Submitted assignment", key=_sanitize_key(subject, "submitted"), value=checklist["submitted_assignment"])
                with col2:
                    if st.button("Reset", key=_sanitize_key("reset", subject)):
                        st.session_state[key] = {"attendance": False, "read_materials": False, "submitted_assignment": False}
                        st.experimental_rerun()

                # persist changes
                st.session_state[key]["attendance"] = checked_att
                st.session_state[key]["read_materials"] = checked_read
                st.session_state[key]["submitted_assignment"] = checked_sub

        st.write("---")
        st.markdown("You can persist these checklists later to your account in Supabase if desired.")

    # ---------- RIGHT: Unread Materials ----------
    with right_col:
        st.subheader("📚 Unread / Pending Materials")
        any_unread = False
        for subject in sorted(subjects_visible.keys(), key=lambda s: s.lower()):
            key = _init_checklist_for_subject(subject)
            checklist = st.session_state[key]
            # unread rule: if read_materials is False, consider all materials "unread"
            if not checklist["read_materials"]:
                items = subjects_visible[subject]
                if items:
                    any_unread = True
                    st.markdown(f"### {subject} — {len(items)} item{'s' if len(items) != 1 else ''}")
                    for item in items:
                        display = item.get("display_name") or item.get("filename") or item.get("path")
                        url = item.get("url")
                        c1, c2 = st.columns([6, 1])
                        c1.write(display)
                        if url:
                            if c2.button("Download", key=_sanitize_key("dl", subject, item.get("path"))):
                                st.markdown(f"[⬇️ Download **{display}**]({url})")
                        else:
                            c2.write("—")
                    if st.button(f"Mark all read: {subject}", key=_sanitize_key("mark_read", subject)):
                        st.session_state[key]["read_materials"] = True
                        st.experimental_rerun()
        if not any_unread:
            st.info("No unread materials — great job!")

        # show uncategorized items (optional)
        if uncategorized_items:
            st.write("---")
            st.subheader("Unassigned Materials")
            st.write("These items have no subject (uploaded before subjects were required). You can reassign them in the backend or re-upload under a subject.")
            for item in uncategorized_items:
                display = item.get("display_name") or item.get("filename") or item.get("path")
                url = item.get("url")
                sc1, sc2 = st.columns([6, 2])
                sc1.write(display)
                if url:
                    if sc2.button("Download", key=_sanitize_key("dl_uncat", item.get("path"))):
                        st.markdown(f"[⬇️ Download **{display}**]({url})")
                else:
                    sc2.write("—")
                # placeholder: assign subject UI (works only if you implement backend endpoint to move files)
                # new_subject = sc1.text_input("Assign subject (dev only)", key=_sanitize_key("assign", item.get("path")))
                # if sc2.button("Assign", key=_sanitize_key("assign_btn", item.get("path"))):
                #     # call backend endpoint to move object to new_subject/<filename>
                #     pass