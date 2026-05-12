from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from dockgectl.command_help import print_help_if_no_subcommand
from dockgectl.client import status_name
from dockgectl.context import make_client
from dockgectl.errors import NotFoundError
from dockgectl.output import dump

app = typer.Typer(help="Manage Dockge stacks")
console = Console()


@app.callback(invoke_without_command=True)
def stack_callback(ctx: typer.Context):
    print_help_if_no_subcommand(ctx)


def _endpoint(value: str | None) -> str | None:
    return value


def _read_text(path: Path | None, default: str = "") -> str:
    if not path:
        return default
    return path.read_text()


def _stack_table(stacks: dict[str, Any]) -> Table:
    table = Table(title="Dockge stacks")
    for col in ["Name", "Status", "Managed", "Endpoint"]:
        table.add_column(col)
    for name, stack in sorted(stacks.items()):
        table.add_row(
            stack.get("name") or name,
            status_name(stack.get("status")),
            str(stack.get("isManagedByDockge", "")),
            stack.get("endpoint") or "",
        )
    return table


def _exists(client, name: str, endpoint: str | None) -> bool:
    try:
        client.get_stack(name, endpoint=endpoint)
        return True
    except NotFoundError:
        return False


@app.command("list")
def list_stacks(
    output: str = typer.Option("table", "--output", "-o", help="table|json|yaml"),
    endpoint: str = typer.Option(None, "--endpoint", help="Dockge agent endpoint, empty for main instance"),
):
    _cfg, client = make_client()
    try:
        stacks = client.list_stacks(endpoint=_endpoint(endpoint))
        dump(stacks, output, _stack_table(stacks))
    finally:
        client.disconnect()


@app.command("get")
def get_stack(
    name: str,
    output: str = typer.Option("json", "--output", "-o", help="json|yaml"),
    endpoint: str = typer.Option(None, "--endpoint", help="Dockge agent endpoint, empty for main instance"),
):
    _cfg, client = make_client()
    try:
        dump(client.get_stack(name, endpoint=_endpoint(endpoint)), output)
    finally:
        client.disconnect()


@app.command("save")
def save_stack(
    name: str,
    compose_file: Path = typer.Option(..., "--file", "-f", exists=True, dir_okay=False, help="Compose YAML file"),
    env_file: Path = typer.Option(None, "--env-file", exists=True, dir_okay=False, help="Compose env file"),
    endpoint: str = typer.Option(None, "--endpoint", help="Dockge agent endpoint, empty for main instance"),
):
    _cfg, client = make_client()
    try:
        ep = _endpoint(endpoint)
        is_add = not _exists(client, name, ep)
        client.save_stack(name, _read_text(compose_file), _read_text(env_file), is_add, endpoint=ep)
        console.print(f"[green]Saved[/green] stack={name} is_add={is_add}")
    finally:
        client.disconnect()


@app.command("deploy")
def deploy_stack(
    name: str,
    compose_file: Path = typer.Option(..., "--file", "-f", exists=True, dir_okay=False, help="Compose YAML file"),
    env_file: Path = typer.Option(None, "--env-file", exists=True, dir_okay=False, help="Compose env file"),
    endpoint: str = typer.Option(None, "--endpoint", help="Dockge agent endpoint, empty for main instance"),
):
    _cfg, client = make_client()
    try:
        ep = _endpoint(endpoint)
        is_add = not _exists(client, name, ep)
        client.deploy_stack(name, _read_text(compose_file), _read_text(env_file), is_add, endpoint=ep)
        console.print(f"[green]Deployed[/green] stack={name} is_add={is_add}")
    finally:
        client.disconnect()


def _action(action: str, name: str, endpoint: str | None) -> None:
    _cfg, client = make_client()
    try:
        client.stack_action(action, name, endpoint=_endpoint(endpoint))
        console.print(f"[green]{action} OK[/green] stack={name}")
    finally:
        client.disconnect()


@app.command("start")
def start(name: str, endpoint: str = typer.Option(None, "--endpoint")):
    _action("start", name, endpoint)


@app.command("stop")
def stop(name: str, endpoint: str = typer.Option(None, "--endpoint")):
    _action("stop", name, endpoint)


@app.command("restart")
def restart(name: str, endpoint: str = typer.Option(None, "--endpoint")):
    _action("restart", name, endpoint)


@app.command("update")
def update(name: str, endpoint: str = typer.Option(None, "--endpoint")):
    _action("update", name, endpoint)


@app.command("down")
def down(name: str, endpoint: str = typer.Option(None, "--endpoint")):
    _action("down", name, endpoint)


@app.command("delete")
def delete(name: str, endpoint: str = typer.Option(None, "--endpoint")):
    _action("delete", name, endpoint)
