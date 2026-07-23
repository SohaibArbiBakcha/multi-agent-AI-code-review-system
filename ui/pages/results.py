"""Page 3 — Results dashboard (tabs: Bugs / Smells / Complexity / Tests / Report)."""
import matplotlib.pyplot as plt
import streamlit as st


def _score_card(score: dict):
    col1, col2 = st.columns([1, 3])
    with col1:
        st.metric("Grade", score.get("grade", "N/A"))
    with col2:
        st.metric("Global score", f"{score.get('value', 'N/A')} / 100")


def render():
    st.header("3. Analysis Results")
    state = st.session_state.get("final_state")
    if not state:
        st.warning("No results available. Run an analysis first.")
        return

    _score_card(state.get("score", {}))

    tab_bugs, tab_smells, tab_complexity, tab_tests, tab_report = st.tabs(
        ["Bugs", "Smells", "Complexity", "Tests", "Report"]
    )

    with tab_bugs:
        bugs = state.get("agent1_result", [])
        st.write(f"{len(bugs)} issue(s) detected")
        for b in bugs:
            with st.expander(f"L.{b.get('line', '?')} — {b.get('type', 'bug')}"):
                st.write(b.get("description", ""))
                st.caption(f"Suggestion: {b.get('suggestion', '')}")

    with tab_smells:
        smells = state.get("agent2_result", [])
        st.write(f"{len(smells)} code smell(s) detected")
        for s in smells:
            with st.expander(f"{s.get('smell_type', '')} — {s.get('location', '')}"):
                st.write(f"Severity: {s.get('severity', '')}")
                st.caption(f"Refactor: {s.get('refactor', '')}")

    with tab_complexity:
        complexity = state.get("agent3_result", {})
        st.json(complexity)
        blocks = complexity.get("cyclomatic_blocks", [])
        if blocks:
            fig, ax = plt.subplots()
            names = [b["name"] for b in blocks]
            values = [b["complexity"] for b in blocks]
            ax.barh(names, values, color="#3B82F6")
            ax.set_xlabel("Cyclomatic complexity")
            st.pyplot(fig)

    with tab_tests:
        st.code(state.get("agent4_result", ""), language=state.get("language", "python"), line_numbers=True)

    with tab_report:
        report = state.get("agent5_result", {})
        st.markdown(report.get("markdown", "Report not available.") if isinstance(report, dict) else str(report))
