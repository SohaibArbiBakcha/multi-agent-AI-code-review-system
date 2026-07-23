"""Agent 3 — ComplexityAgent.

For Python, Radon computes real cyclomatic complexity, maintainability
index and Halstead metrics. Radon only parses Python, so for other
languages the LLM estimates the same schema directly from the code —
labeled as an estimate, since it is not a deterministic measurement.
"""
from loguru import logger

from llm.ollama_client import OllamaUnavailableError, generate_json
from tools.language_detect import describe_language
from tools.static_analysis import run_radon

HOTSPOT_SYSTEM_PROMPT = """You are a software quality expert. You are given Radon
complexity metrics for a Python file (a list of blocks with their
cyclomatic complexity). Identify the 3 riskiest functions ("hotspots")
and briefly explain why in English. Respond ONLY with a JSON array:
[{"function": str, "score": <float>, "reason": str}, ...]"""

GENERIC_SYSTEM_PROMPT = """You are a software quality expert specialized in {language}.
Analyze the provided source code and ESTIMATE (no exact measurement tool
exists here for this language) the following metrics. Respond ONLY with
a JSON object of the form:
{{"cyclomatic_avg": <float>, "maintainability_index": <float 0-100>,
 "hotspots": [{{"function": str, "score": <float>, "reason": str}}]}}"""


def _grade(mi: float) -> str:
    if mi >= 85:
        return "A"
    if mi >= 70:
        return "B"
    if mi >= 50:
        return "C"
    if mi >= 25:
        return "D"
    return "F"


def _run_python(code: str) -> dict:
    metrics = run_radon(code)
    if "error" in metrics:
        return metrics

    blocks = metrics.get("cyclomatic_blocks", [])
    hotspots = []
    if blocks:
        try:
            hotspots = generate_json(str(blocks), HOTSPOT_SYSTEM_PROMPT)
        except (OllamaUnavailableError, ValueError) as exc:
            logger.warning(f"Complexity: LLM hotspot analysis unavailable ({exc})")
            top = sorted(blocks, key=lambda b: b["complexity"], reverse=True)[:3]
            hotspots = [
                {"function": b["name"], "score": b["complexity"], "reason": "High cyclomatic complexity"}
                for b in top
            ]

    return {
        "cyclomatic_avg": metrics["cyclomatic_avg"],
        "maintainability_index": metrics["maintainability_index"],
        "halstead": metrics["halstead"],
        "grade": _grade(metrics["maintainability_index"]),
        "hotspots": hotspots,
    }


def _run_generic(code: str, language: str) -> dict:
    system = GENERIC_SYSTEM_PROMPT.format(language=describe_language(language))
    try:
        result = generate_json(code, system)
    except (OllamaUnavailableError, ValueError) as exc:
        logger.warning(f"Complexity: LLM estimate unavailable for {language} ({exc})")
        return {"cyclomatic_avg": 10, "maintainability_index": 50, "grade": "C", "hotspots": [], "estimated": True}

    mi = result.get("maintainability_index", 50)
    return {
        "cyclomatic_avg": result.get("cyclomatic_avg", 10),
        "maintainability_index": mi,
        "grade": _grade(mi),
        "hotspots": result.get("hotspots", []),
        "estimated": True,
    }


def run(code: str, language: str = "python") -> dict:
    if language == "python":
        return _run_python(code)
    return _run_generic(code, language)
