import subprocess
import sys
from pathlib import Path


def test_mcp_smoke_script_runs_successfully() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "mcp_smoke_check.py"

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "MCP smoke checks passed" in (result.stdout + result.stderr)
