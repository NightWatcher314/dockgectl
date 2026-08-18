import json

import typer
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


def test_stack_apply_help_exposes_structured_output():
    root = typer.main.get_command(app)
    apply = root.commands["stack"].commands["apply"]
    output = next(param for param in apply.params if param.name == "output")
    assert output.opts == ["--output", "-o"]


def test_stack_apply_rejects_invalid_output_before_connecting(tmp_path, monkeypatch):
    from dockgectl.commands import stack

    compose = tmp_path / "compose.yaml"
    compose.write_text("services: {}\n")
    monkeypatch.setattr(
        stack,
        "make_client",
        lambda: (_ for _ in ()).throw(AssertionError("must not connect")),
    )
    res = CliRunner().invoke(app, ["stack", "apply", "app", "-f", str(compose), "-o", "bad"])
    assert res.exit_code != 0
    assert not isinstance(res.exception, AssertionError)


def test_stack_apply_dry_run_emits_valid_json(tmp_path, monkeypatch):
    from dockgectl.commands import stack
    from dockgectl.errors import NotFoundError

    class Client:
        def get_stack(self, name, endpoint=None):
            raise NotFoundError(name)

        def disconnect(self):
            pass

    compose = tmp_path / "compose.yaml"
    compose.write_text("services: {}\n")
    monkeypatch.setattr(stack, "make_client", lambda: (None, Client()))

    res = CliRunner().invoke(
        app,
        ["stack", "apply", "app", "-f", str(compose), "--dry-run", "-o", "json"],
    )

    assert res.exit_code == 0
    assert json.loads(res.output)["name"] == "app"
