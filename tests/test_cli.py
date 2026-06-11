from typer.testing import CliRunner

from dockgectl.cli import app


def test_help():
    res = CliRunner().invoke(app, ["--help"])
    assert res.exit_code == 0
    assert "Dockge CLI" in res.output


def test_missing_top_level_command_shows_help():
    res = CliRunner().invoke(app, [])
    assert res.exit_code == 0
    assert "Dockge CLI" in res.output
    assert "Missing command" not in res.output


def test_missing_command_group_subcommand_shows_help():
    res = CliRunner().invoke(app, ["stack"])
    assert res.exit_code == 0
    assert "Manage Dockge stacks" in res.output
    assert "Missing command" not in res.output


def test_agent_group_shows_help():
    res = CliRunner().invoke(app, ["agent"])
    assert res.exit_code == 0
    assert "Manage Dockge agent hosts" in res.output


def test_config_get_uses_temp_config(tmp_path, monkeypatch):
    cfg_path = tmp_path / "config.json"
    monkeypatch.setenv("DOCKGECTL_CONFIG", str(cfg_path))
    res = CliRunner().invoke(app, ["config", "get"])
    assert res.exit_code == 0
    assert "current_profile" in res.output


def test_invalid_output_format_fails_for_config_get(tmp_path, monkeypatch):
    cfg_path = tmp_path / "config.json"
    monkeypatch.setenv("DOCKGECTL_CONFIG", str(cfg_path))
    res = CliRunner().invoke(app, ["config", "get", "-o", "bad"])
    assert res.exit_code == 1
    assert "Unsupported output format" in str(res.exception)


def test_stack_logs_rejects_negative_tail():
    res = CliRunner().invoke(app, ["stack", "logs", "app", "--tail", "-1"])
    assert res.exit_code != 0
