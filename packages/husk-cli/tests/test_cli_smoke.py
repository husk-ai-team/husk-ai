from __future__ import annotations

from click.testing import CliRunner

from husk import __version__
from husk.cli import main


def test_version() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_help_lists_commands() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    for cmd in ["start", "list", "doctor", "demo", "clean"]:
        assert cmd in result.output
