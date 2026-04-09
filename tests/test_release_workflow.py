from pathlib import Path


def test_release_workflow_has_versioned_publish_and_release_steps() -> None:
    workflow_path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "release.yml"
    assert workflow_path.exists(), "release.yml should exist"

    content = workflow_path.read_text(encoding="utf-8")
    assert "name: Release | Versioned Publish" in content
    assert "push:" in content
    assert "- \"v*.*.*\"" in content
    assert "workflow_dispatch:" in content
    assert "inputs:" in content
    assert "version:" in content
    assert "contents: write" in content
    assert "packages: write" in content
    assert "ruff check ." in content
    assert "pytest -q" in content
    assert "python scripts/mcp_smoke_check.py" in content
    assert "docker/build-push-action@" in content
    assert "build-args:" in content
    assert "APP_RELEASE=${{ env.RELEASE_VERSION }}" in content
    assert "softprops/action-gh-release@" in content
    assert "ghcr.io/${{ github.repository_owner }}/system-context:${{ env.RELEASE_VERSION }}" in content
