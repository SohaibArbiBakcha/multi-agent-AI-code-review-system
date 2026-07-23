"""Page 1 — Upload & Config."""
import streamlit as st

from tools.language_detect import EXTENSION_MAP, detect_language, is_fully_supported

# Dropdown options: every language we can detect, sorted, "auto" first.
LANGUAGE_OPTIONS = ["Auto-detect"] + sorted(set(EXTENSION_MAP.values()))


def render():
    st.header("1. Submit your code")
    st.caption(
        "Drop a source file, in any programming language. The language is "
        "detected automatically; Python additionally benefits from dedicated "
        "static analysis (Pylint/Bandit/Radon)."
    )

    uploaded = st.file_uploader("Source file", type=None)

    if uploaded is not None:
        code = uploaded.getvalue().decode("utf-8", errors="replace")
        detected = detect_language(uploaded.name, code)

        default_index = (
            LANGUAGE_OPTIONS.index(detected) if detected in LANGUAGE_OPTIONS else 0
        )
        choice = st.selectbox(
            f"Detected language: **{detected}**  -  confirm or correct:",
            options=LANGUAGE_OPTIONS,
            index=default_index,
        )
        language = detected if choice == "Auto-detect" else choice

        if is_fully_supported(language):
            st.success(f"'{language}': dedicated static analysis + LLM (Pylint, Bandit, Radon).")
        elif language == "unknown":
            st.warning("Language not recognized: analysis will rely entirely on the LLM.")
        else:
            st.info(f"'{language}': analysis handled entirely by the LLM (no dedicated static tool for this language).")

        st.session_state["filename"] = uploaded.name
        st.session_state["language"] = language
        st.session_state["code"] = code
        st.code(code, language=language if language != "unknown" else None, line_numbers=True)

        if st.button("Run analysis", type="primary"):
            st.session_state["page"] = "Live Analysis"
            st.session_state["trigger_analysis"] = True
            st.rerun()
    else:
        st.info("Waiting for a source file.")
