from __future__ import annotations

import getpass
import os
import sys

import typer
from rich.console import Console

from dockgectl.command_help import print_help_if_no_subcommand
from dockgectl.client import DockgeClient
from dockgectl.config import Config, normalize_base_url
from dockgectl.errors import DockgectlError
from dockgectl.output import dump

app = typer.Typer(help="Authenticate to Dockge")
console = Console()


@app.callback(invoke_without_command=True)
def auth_callback(ctx: typer.Context):
    print_help_if_no_subcommand(ctx)


@app.command("login")
def login(
    username: str = typer.Option(None, "--username", "-u", help="Dockge username"),
    url: str = typer.Option(None, "--url", help="Dockge base URL for the active profile"),
    totp: str = typer.Option(None, "--totp", help="2FA token"),
    password_stdin: bool = typer.Option(False, "--password-stdin", help="Read password from stdin"),
    save_password: bool = typer.Option(False, "--save-password", help="Save password in the active profile config"),
    use_saved_password: bool = typer.Option(True, "--use-saved-password/--no-use-saved-password", help="Reuse saved password when available"),
):
    cfg = Config.load()
    if url:
        cfg.url = normalize_base_url(url)
    if not cfg.url:
        cfg.url = normalize_base_url(typer.prompt("Dockge URL"))
    username = username or cfg.username or os.environ.get("DOCKGECTL_USERNAME") or typer.prompt("Username")

    if password_stdin:
        password = sys.stdin.read().strip("\n")
    elif os.environ.get("DOCKGECTL_PASSWORD"):
        password = os.environ["DOCKGECTL_PASSWORD"]
    elif use_saved_password and cfg.password:
        password = cfg.password
    else:
        password = getpass.getpass("Password: ")

    client = DockgeClient(cfg.url, verify_tls=cfg.verify_tls, endpoint=cfg.endpoint)
    token = client.login(username, password, token=totp)["token"]
    cfg.username = username
    cfg.token = token
    if save_password:
        cfg.password = password
    cfg.save()
    console.print(f"[green]Login OK[/green] profile={cfg.current_profile} saved_password={bool(cfg.password)}")
    client.disconnect()


@app.command("status")
def status(output: str = typer.Option("table", "--output", "-o", help="table|json|yaml")):
    cfg = Config.load()
    data = cfg.display()
    data["authenticated"] = False
    if cfg.token and cfg.url:
        client = DockgeClient(cfg.url, token=cfg.token, verify_tls=cfg.verify_tls, endpoint=cfg.endpoint)
        try:
            client.login_by_token()
            client.wait_for_info(timeout=1)
            data["authenticated"] = True
            data["info"] = client.info
        except DockgectlError as exc:
            data["auth_error"] = str(exc)
        finally:
            client.disconnect()
    dump(data, output)


@app.command("logout")
def logout(clear_password: bool = typer.Option(False, "--clear-password", help="Also remove saved password")):
    cfg = Config.load()
    cfg.token = None
    if clear_password:
        cfg.password = None
    cfg.save()
    console.print(f"Logged out locally from profile={cfg.current_profile}")


@app.command("forget-password")
def forget_password():
    cfg = Config.load()
    cfg.password = None
    cfg.save()
    console.print(f"Removed saved password for profile={cfg.current_profile}")
