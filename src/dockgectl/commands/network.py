from __future__ import annotations

import typer
from rich.table import Table

from dockgectl.context import make_client
from dockgectl.output import dump

app = typer.Typer(help="Inspect Docker networks via Dockge")


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

