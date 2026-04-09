from pathlib import Path


def test_ci_workflow_includes_mcp_smoke_gate() -> None:
    workflow_path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
    content = workflow_path.read_text(encoding="utf-8")

    assert "name: CI | Quality Gates" in content
    assert "lint-and-fast-tests:" in content
    assert "e2e-and-smoke:" in content
    assert "pytest -q -m \"not e2e and not smoke\"" in content
    assert "pytest -q -m \"e2e\"" in content
    assert "Run MCP smoke checks" in content
    assert "python scripts/mcp_smoke_check.py" in content
