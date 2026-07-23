"""Page 2 — Live analysis with streamed agent logs."""
import streamlit as st

from orchestrator.graph import stream_analysis

AGENT_LABELS = {
    "bug_hunter": "🐛 BugHunterAgent",
    "code_smell": "👃 CodeSmellAgent",
    "complexity": "📐 ComplexityAgent",
    "test_generator": "🧪 TestGeneratorAgent",
    "report_writer": "📝 ReportWriterAgent",
}


def render():
    st.header("2. Live Analysis")

    if "code" not in st.session_state:
        st.warning("No file submitted. Go back to step 1.")
        return

    if not st.session_state.get("trigger_analysis") and "final_state" not in st.session_state:
        st.info("Click 'Run analysis' from the Upload page.")
        return

    log_box = st.empty()
    progress_bars = {name: st.progress(0, text=label) for name, label in AGENT_LABELS.items()}
    logs = []

    if st.session_state.get("trigger_analysis"):
        final_state = {}
        for node_name, partial in stream_analysis(
            st.session_state["code"], st.session_state["filename"], st.session_state["language"]
        ):
            logs.append(f"[{node_name}] done.")
            log_box.code("\n".join(logs))
            if node_name in progress_bars:
                progress_bars[node_name].progress(100, text=f"{AGENT_LABELS[node_name]} ✅")
            final_state.update(partial)

        st.session_state["final_state"] = final_state
        st.session_state["trigger_analysis"] = False
        st.success("Analysis complete. Check the Results tab.")
    else:
        st.success("Analysis already completed for this file.")
