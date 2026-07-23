"""LangGraph pipeline: Phase 1 (parallel) -> Phase 2 -> Phase 3.

Phase 1 runs BugHunter, CodeSmell and Complexity concurrently since none
of them depend on each other's output. Phase 2 (TestGenerator) and
Phase 3 (ReportWriter) run sequentially because each consumes the
previous phase's results. See report Chapter 2.4 for the design rationale.
"""
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from langgraph.graph import END, START, StateGraph
from loguru import logger

from agents import bug_hunter, code_smell, complexity, report_writer, test_generator
from orchestrator.scoring import compute_score
from orchestrator.state import CodeSentinelState
from tools.language_detect import detect_language

AGENT_TIMEOUT = int(os.getenv("AGENT_TIMEOUT_SECONDS", "120"))


def _with_timeout(fn, *args, fallback):
    """Run fn(*args) in a worker thread, returning fallback on timeout/error
    so a single stuck agent never blocks the whole pipeline (see 2.4)."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn, *args)
        try:
            return future.result(timeout=AGENT_TIMEOUT)
        except FutureTimeoutError:
            logger.error(f"{fn.__module__}: timed out after {AGENT_TIMEOUT}s")
            return fallback
        except Exception as exc:
            logger.error(f"{fn.__module__}: failed ({exc})")
            return fallback


def _node_bug_hunter(state: CodeSentinelState) -> dict:
    logger.info("Phase 1 -> BugHunterAgent")
    result = _with_timeout(bug_hunter.run, state["input_code"], state["language"], fallback=[])
    return {"agent1_result": result}


def _node_code_smell(state: CodeSentinelState) -> dict:
    logger.info("Phase 1 -> CodeSmellAgent")
    result = _with_timeout(code_smell.run, state["input_code"], state["language"], fallback=[])
    return {"agent2_result": result}


def _node_complexity(state: CodeSentinelState) -> dict:
    logger.info("Phase 1 -> ComplexityAgent")
    result = _with_timeout(complexity.run, state["input_code"], state["language"], fallback={})
    return {"agent3_result": result}


def _node_test_generator(state: CodeSentinelState) -> dict:
    logger.info("Phase 2 -> TestGeneratorAgent")
    module_name = state.get("filename", "solution").rsplit(".", 1)[0]
    result = _with_timeout(
        test_generator.run, state["input_code"], module_name, state["language"],
        fallback="# Timeout: generation de tests non disponible.\n",
    )
    return {"agent4_result": result}


def _node_report_writer(state: CodeSentinelState) -> dict:
    logger.info("Phase 3 -> ReportWriterAgent")
    score = compute_score(
        state.get("agent1_result", []),
        state.get("agent2_result", []),
        state.get("agent3_result", {}),
    )
    report = report_writer.run(
        state.get("filename", "unknown.py"),
        state.get("agent1_result", []),
        state.get("agent2_result", []),
        state.get("agent3_result", {}),
        state.get("agent4_result", ""),
        score,
        state.get("language", "python"),
    )
    return {"agent5_result": report, "score": score, "status": "completed"}


def build_graph():
    graph = StateGraph(CodeSentinelState)

    graph.add_node("bug_hunter", _node_bug_hunter)
    graph.add_node("code_smell", _node_code_smell)
    graph.add_node("complexity", _node_complexity)
    graph.add_node("test_generator", _node_test_generator)
    graph.add_node("report_writer", _node_report_writer)

    # Phase 1 — fan-out from START, fan-in into Phase 2
    for node in ("bug_hunter", "code_smell", "complexity"):
        graph.add_edge(START, node)
        graph.add_edge(node, "test_generator")

    # Phase 2 -> Phase 3
    graph.add_edge("test_generator", "report_writer")
    graph.add_edge("report_writer", END)

    return graph.compile()


def analyze(code: str, filename: str, language: str | None = None) -> CodeSentinelState:
    """Synchronous convenience entrypoint used by the Streamlit app.

    `language` is auto-detected from the filename/content when not given
    explicitly (e.g. by the upload page after the user confirms/overrides it).
    """
    app = build_graph()
    initial: CodeSentinelState = {
        "input_code": code,
        "filename": filename,
        "language": language or detect_language(filename, code),
        "status": "running",
        "logs": [],
    }
    return app.invoke(initial)


def stream_analysis(code: str, filename: str, language: str | None = None):
    """Yields (node_name, partial_state) as each agent completes, for live UI updates."""
    app = build_graph()
    initial: CodeSentinelState = {
        "input_code": code,
        "filename": filename,
        "language": language or detect_language(filename, code),
        "status": "running",
        "logs": [],
    }
    for event in app.stream(initial, stream_mode="updates"):
        for node_name, partial_state in event.items():
            yield node_name, partial_state
