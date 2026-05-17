from __future__ import annotations

from typing import Any

import typer
from rich.table import Table

from dockgectl.command_help import print_help_if_no_subcommand
from dockgectl.context import make_client
from dockgectl.output import dump

app = typer.Typer(help="Manage Dockge agent hosts")


@app.callback(invoke_without_command=True)
def agent_callback(ctx: typer.Context):
    print_help_if_no_subcommand(ctx)


def _agent_table(agents: dict[str, Any]) -> Table:
    table = Table(title="Dockge agent hosts")
    for col in ["Endpoint", "Name", "URL", "Username"]:
        table.add_column(col)
    for endpoint, agent in sorted(agents.items()):
        table.add_row(
            agent.get("endpoint") or endpoint or "(main)",
            agent.get("name") or "",
            agent.get("url") or "",
            agent.get("username") or "",
        )
    return table


@app.command("list")
def list_agents(output: str = typer.Option("table", "--output", "-o", help="table|json|yaml")):
    _cfg, client = make_client()
    try:
        agents = client.list_agents()
        dump(agents, output, _agent_table(agents))
    finally:
        client.disconnect()
