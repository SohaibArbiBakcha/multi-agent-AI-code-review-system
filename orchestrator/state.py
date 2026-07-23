"""Shared state passed between every node of the LangGraph pipeline."""
from typing import Any, TypedDict


class CodeSentinelState(TypedDict, total=False):
    input_code: str
    language: str
    filename: str

    agent1_result: list[dict]   # BugHunter
    agent2_result: list[dict]   # CodeSmell
    agent3_result: dict         # Complexity
    agent4_result: str          # TestGenerator (pytest file content)
    agent5_result: dict         # ReportWriter ({"markdown": ...})

    score: dict[str, Any]       # {"value": float, "grade": str}
    status: str
    logs: list[str]
