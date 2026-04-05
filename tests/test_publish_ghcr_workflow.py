from pathlib import Path


def test_publish_ghcr_workflow_has_required_steps() -> None:
    workflow_path = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "publish-ghcr.yml"
    )
    assert workflow_path.exists(), "publish-ghcr.yml should exist"

    content = workflow_path.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in content
    assert "packages: write" in content
    assert "registry: ghcr.io" in content
    assert "docker/login-action@" in content
    assert "docker/build-push-action@" in content
    assert "${{ github.repository_owner }}" in content
