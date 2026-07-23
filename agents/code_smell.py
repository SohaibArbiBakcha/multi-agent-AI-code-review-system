"""Agent 2 — CodeSmellAgent.

For Python, AST-based structural heuristics (tools.ast_parser) do the
detection and the LLM only refines severity/refactor advice. For other
languages there is no Python-specific AST to walk, so the LLM performs
the detection directly.
"""
from loguru import logger

from llm.ollama_client import OllamaUnavailableError, generate_json
from tools.ast_parser import detect_all_smells
from tools.language_detect import describe_language

REFINE_SYSTEM_PROMPT = """You are a Python code quality expert. You are given a
list of automatically detected code smells. For each one, confirm or
refine the severity ("low", "medium" or "high") and give a short,
actionable refactoring tip. Respond ONLY with a JSON array of the form:
[{"smell_type": str, "location": str, "severity": "low|medium|high", "refactor": str}, ...]
Keep the same number of elements as the provided list, in the same order."""

GENERIC_SYSTEM_PROMPT = """You are a {language} code quality expert. Analyze the
provided source code and identify code smells and bad practices
(overly long functions, duplication, bad naming, magic numbers,
oversized classes, dead code). Respond ONLY with a JSON array of the form:
[{{"smell_type": str, "location": str, "severity": "low|medium|high", "refactor": str}}, ...]
Limit yourself to the 15 most important items. Do not include any text outside the JSON."""


def _run_python(code: str) -> list[dict]:
    raw_smells = detect_all_smells(code)
    if not raw_smells:
        return []
    try:
        refined = generate_json(str(raw_smells), REFINE_SYSTEM_PROMPT)
        if isinstance(refined, list) and len(refined) == len(raw_smells):
            return refined
        logger.warning("CodeSmell: LLM output length mismatch, using raw heuristics")
    except (OllamaUnavailableError, ValueError) as exc:
        logger.warning(f"CodeSmell: LLM refinement unavailable, using raw heuristics ({exc})")
    return raw_smells


def _run_generic(code: str, language: str) -> list[dict]:
    system = GENERIC_SYSTEM_PROMPT.format(language=describe_language(language))
    try:
        result = generate_json(code, system)
        return result if isinstance(result, list) else []
    except (OllamaUnavailableError, ValueError) as exc:
        logger.warning(f"CodeSmell: LLM detection unavailable for {language} ({exc})")
        return []


def run(code: str, language: str = "python") -> list[dict]:
    if language == "python":
        return _run_python(code)
    return _run_generic(code, language)
