import json

from dockgectl.config import Config


def test_migrates_single_profile_config(tmp_path, monkeypatch):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"url": "https://dockge.example.com", "token": "t", "username": "u", "verify_tls": False}))
    monkeypatch.setenv("DOCKGECTL_CONFIG", str(cfg_path))
    cfg = Config.load()
    assert cfg.current_profile == "default"
    assert cfg.url == "https://dockge.example.com"
    assert cfg.token == "t"
    assert cfg.username == "u"
    assert cfg.verify_tls is False


def test_profiles_save_and_switch(tmp_path, monkeypatch):
    cfg_path = tmp_path / "config.json"
    monkeypatch.setenv("DOCKGECTL_CONFIG", str(cfg_path))
    cfg = Config.load()
    cfg.add_profile("home", url="dockge.example.com", endpoint="remote.example.com", use=True)
    cfg.username = "admin"
    cfg.password = "secret"
    cfg.save()

    loaded = Config.load()
    assert loaded.current_profile == "home"
    assert loaded.url == "https://dockge.example.com"
    assert loaded.endpoint == "remote.example.com"
    assert loaded.username == "admin"
    assert loaded.password == "secret"
    assert loaded.display()["has_password"] is True


def test_environment_overrides_active_profile(tmp_path, monkeypatch):
    cfg_path = tmp_path / "config.json"
    monkeypatch.setenv("DOCKGECTL_CONFIG", str(cfg_path))
    monkeypatch.setenv("DOCKGECTL_URL", "dockge.local")
    monkeypatch.setenv("DOCKGECTL_TOKEN", "env-token")
    monkeypatch.setenv("DOCKGECTL_ENDPOINT", "agent.local")
    monkeypatch.setenv("DOCKGECTL_INSECURE", "1")
    cfg = Config.load()
    assert cfg.url == "https://dockge.local"
    assert cfg.token == "env-token"
    assert cfg.endpoint == "agent.local"
    assert cfg.verify_tls is False

