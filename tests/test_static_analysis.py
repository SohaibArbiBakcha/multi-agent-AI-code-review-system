from tools.static_analysis import run_radon


def test_run_radon_reports_metrics_for_valid_code():
    code = "def add(a, b):\n    return a + b\n"
    metrics = run_radon(code)
    assert "cyclomatic_avg" in metrics
    assert "maintainability_index" in metrics
    assert metrics["cyclomatic_blocks"][0]["name"] == "add"


def test_run_radon_reports_error_on_syntax_error():
    metrics = run_radon("def f(:\n")
    assert "error" in metrics
