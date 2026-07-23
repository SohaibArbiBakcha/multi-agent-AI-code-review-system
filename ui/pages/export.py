"""Page 4 — PDF export."""
import streamlit as st

from tools.pdf_generator import generate_pdf


def render():
    st.header("4. Export Report")
    state = st.session_state.get("final_state")
    if not state:
        st.warning("No results available. Run an analysis first.")
        return

    state = {**state, "filename": st.session_state.get("filename", "unknown.py")}

    if st.button("Generate PDF"):
        pdf_bytes = generate_pdf(state)
        st.session_state["pdf_bytes"] = pdf_bytes
        st.success("PDF generated.")

    if "pdf_bytes" in st.session_state:
        st.download_button(
            "Download PDF report",
            data=st.session_state["pdf_bytes"],
            file_name=f"codesentinel_{state['filename'].replace('.py', '')}.pdf",
            mime="application/pdf",
        )
