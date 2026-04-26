from __future__ import annotations

from .client import DockgeClient
from .config import Config


def make_client(require_token: bool = True) -> tuple[Config, DockgeClient]:
    cfg = Config.load()
    token = cfg.token if require_token else cfg.token
    return cfg, DockgeClient(cfg.url or "", token=token, verify_tls=cfg.verify_tls, endpoint=cfg.endpoint)

