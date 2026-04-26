from __future__ import annotations

import sys

import typer
from rich.console import Console

from dockgectl import __version__
from dockgectl.commands import auth, config_cmd, network, service, stack
from dockgectl.context import make_client
from dockgectl.errors import DockgectlError

app = typer.Typer(help="Dockge CLI")
app.add_typer(config_cmd.app, name="config")
app.add_typer(auth.app, name="auth")
app.add_typer(stack.app, name="stack")
app.add_typer(service.app, name="service")
app.add_typer(network.app, name="network")
console = Console(stderr=True)


@app.command()
def version():
    """Print dockgectl version."""
    typer.echo(__version__)


@app.command()
def doctor():
    """Check connectivity to the configured Dockge instance."""
    cfg, client = make_client(require_token=False)
    try:
        client.connect()
        client.wait_for_info(timeout=1)
        authenticated = False
        if cfg.token:
            try:
                client.login_by_token(cfg.token)
                authenticated = True
            except DockgectlError:
                authenticated = False
        elif client.logged_in:
            authenticated = True
        Console().print({
            "url": cfg.url,
            "profile": cfg.current_profile,
            "endpoint": cfg.endpoint,
            "connected": client.connected,
            "authenticated": authenticated,
            "need_setup": client.need_setup,
            "info": client.info,
        })
    finally:
        client.disconnect()


@app.command("composerize")
def composerize(docker_run_command: str):
    """Convert a docker run command to Compose YAML using Dockge."""
    _cfg, client = make_client()
    try:
        typer.echo(client.composerize(docker_run_command))
    finally:
        client.disconnect()


def main():
    try:
        app()
    except DockgectlError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
