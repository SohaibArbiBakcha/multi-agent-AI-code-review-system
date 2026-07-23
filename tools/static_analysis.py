"""Wrappers around the static-analysis CLIs/libraries used by the agents.

Pylint and Bandit are invoked as subprocesses with JSON output (they don't
expose a stable importable API); Radon is used as a library since its
programmatic API is stable and avoids a subprocess round-trip.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from radon.complexity import cc_visit
from radon.metrics import h_visit, mi_visit
from radon.raw import analyze as radon_raw


def _write_temp(code: str) -> Path:
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    )
    tmp.write(code)
    tmp.close()
    return Path(tmp.name)


def run_pylint(code: str) -> list[dict]:
    """Return pylint findings as a list of {line, symbol, message, type}."""
    path = _write_temp(code)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pylint", "--output-format=json", str(path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if not result.stdout.strip():
            return []
        raw = json.loads(result.stdout)
        return [
            {
                "line": item.get("line"),
                "symbol": item.get("symbol"),
                "message": item.get("message"),
                "type": item.get("type"),
            }
            for item in raw
        ]
    except (json.JSONDecodeError, subprocess.TimeoutExpired):
        return []
    finally:
        path.unlink(missing_ok=True)


def run_bandit(code: str) -> list[dict]:
    """Return bandit findings as a list of {line, severity, confidence, issue}."""
    path = _write_temp(code)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "bandit", "-f", "json", "-q", str(path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if not result.stdout.strip():
            return []
        raw = json.loads(result.stdout)
        return [
            {
                "line": item.get("line_number"),
                "severity": item.get("issue_severity"),
                "confidence": item.get("issue_confidence"),
                "issue": item.get("issue_text"),
                "rule": item.get("test_id"),
            }
            for item in raw.get("results", [])
        ]
    except (json.JSONDecodeError, subprocess.TimeoutExpired):
        return []
    finally:
        path.unlink(missing_ok=True)


def run_radon(code: str) -> dict:
    """Return complexity, maintainability index and Halstead metrics."""
    try:
        blocks = cc_visit(code)
        cyclomatic = [
            {"name": b.name, "complexity": b.complexity, "lineno": b.lineno}
            for b in blocks
        ]
        avg_cc = (
            sum(b["complexity"] for b in cyclomatic) / len(cyclomatic)
            if cyclomatic
            else 0.0
        )
        mi = mi_visit(code, multi=True)
        halstead = h_visit(code).total._asdict()
        raw = radon_raw(code)
        return {
            "cyclomatic_avg": round(avg_cc, 2),
            "cyclomatic_blocks": cyclomatic,
            "maintainability_index": round(mi, 2),
            "halstead": halstead,
            "loc": raw.loc,
            "sloc": raw.sloc,
        }
    except SyntaxError as exc:
        return {"error": f"SyntaxError: {exc}"}
