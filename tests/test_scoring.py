from orchestrator.scoring import compute_score


def test_perfect_code_scores_high_grade_a():
    score = compute_score(bugs=[], smells=[], complexity={"maintainability_index": 100, "cyclomatic_avg": 2})
    assert score["value"] == 100.0
    assert score["grade"] == "A"


def test_many_critical_bugs_yield_grade_f():
    bugs = [{"type": "security"}] * 10
    score = compute_score(bugs=bugs, smells=[], complexity={"maintainability_index": 0, "cyclomatic_avg": 20})
    assert score["grade"] == "F"


def test_score_is_clamped_between_0_and_100():
    bugs = [{"type": "security"}] * 50
    smells = [{"severity": "high"}] * 50
    score = compute_score(bugs=bugs, smells=smells, complexity={"maintainability_index": 0, "cyclomatic_avg": 30})
    assert 0 <= score["value"] <= 100


def test_missing_complexity_fields_use_safe_defaults():
    score = compute_score(bugs=[], smells=[], complexity={})
    assert 0 <= score["value"] <= 100
