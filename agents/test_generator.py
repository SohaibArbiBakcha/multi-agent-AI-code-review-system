"""Agent 4 — TestGeneratorAgent.

For Python, function signatures are extracted via AST and every generated
snippet is validated with ast.parse() before being kept. For other
languages there is no cheap way to validate syntax here, so the LLM is
asked to use the language's idiomatic test framework and the output only
gets a lightweight brace-balance sanity check.
"""
import ast
import re

from loguru import logger

from llm.ollama_client import OllamaUnavailableError, generate_text
from tools.ast_parser import extract_functions
from tools.language_detect import describe_language

PYTHON_SYSTEM_PROMPT = """You are a Python unit testing expert using pytest.
You are given a file's source code and the list of its functions.
Generate a complete pytest test file that imports the necessary functions
and covers, for EACH function, at minimum:
- a nominal case (happy path)
- an edge case
- an error case if relevant

Respond ONLY with valid Python code (the test file's content), with no
explanation and no markdown block."""

GENERIC_SYSTEM_PROMPT = """You are a unit testing expert. The source code
below is written in {language}. Generate a complete test file, using the
idiomatic test framework for this language ({framework} if applicable,
otherwise this language's standard framework). Cover, for each public
function/method, at minimum a nominal case, an edge case, and an error
case if relevant.

Respond ONLY with the test file's content, with no explanation and no
markdown block."""

TEST_FRAMEWORKS = {
    "javascript": "Jest", "typescript": "Jest", "java": "JUnit 5",
    "csharp": "xUnit", "go": "package testing", "rust": "#[test] (built-in)",
    "ruby": "RSpec", "php": "PHPUnit", "cpp": "Catch2", "c": "Unity",
    "swift": "XCTest", "kotlin": "JUnit 5", "scala": "ScalaTest",
}

DEFAULT_FRAMEWORK_LABEL = "the standard test framework"


_FENCE_RE = re.compile(r"```(?:\w+)?\n(.*?)```", re.DOTALL)


def _strip_fences(text: str) -> str:
    """Extract the content of a fenced code block wherever it appears.

    Despite an explicit "no explanation, no markdown" instruction in the
    prompt, the model frequently prepends a sentence of prose before the
    fence anyway (observed live: "Voici un exemple de fichier de tests
    pytest..." followed by the actual ```python block). A prefix check
    like `text.startswith("```")` misses that case entirely and lets the
    prose leak into the "generated test", which then fails ast.parse().
    Searching for the fence anywhere in the text, not just at position 0,
    fixes this without needing the model to comply perfectly.
    """
    text = text.strip()
    match = _FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    return text


def _braces_balanced(text: str) -> bool:
    pairs = {"(": ")", "{": "}", "[": "]"}
    stack = []
    for ch in text:
        if ch in pairs:
            stack.append(pairs[ch])
        elif ch in pairs.values():
            if not stack or stack.pop() != ch:
                return False
    return not stack


def _run_python(code: str, module_name: str) -> str:
    functions = extract_functions(code)
    if not functions:
        return "# No function detected: no tests generated.\n"

    prompt = (
        f"Module name to import: {module_name}\n\n"
        f"Source code:\n{code}\n\n"
        f"Functions to cover: {[f['name'] for f in functions]}"
    )
    try:
        raw = generate_text(prompt, PYTHON_SYSTEM_PROMPT)
    except OllamaUnavailableError as exc:
        logger.warning(f"TestGenerator: LLM unavailable, emitting stub tests ({exc})")
        stub = "\n".join(
            f"def test_{f['name']}_todo():\n    pass  # LLM unavailable: fill in this test manually\n"
            for f in functions
        )
        return f"import pytest\nfrom {module_name} import *\n\n{stub}"

    test_code = _strip_fences(raw)
    try:
        ast.parse(test_code)
    except SyntaxError as exc:
        logger.warning(f"TestGenerator: generated tests invalid ({exc}), discarding")
        return f"# Invalid generation, check manually.\n# Error: {exc}\n"
    return test_code


def _run_generic(code: str, language: str, module_name: str) -> str:
    framework = TEST_FRAMEWORKS.get(language, DEFAULT_FRAMEWORK_LABEL)
    system = GENERIC_SYSTEM_PROMPT.format(language=describe_language(language), framework=framework)
    prompt = f"Module/file name: {module_name}\n\nSource code:\n{code}"
    try:
        raw = generate_text(prompt, system)
    except OllamaUnavailableError as exc:
        logger.warning(f"TestGenerator: LLM unavailable for {language} ({exc})")
        return f"// LLM unavailable: no tests generated for {language}.\n"

    test_code = _strip_fences(raw)
    if not _braces_balanced(test_code):
        logger.warning(f"TestGenerator: generated {language} tests look malformed (unbalanced braces), discarding")
        return f"// Invalid generation (unbalanced braces), check manually.\n"
    return test_code


def run(code: str, module_name: str = "solution", language: str = "python") -> str:
    if language == "python":
        return _run_python(code, module_name)
    return _run_generic(code, language, module_name)
