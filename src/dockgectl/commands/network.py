from __future__ import annotations

import typer
from rich.table import Table

from dockgectl.command_help import print_help_if_no_subcommand
from dockgectl.context import make_client
from dockgectl.output import dump

app = typer.Typer(help="Inspect Docker networks via Dockge")


@app.callback(invoke_without_command=True)
def network_callback(ctx: typer.Context):
    print_help_if_no_subcommand(ctx)


@app.command("list")
def list_networks(
    output: str = typer.Option("table", "--output", "-o", help="table|json|yaml"),
    endpoint: str = typer.Option(None, "--endpoint"),
):
    _cfg, client = make_client()
    try:
        networks = client.docker_networks(endpoint=endpoint)
        table = Table(title="Docker networks")
        table.add_column("Name")
        for name in networks:
            table.add_row(name)
        dump(networks, output, table)
    finally:
        client.disconnect()
