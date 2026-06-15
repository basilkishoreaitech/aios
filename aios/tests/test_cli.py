from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from cli import cli

def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Terminal Operator CLI" in result.output

@patch("httpx.post")
def test_cli_login_success(mock_post):
    mock_post.return_value = MagicMock(
        status_code=200,
        json=lambda: {"access_token": "test-access-token", "role": "admin", "display_name": "SRE Lead"}
    )
    
    runner = CliRunner()
    result = runner.invoke(cli, ["login", "--username", "admin", "--password", "aios-admin-2026"])
    assert result.exit_code == 0
    assert "Successfully authenticated" in result.output

@patch("httpx.post")
def test_cli_query(mock_post):
    mock_post.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "answer": "Connection pool limit reached.",
            "citations": [{"title": "DB Pool Runbook", "category": "runbook", "relevance": 0.88}],
            "confidence": 0.88,
            "source_breakdown": {"kb": 1, "db": 0, "web": 0}
        }
    )
    
    runner = CliRunner()
    result = runner.invoke(cli, ["query", "What caused the db latency?"])
    assert result.exit_code == 0
    assert "AIOS RESPONSE" in result.output
    assert "Connection pool limit reached" in result.output
