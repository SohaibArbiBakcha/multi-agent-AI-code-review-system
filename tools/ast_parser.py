"""AST-based structural analysis: function extraction and code-smell heuristics.

Radon and Pylint already cover complexity and most style rules, so this
module focuses on the smells that need a structural (not line-based) view:
long functions, duplicated blocks, god classes, magic numbers and dead code.
"""
import ast
import difflib
import keyword
import re

LONG_FUNCTION_LINES = 40
GOD_CLASS_METHODS = 12
DUPLICATE_SIMILARITY = 0.85
MAGIC_NUMBER_ALLOWLIST = {-1, 0, 1, 2, 100}


def extract_functions(code: str) -> list[dict]:
    """Return one entry per top-level/nested function: name, args, line span."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    functions = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end_line = getattr(node, "end_lineno", node.lineno)
            functions.append(
                {
                    "name": node.name,
                    "args": [a.arg for a in node.args.args],
                    "lineno": node.lineno,
                    "end_lineno": end_line,
                    "length": end_line - node.lineno + 1,
                    "is_async": isinstance(node, ast.AsyncFunctionDef),
                    "docstring": ast.get_docstring(node),
                }
            )
    return functions


def detect_long_functions(code: str) -> list[dict]:
    return [
        {
            "smell_type": "long_function",
            "location": f"{f['name']} (line {f['lineno']})",
            "severity": "high" if f["length"] > 2 * LONG_FUNCTION_LINES else "medium",
            "refactor": "Split this function into smaller, single-purpose helpers.",
        }
        for f in extract_functions(code)
        if f["length"] > LONG_FUNCTION_LINES
    ]


def detect_god_classes(code: str) -> list[dict]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    smells = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
            if len(methods) > GOD_CLASS_METHODS:
                smells.append(
                    {
                        "smell_type": "god_class",
                        "location": f"{node.name} (line {node.lineno})",
                        "severity": "high",
                        "refactor": "Split responsibilities across smaller, focused classes.",
                    }
                )
    return smells


def detect_magic_numbers(code: str) -> list[dict]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    smells = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            if node.value not in MAGIC_NUMBER_ALLOWLIST:
                smells.append(
                    {
                        "smell_type": "magic_number",
                        "location": f"line {getattr(node, 'lineno', '?')}",
                        "severity": "low",
                        "refactor": f"Replace literal {node.value} with a named constant.",
                    }
                )
    return smells


def detect_duplicate_blocks(code: str) -> list[dict]:
    """Naive duplicate detection: compare functions pairwise via difflib."""
    functions = extract_functions(code)
    lines = code.splitlines()
    bodies = {
        f["name"]: "\n".join(lines[f["lineno"] - 1 : f["end_lineno"]])
        for f in functions
    }
    smells = []
    seen = set()
    names = list(bodies)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            pair = frozenset((a, b))
            if pair in seen:
                continue
            ratio = difflib.SequenceMatcher(None, bodies[a], bodies[b]).ratio()
            if ratio >= DUPLICATE_SIMILARITY:
                seen.add(pair)
                smells.append(
                    {
                        "smell_type": "duplicate_code",
                        "location": f"{a} / {b}",
                        "severity": "medium",
                        "refactor": "Extract the shared logic into a common helper function.",
                    }
                )
    return smells


def detect_bad_naming(code: str) -> list[dict]:
    smells = []
    for f in extract_functions(code):
        if f["name"].startswith("__") and f["name"].endswith("__"):
            continue
        if not re.match(r"^[a-z_][a-z0-9_]*$", f["name"]):
            smells.append(
                {
                    "smell_type": "naming_convention",
                    "location": f"{f['name']} (line {f['lineno']})",
                    "severity": "low",
                    "refactor": "Use snake_case for function names (PEP 8).",
                }
            )
        for arg in f["args"]:
            if len(arg) == 1 and arg not in ("_",) and not keyword.iskeyword(arg):
                smells.append(
                    {
                        "smell_type": "naming_convention",
                        "location": f"argument '{arg}' in {f['name']} (line {f['lineno']})",
                        "severity": "low",
                        "refactor": "Use a descriptive parameter name instead of a single letter.",
                    }
                )
    return smells


def detect_all_smells(code: str) -> list[dict]:
    return (
        detect_long_functions(code)
        + detect_god_classes(code)
        + detect_magic_numbers(code)
        + detect_duplicate_blocks(code)
        + detect_bad_naming(code)
    )
