"""Global quality score — see report Chapter 2.6 for the formula rationale."""


def compute_score(bugs: list[dict], smells: list[dict], complexity: dict) -> dict:
    critical_bugs = sum(1 for b in bugs if b.get("type") == "security")
    bug_penalty = min(100, len(bugs) * 10 + critical_bugs * 25)

    high_smells = sum(1 for s in smells if s.get("severity") == "high")
    smell_penalty = min(100, len(smells) * 5 + high_smells * 15)

    maintainability = complexity.get("maintainability_index", 50) if isinstance(complexity, dict) else 50
    cyclomatic_avg = complexity.get("cyclomatic_avg", 10) if isinstance(complexity, dict) else 10
    testability = 100 if cyclomatic_avg <= 8 else 50

    value = (
        (100 - bug_penalty) * 0.30
        + (100 - smell_penalty) * 0.25
        + maintainability * 0.25
        + testability * 0.20
    )
    value = round(max(0, min(100, value)), 1)

    if value >= 90:
        grade = "A"
    elif value >= 75:
        grade = "B"
    elif value >= 60:
        grade = "C"
    elif value >= 40:
        grade = "D"
    else:
        grade = "F"

    return {"value": value, "grade": grade}
