"""Programming language detection.

Extension is the primary signal (reliable, instant). A handful of
well-known extensionless filenames (Dockerfile, Makefile, ...) are matched
next. When neither matches, content heuristics act as a fallback so
upload still works for pasted/renamed snippets. If even that fails,
detection honestly returns "unknown" rather than guessing — see
`describe_language()` for how callers should phrase that case to the LLM.
"""
import re

EXTENSION_MAP = {
    "py": "python", "pyw": "python",
    "js": "javascript", "jsx": "javascript", "mjs": "javascript", "cjs": "javascript",
    "ts": "typescript", "tsx": "typescript",
    "java": "java",
    "c": "c", "h": "c",
    "cpp": "cpp", "cc": "cpp", "cxx": "cpp", "hpp": "cpp", "hxx": "cpp",
    "cs": "csharp",
    "go": "go",
    "rb": "ruby",
    "php": "php",
    "rs": "rust",
    "swift": "swift",
    "kt": "kotlin", "kts": "kotlin",
    "scala": "scala",
    "sh": "bash", "bash": "bash", "zsh": "bash",
    "ps1": "powershell",
    "sql": "sql",
    "html": "html", "htm": "html",
    "css": "css", "scss": "scss", "less": "less",
    "r": "r",
    "m": "objective-c", "mm": "objective-c",
    "pl": "perl", "pm": "perl",
    "lua": "lua",
    "dart": "dart",
    "hs": "haskell", "lhs": "haskell",
    "ex": "elixir", "exs": "elixir",
    "erl": "erlang", "hrl": "erlang",
    "clj": "clojure", "cljs": "clojure", "cljc": "clojure",
    "ml": "ocaml", "mli": "ocaml",
    "fs": "fsharp", "fsx": "fsharp",
    "jl": "julia",
    "zig": "zig",
    "nim": "nim",
    "cr": "crystal",
    "ex4": "mql", "mq4": "mql", "mq5": "mql",
    "f90": "fortran", "f95": "fortran", "f": "fortran",
    "pas": "pascal", "pp": "pascal",
    "vb": "vbnet", "vbs": "vbscript",
    "groovy": "groovy", "gradle": "groovy",
    "coffee": "coffeescript",
    "elm": "elm",
    "vue": "vue",
    "d": "d",
    "asm": "assembly", "s": "assembly",
    "yaml": "yaml", "yml": "yaml",
    "json": "json",
    "toml": "toml",
    "xml": "xml",
    "md": "markdown",
    "proto": "protobuf",
    "tf": "terraform",
    "sol": "solidity",
    "cob": "cobol", "cbl": "cobol",
}

# Well-known filenames without a useful extension.
FILENAME_MAP = {
    "dockerfile": "dockerfile",
    "makefile": "makefile",
    "gnumakefile": "makefile",
    "rakefile": "ruby",
    "gemfile": "ruby",
    "vagrantfile": "ruby",
    "cmakelists.txt": "cmake",
}

# Order matters: more specific/distinctive patterns first.
CONTENT_HEURISTICS = [
    ("python", re.compile(r"^\s*def\s+\w+\s*\(.*\):|^\s*import\s+\w+|^\s*from\s+\w+\s+import", re.MULTILINE)),
    ("java", re.compile(r"\bpublic\s+(static\s+)?class\b|\bSystem\.out\.println\b")),
    ("csharp", re.compile(r"\bnamespace\s+\w+|\bConsole\.WriteLine\b")),
    ("cpp", re.compile(r"#include\s*<\w+>|\bstd::\w+")),
    ("c", re.compile(r"#include\s*<stdio\.h>|\bprintf\s*\(")),
    ("go", re.compile(r"^\s*package\s+\w+|\bfunc\s+\w+\s*\(", re.MULTILINE)),
    ("rust", re.compile(r"\bfn\s+\w+\s*\(|\blet\s+mut\b")),
    ("php", re.compile(r"<\?php")),
    # More specific than the generic "def ... end" Ruby pattern below, so it
    # must be checked first or Elixir source gets misdetected as Ruby.
    ("elixir", re.compile(r"\bdefmodule\s+\w+")),
    ("clojure", re.compile(r"\(defn\s+\w+|\(ns\s+\w+")),
    ("haskell", re.compile(r"^\s*module\s+\w+\s+where|::\s*\w+\s*->", re.MULTILINE)),
    ("ruby", re.compile(r"\bdef\s+\w+.*\bend\b|\brequire\s+['\"]", re.DOTALL)),
    ("typescript", re.compile(r"\binterface\s+\w+|:\s*(string|number|boolean)\b")),
    ("javascript", re.compile(r"\bfunction\s+\w*\s*\(|=>\s*\{|\bconst\s+\w+\s*=")),
    ("html", re.compile(r"<!DOCTYPE html>|<html[\s>]", re.IGNORECASE)),
    ("sql", re.compile(r"\bSELECT\b.+\bFROM\b|\bCREATE\s+TABLE\b", re.IGNORECASE)),
    ("julia", re.compile(r"^\s*function\s+\w+.*\bend\b|\busing\s+\w+", re.MULTILINE)),
    ("kotlin", re.compile(r"\bfun\s+\w+\s*\(|\bval\s+\w+\s*[:=]")),
]


def detect_language(filename: str, code: str = "") -> str:
    """Best-effort language name (lowercase) from filename, falling back to content."""
    base = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].lower()
    if base in FILENAME_MAP:
        return FILENAME_MAP[base]

    ext = base.rsplit(".", 1)[-1] if "." in base else ""
    if ext in EXTENSION_MAP:
        return EXTENSION_MAP[ext]

    for language, pattern in CONTENT_HEURISTICS:
        if pattern.search(code):
            return language

    return "unknown"


def is_fully_supported(language: str) -> bool:
    """True if the language has dedicated static-analysis tooling (Pylint/Bandit/Radon/ast).

    Other languages still get a full LLM-driven analysis (see agents/*), just
    without the deterministic static-analysis layer that only exists for Python.
    """
    return language == "python"


def describe_language(language: str) -> str:
    """Phrase used to slot a detected language into an LLM prompt.

    Detection can legitimately fail ("unknown") for languages outside the
    extension map and content heuristics (e.g. COBOL, Fortran variants,
    esoteric/DSLs). In that case, naming the language "unknown" to the model
    verbatim ("you are an expert in unknown") measurably degrades output
    quality — so instead the model is asked to identify the language itself
    from the code before analyzing it.
    """
    if language == "unknown":
        return "the programming language used in the provided code (identify it first from the code itself)"
    return language
