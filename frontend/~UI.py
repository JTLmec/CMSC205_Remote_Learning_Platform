# frontend/UI.py
import os
import streamlit as st
import requests

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")

st.set_page_config(page_title="Remote Learning Platform", layout="wide")
st.title("Remote Learning Platform (UI)")

tabs = st.tabs(["Home", "Materials", "Upload"])

# ---------------- Home ----------------
with tabs[0]:
    st.write("Welcome! Use the Materials tab to view files. Use Upload to add materials.")

# ---------------- Materials ----------------
with tabs[1]:
    st.header("Materials")

    if st.button("Refresh materials list"):
        st.rerun()

    def fetch_materials():
        try:
            resp = requests.get(f"{API_BASE}/materials/list", timeout=5)
            if resp.status_code == 200:
                return resp.json()
            else:
                st.error(f"List API error: {resp.status_code} {resp.text}")
                return []
        except Exception as e:
            st.error(f"Request error: {e}")
            return []

    files = fetch_materials()

    if not files:
        st.info("No files found.")
    else:
        for f in files:
            # Expected keys from backend normalization
            path = f.get("path") or f.get("name") or ""
            url = f.get("url") or ""
            display = f.get("display_name") or (path.split("_", 1)[-1] if path else "unknown")

            st.write(f"### 📄 {display}")

            col1, col2, col3 = st.columns([3, 1.5, 2])

            # Show link
            #if url:
            #    col1.markdown(f"[🔗 Open in Browser]({url})", unsafe_allow_html=True)

            # Real download button
            if col2.button("⬇ Download", key="download_" + path):
                try:
                    file_bytes = requests.get(url).content
                    st.download_button(
                        label=f"Click to Save {display}",
                        data=file_bytes,
                        file_name=display,
                        mime="application/pdf",
                        key="download_button_" + path
                    )
                except Exception as e:
                    st.error(f"Download error: {e}")

            st.write("---")

# ---------------- Upload ----------------
with tabs[2]:
    st.header("Upload Material")
    uploaded = st.file_uploader("Upload PDF", type=["pdf"])

    if st.button("Upload"):
        if not uploaded:
            st.warning("Please choose a file first")
        else:
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