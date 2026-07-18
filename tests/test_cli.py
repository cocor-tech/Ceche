"""CLI integration tests — tests every command through Typer's CliRunner."""

from __future__ import annotations

from typer.testing import CliRunner

from ceche.interfaces.cli import app

runner = CliRunner()


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "ceche v" in result.stdout


def test_version_short() -> None:
    result = runner.invoke(app, ["-V"])
    assert result.exit_code == 0
    assert "ceche v" in result.stdout


def test_check_help() -> None:
    result = runner.invoke(app, ["check", "--help"])
    assert result.exit_code == 0
    assert "check" in result.stdout


def test_bulk_help() -> None:
    result = runner.invoke(app, ["bulk", "--help"])
    assert result.exit_code == 0
    assert "bulk" in result.stdout


def test_start_help() -> None:
    result = runner.invoke(app, ["start", "--help"])
    assert result.exit_code == 0
    assert "start" in result.stdout


def test_bulk_no_args_shows_error() -> None:
    result = runner.invoke(app, ["bulk"])
    assert result.exit_code != 0


def test_stats_command() -> None:
    result = runner.invoke(app, ["stats"])
    assert result.exit_code == 0
    assert "Statistics" in result.stdout


def test_keys_command() -> None:
    result = runner.invoke(app, ["keys"])
    assert result.exit_code == 0


def test_cache_command() -> None:
    result = runner.invoke(app, ["cache"])
    assert result.exit_code == 0


def test_version_command() -> None:
    result = runner.invoke(app, ["version", "check"])
    assert result.exit_code == 0
    assert "Current:" in result.stdout


def test_demo_command() -> None:
    result = runner.invoke(app, ["demo"])
    assert result.exit_code == 0


def test_config_command() -> None:
    result = runner.invoke(app, ["config", "--format", "json"])
    assert result.exit_code == 0


def test_history_command() -> None:
    result = runner.invoke(app, ["history"])
    assert result.exit_code == 0


def test_profiles_command() -> None:
    result = runner.invoke(app, ["profiles"])
    assert result.exit_code == 0


def test_python_m_ceche() -> None:
    """python -m ceche --version should work."""
    import subprocess
    import sys
    result = subprocess.run(
        [sys.executable, "-m", "ceche", "--version"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "ceche v" in result.stdout
