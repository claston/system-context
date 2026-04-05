from pathlib import Path


def test_render_staging_workflow_uses_render_secrets() -> None:
    workflow_path = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "deploy-render-staging.yml"
    )
    assert workflow_path.exists(), "deploy-render-staging.yml should exist"

    content = workflow_path.read_text(encoding="utf-8")
    assert "environment: staging" in content
    assert "vars.RENDER_DEPLOY_ENABLED == 'true'" in content
    assert "workflow_run:" in content
    assert "- Deploy Staging" in content
    assert "github.event.workflow_run.conclusion == 'success'" in content
    assert "${{ secrets.RENDER_API_KEY }}" in content
    assert "${{ secrets.RENDER_STAGING_SERVICE_ID }}" in content
    assert "Skipping Render deploy because RENDER_API_KEY or RENDER_STAGING_SERVICE_ID is not configured." in content
    assert "curl -fsS -X POST" in content
