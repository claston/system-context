import pytest

from scripts.mcp_smoke_check import run_smoke_checks


@pytest.mark.smoke
def test_mcp_smoke_script_runs_successfully(capsys: pytest.CaptureFixture[str]) -> None:
    run_smoke_checks()
    output = capsys.readouterr().out
    assert "MCP smoke checks passed" in output
