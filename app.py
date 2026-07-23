"""CodeSentinel — Streamlit entrypoint.

Run locally with:  streamlit run app.py
Requires Ollama running (ollama serve) with qwen2.5-coder:7b and mistral:7b pulled.
"""
import streamlit as st
from dotenv import load_dotenv

from ui.pages import export, live_analysis, results, upload

load_dotenv()

st.set_page_config(page_title="CodeSentinel", page_icon="🛡️", layout="wide")

PAGES = {
    "Upload": upload,
    "Live Analysis": live_analysis,
    "Results": results,
    "Export": export,
}

with st.sidebar:
    st.title("🛡️ CodeSentinel")
    st.caption("Multi-agent code review — 100% local")
    default_page = st.session_state.get("page", "Upload")
    page_name = st.radio("Navigation", list(PAGES.keys()), index=list(PAGES.keys()).index(default_page))
    st.session_state["page"] = page_name
    st.divider()
    st.caption("ISMAGI — Final Year Project 2025-2026")

PAGES[page_name].render()
