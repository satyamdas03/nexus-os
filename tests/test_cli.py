"""Tests for the CLI entry points."""

from __future__ import annotations

from typer.testing import CliRunner

from nexus_os.cli import app

runner = CliRunner()


def test_roster_load_cli():
    result = runner.invoke(app, ["roster", "load"])
    assert result.exit_code == 0
    assert "233 agents" in result.output


def test_roster_list_cli():
    result = runner.invoke(app, ["roster", "list", "--division", "testing"])
    assert result.exit_code == 0
    assert "Evidence Collector" in result.output


def test_roster_info_cli():
    result = runner.invoke(app, ["roster", "info", "engineering-frontend-developer"])
    assert result.exit_code == 0
    assert "Frontend Developer" in result.output


def test_init_cli(temp_repo):
    result = runner.invoke(app, ["init", "--repo", str(temp_repo)])
    assert result.exit_code == 0
    assert "Initialized NEXUS workspace" in result.output
    assert (temp_repo / ".nexus-os" / "state.json").exists()


def test_micro_cli_dry_run(temp_repo):
    result = runner.invoke(
        app,
        [
            "micro",
            "--repo",
            str(temp_repo),
            "--goal",
            "test",
            "--agents",
            "engineering-frontend-developer",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "completed" in result.output
