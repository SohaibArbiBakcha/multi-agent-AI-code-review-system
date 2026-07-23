from tools.ast_parser import (
    detect_bad_naming,
    detect_duplicate_blocks,
    detect_long_functions,
    detect_magic_numbers,
    extract_functions,
)

LONG_FUNC = "def f():\n" + "\n".join(f"    x = {i}" for i in range(50)) + "\n    return x\n"


def test_extract_functions_finds_names_and_args():
    code = "def add(a, b):\n    return a + b\n"
    functions = extract_functions(code)
    assert len(functions) == 1
    assert functions[0]["name"] == "add"
    assert functions[0]["args"] == ["a", "b"]


def test_extract_functions_on_empty_module():
    assert extract_functions("x = 1\n") == []


def test_detect_long_functions_flags_oversized_body():
    smells = detect_long_functions(LONG_FUNC)
    assert len(smells) == 1
    assert smells[0]["smell_type"] == "long_function"


def test_detect_long_functions_ignores_short_body():
    assert detect_long_functions("def f():\n    return 1\n") == []


def test_detect_magic_numbers_flags_uncommon_literal():
    smells = detect_magic_numbers("def f():\n    return 42\n")
    assert any(s["smell_type"] == "magic_number" for s in smells)


def test_detect_magic_numbers_ignores_allowlisted_values():
    smells = detect_magic_numbers("def f():\n    return 0 + 1 - 1\n")
    assert smells == []


def test_detect_duplicate_blocks_flags_near_identical_functions():
    code = (
        "def a():\n    x = 1\n    y = 2\n    return x + y\n\n"
        "def b():\n    x = 1\n    y = 2\n    return x + y\n"
    )
    smells = detect_duplicate_blocks(code)
    assert len(smells) == 1
    assert smells[0]["smell_type"] == "duplicate_code"


def test_detect_bad_naming_flags_single_letter_argument():
    smells = detect_bad_naming("def f(x):\n    return x\n")
    assert any("argument" in s["location"] for s in smells)


def test_syntax_error_returns_empty_lists_not_raises():
    broken = "def f(:\n    pass\n"
    assert extract_functions(broken) == []
    assert detect_long_functions(broken) == []
