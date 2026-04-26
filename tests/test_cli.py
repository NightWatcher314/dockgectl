from typer.testing import CliRunner

from dockgectl.cli import app


def test_help():
    res = CliRunner().invoke(app, ["--help"])
    assert res.exit_code == 0
    assert "Dockge CLI" in res.output


def test_config_get_uses_temp_config(tmp_path, monkeypatch):
    cfg_path = tmp_path / "config.json"
    monkeypatch.setenv("DOCKGECTL_CONFIG", str(cfg_path))
    res = CliRunner().invoke(app, ["config", "get"])
    assert res.exit_code == 0
    assert "current_profile" in res.output

