from __future__ import annotations

from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from dockgectl.command_help import print_help_if_no_subcommand
from dockgectl.context import make_client
from dockgectl.output import dump

app = typer.Typer(help="Manage services inside a Dockge stack")
console = Console()


@app.callback(invoke_without_command=True)
def service_callback(ctx: typer.Context):
    print_help_if_no_subcommand(ctx)


def _status_table(data: dict[str, Any]) -> Table:
    table = Table(title="Dockge service status")
    table.add_column("Service")
    table.add_column("Status")
    for service, status in sorted(data.items()):
        table.add_row(service, str(status))
    return table


def _agent_endpoints(client) -> list[str]:
    agents = client.list_agents()
    endpoints: set[str] = set()
    for endpoint, agent in agents.items():
        value = (agent.get("endpoint") or endpoint) if isinstance(agent, dict) else endpoint
        endpoints.add(str(value or ""))
    return sorted(endpoints)


@app.command("status")
def status(
    stack: str,
    output: str = typer.Option("table", "--output", "-o", help="table|json|yaml"),
    endpoint: str = typer.Option(None, "--endpoint"),
    all_endpoints: bool = typer.Option(False, "--all-endpoints", help="Check this stack across every configured Dockge agent endpoint"),
):
    _cfg, client = make_client()
    try:
        if all_endpoints:
            data: dict[str, Any] = {}
            for ep in _agent_endpoints(client):
                try:
                    data[ep] = client.service_status(stack, endpoint=ep)
                except Exception as exc:
                    data[ep] = {"error": str(exc)}
            dump(data, output)
            return
        data = client.service_status(stack, endpoint=endpoint)
        dump(data, output, _status_table(data))
    finally:
        client.disconnect()


def _confirm_service_action(action: str, stack: str, service: str, yes: bool) -> None:
    if action in {"stop"} and not yes:
        typer.confirm(f"Run disruptive action '{action}' on {stack}/{service}?", abort=True)


def _action(action: str, stack: str, service: str, endpoint: str | None, yes: bool = True) -> None:
    _confirm_service_action(action, stack, service, yes)
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
def stop(stack: str, service: str, endpoint: str = typer.Option(None, "--endpoint"), yes: bool = typer.Option(False, "--yes", "-y")):
    _action("stop", stack, service, endpoint, yes)


@app.command("restart")
def restart(stack: str, service: str, endpoint: str = typer.Option(None, "--endpoint")):
    _action("restart", stack, service, endpoint)
