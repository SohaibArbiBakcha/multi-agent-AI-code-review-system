"""Agent 1 — BugHunterAgent.

For Python, runs Pylint + Bandit and asks the LLM to explain each raw
finding. For any other language (no equivalent static-analysis tooling
wired up), the LLM performs the detection itself in a single pass, since
Qwen2.5-Coder is multi-language. Falls back to the raw static-analysis
message (Python) or an empty list (other languages) if Ollama is
unreachable, so the pipeline degrades gracefully instead of failing.

The per-finding explanation calls run concurrently (see MAX_WORKERS below).
Measured live against qwen2.5-coder:7b on an RTX 4060, a single explanation
call takes ~16s; a file with ~17 findings run sequentially took ~280s and
blew straight through the orchestrator's 120s per-agent timeout, silently
returning zero bugs on a file that pylint/bandit had flagged 17 times. A
thread pool brings that down to roughly (findings / MAX_WORKERS) * 16s.
"""
from concurrent.futures import ThreadPoolExecutor

from loguru import logger

from llm.ollama_client import OllamaUnavailableError, generate_json
from tools.language_detect import describe_language
from tools.static_analysis import run_bandit, run_pylint

MAX_WORKERS = 4
MAX_FINDINGS = 20

EXPLAIN_SYSTEM_PROMPT = """You are a Python code review expert explaining
issues to computer science students. For the given issue, respond
ONLY with a JSON object of the form:
{"line": <int>, "type": "bug|security|warning", "description": "<2-3 sentences in English explaining the problem>", "suggestion": "<concrete fix>"}
Do not include any text outside the JSON."""

GENERIC_SYSTEM_PROMPT = """You are a {language} code review expert explaining
issues to computer science students. Analyze the provided source code and
identify likely bugs and security flaws. Respond ONLY with a JSON array
of the form:
[{{"line": <int>, "type": "bug|security|warning", "description": "<2-3 sentences in English>", "suggestion": "<concrete fix>"}}, ...]
Limit yourself to the 15 most important issues. Do not include any text outside the JSON."""


def _explain(issue_line: int, raw_message: str, issue_type: str) -> dict:
    prompt = f"Ligne {issue_line} : {raw_message}"
    try:
        result = generate_json(prompt, EXPLAIN_SYSTEM_PROMPT)
        result.setdefault("line", issue_line)
        result.setdefault("type", issue_type)
        return result
    except (OllamaUnavailableError, ValueError) as exc:
        logger.warning(f"BugHunter: LLM explanation unavailable, using raw message ({exc})")
        return {
            "line": issue_line,
            "type": issue_type,
            "description": raw_message,
            "suggestion": "N/A (LLM unavailable)",
        }


def _run_python(code: str) -> list[dict]:
    raw_issues = [
        (item["line"], item["message"], "warning" if item["type"] in ("convention", "refactor") else "bug")
        for item in run_pylint(code)
    ] + [
        (item["line"], item["issue"], "security")
        for item in run_bandit(code)
    ]

    if len(raw_issues) > MAX_FINDINGS:
        logger.warning(f"BugHunter: {len(raw_issues)} findings exceeds cap, keeping first {MAX_FINDINGS}")
        raw_issues = raw_issues[:MAX_FINDINGS]

    if not raw_issues:
        return []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        return list(pool.map(lambda args: _explain(*args), raw_issues))


def _run_generic(code: str, language: str) -> list[dict]:
    system = GENERIC_SYSTEM_PROMPT.format(language=describe_language(language))
    try:
        result = generate_json(code, system)
        return result if isinstance(result, list) else []
    except (OllamaUnavailableError, ValueError) as exc:
        logger.warning(f"BugHunter: LLM detection unavailable for {language} ({exc})")
        return []


def run(code: str, language: str = "python") -> list[dict]:
    if language == "python":
        return _run_python(code)
    return _run_generic(code, language)
