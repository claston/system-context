from pathlib import Path


def test_staging_workflow_uses_environment_and_secrets() -> None:
    workflow_path = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "deploy-staging.yml"
    )
    assert workflow_path.exists(), "deploy-staging.yml should exist"

    content = workflow_path.read_text(encoding="utf-8")
    assert "name: Staging | Environment Validation" in content
    assert "concurrency:" in content
    assert "staging-validation-${{ github.ref }}" in content
    assert "environment: staging" in content
    assert "${{ secrets.STAGING_DATABASE_URL }}" in content
    assert "${{ secrets.STAGING_MCP_API_TOKEN }}" in content
    assert "python scripts/validate_environment.py" in content
    assert "python scripts/mcp_smoke_check.py" in content
