from tools.language_detect import describe_language, detect_language, is_fully_supported


def test_detects_python_by_extension():
    assert detect_language("solution.py", "") == "python"


def test_detects_javascript_by_extension():
    assert detect_language("app.js", "") == "javascript"


def test_detects_java_by_extension():
    assert detect_language("Main.java", "") == "java"


def test_falls_back_to_content_when_extension_unknown():
    code = "public class Main {\n    public static void main(String[] a) {}\n}\n"
    assert detect_language("snippet.txt", code) == "java"


def test_falls_back_to_content_for_python_without_extension():
    code = "import os\n\ndef main():\n    pass\n"
    assert detect_language("snippet", code) == "python"


def test_returns_unknown_when_nothing_matches():
    assert detect_language("data.xyz", "some random unrecognized content 123") == "unknown"


def test_is_fully_supported_only_for_python():
    assert is_fully_supported("python") is True
    assert is_fully_supported("javascript") is False
    assert is_fully_supported("unknown") is False


def test_detects_extensionless_well_known_filenames():
    assert detect_language("Dockerfile", "") == "dockerfile"
    assert detect_language("Makefile", "") == "makefile"
    assert detect_language("path/to/Rakefile", "") == "ruby"


def test_detects_less_common_languages_by_extension():
    assert detect_language("Main.hs", "") == "haskell"
    assert detect_language("lib.ex", "") == "elixir"
    assert detect_language("app.clj", "") == "clojure"
    assert detect_language("script.zig", "") == "zig"
    assert detect_language("data.jl", "") == "julia"


def test_elixir_content_is_not_misdetected_as_ruby():
    code = "defmodule MyApp do\n  def hello, do: :world\nend\n"
    assert detect_language("weird_file", code) == "elixir"


def test_ruby_content_still_detected_without_defmodule():
    code = "def hello\n  puts 'hi'\nend\n"
    assert detect_language("weird_ruby", code) == "ruby"


def test_describe_language_passes_through_known_language():
    assert describe_language("rust") == "rust"


def test_describe_language_asks_model_to_self_identify_when_unknown():
    phrase = describe_language("unknown")
    assert "unknown" not in phrase
    assert "identify" in phrase
