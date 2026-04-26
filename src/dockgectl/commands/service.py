from __future__ import annotations

from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from dockgectl.context import make_client
from dockgectl.output import dump

app = typer.Typer(help="Manage services inside a Dockge stack")
console = Console()


def _status_table(data: dict[str, Any]) -> Table:
    table = Table(title="Dockge service status")
    table.add_column("Service")
    table.add_column("Status")
    for service, status in sorted(data.items()):
        table.add_row(service, str(status))
    return table


@app.command("status")
def status(
    stack: str,
    output: str = typer.Option("table", "--output", "-o", help="table|json|yaml"),
    endpoint: str = typer.Option(None, "--endpoint"),
):
    _cfg, client = make_client()
    try:
        data = client.service_status(stack, endpoint=endpoint)
        dump(data, output, _status_table(data))
    finally:
        client.disconnect()


def _action(action: str, stack: str, service: str, endpoint: str | None) -> None:
    _cfg, client = make_client()
    try:
        client.service_action(action, stack, service, endpoint=endpoint)
        console.print(f"[green]{action} OK[/green] stack={stack} service={service}")
    finally:
        client.disconnect()


@app.command("start")
def start(stack: str, service: str, endpoint: str = typer.Option(None, "--endpoint")):
    _action("start", stack, service, endpoint)


@app.command("stop")
def stop(stack: str, service: str, endpoint: str = typer.Option(None, "--endpoint")):
    _action("stop", stack, service, endpoint)


@app.command("restart")
def restart(stack: str, service: str, endpoint: str = typer.Option(None, "--endpoint")):
    _action("restart", stack, service, endpoint)

