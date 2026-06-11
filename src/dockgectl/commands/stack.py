from __future__ import annotations

import difflib
import re
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

import typer
from rich.console import Console
from rich.table import Table

from dockgectl.command_help import print_help_if_no_subcommand
from dockgectl.client import status_name
from dockgectl.context import make_client
from dockgectl.errors import ApiError, NotFoundError
from dockgectl.output import dump

app = typer.Typer(help="Manage Dockge stacks")
console = Console()

SECRET_KEY_RE = re.compile(r"(pass|password|token|secret|key|credential|cookie|auth|jwt)", re.I)
COMPOSE_KEYS = ("composeYAML", "composeYaml", "composeFile", "compose", "yaml")
ENV_KEYS = ("composeENV", "composeEnv", "env", "stackEnv")


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


def _ps_table(data: dict[str, Any]) -> Table:
    table = Table(title=f"Dockge stack ps: {data.get('name', '')}")
    for col in ["Service", "Status"]:
        table.add_column(col)
    services = data.get("services") or {}
    for service, status in sorted(services.items()):
        table.add_row(service, str(status))
    if not services:
        table.add_row("(none)", "")
    return table


def _exists(client, name: str, endpoint: str | None) -> bool:
    try:
        client.get_stack(name, endpoint=endpoint)
        return True
    except NotFoundError:
        return False


def _agent_endpoints(client) -> list[str]:
    agents = client.list_agents()
    endpoints: set[str] = set()
    for endpoint, agent in agents.items():
        value = (agent.get("endpoint") or endpoint) if isinstance(agent, dict) else endpoint
        endpoints.add(str(value or ""))
    return sorted(endpoints)


def _stack_text(stack: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = stack.get(key)
        if isinstance(value, str):
            return value
    return ""


def _parse_env(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def _redact_value(key: str, value: str) -> str:
    if SECRET_KEY_RE.search(key):
        return "<redacted>" if value else ""
    return value


def _env_delta(current: str, desired: str) -> dict[str, Any]:
    current_env = _parse_env(current)
    desired_env = _parse_env(desired)
    current_keys = set(current_env)
    desired_keys = set(desired_env)
    common = current_keys & desired_keys
    changed = sorted(k for k in common if current_env[k] != desired_env[k])
    return {
        "added": sorted(desired_keys - current_keys),
        "removed": sorted(current_keys - desired_keys),
        "changed": [
            {
                "key": key,
                "current": _redact_value(key, current_env[key]),
                "desired": _redact_value(key, desired_env[key]),
            }
            for key in changed
        ],
    }


def _build_plan(client, name: str, compose_text: str, env_text: str, endpoint: str | None) -> dict[str, Any]:
    try:
        stack = client.get_stack(name, endpoint=endpoint)
        exists = True
    except NotFoundError:
        stack = {}
        exists = False
    current_compose = _stack_text(stack, COMPOSE_KEYS)
    current_env = _stack_text(stack, ENV_KEYS)
    return {
        "name": name,
        "endpoint": endpoint or "",
        "exists": exists,
        "compose_changed": current_compose != compose_text,
        "env_changed": current_env != env_text,
        "env_delta": _env_delta(current_env, env_text),
        "current_compose_found": bool(current_compose),
        "current_env_found": bool(current_env),
    }


def _diff_text(label: str, current: str, desired: str) -> str:
    if current == desired:
        return f"# {label}: no changes\n"
    return "".join(
        difflib.unified_diff(
            current.splitlines(keepends=True),
            desired.splitlines(keepends=True),
            fromfile=f"current/{label}",
            tofile=f"desired/{label}",
        )
    ) or f"# {label}: changed\n"


def _print_plan_table(plan: dict[str, Any]) -> Table:
    table = Table(title="Dockge stack plan")
    table.add_column("Field")
    table.add_column("Value")
    for key in ["name", "endpoint", "exists", "compose_changed", "env_changed", "current_compose_found", "current_env_found"]:
        table.add_row(key, str(plan.get(key)))
    delta = plan.get("env_delta") or {}
    table.add_row("env_added", ", ".join(delta.get("added") or []))
    table.add_row("env_removed", ", ".join(delta.get("removed") or []))
    table.add_row("env_changed_keys", ", ".join(item["key"] for item in delta.get("changed") or []))
    return table


def _confirm_overwrite(name: str, exists: bool, yes: bool, action: str) -> None:
    if not exists or yes:
        return
    typer.confirm(f"Stack '{name}' already exists. Continue with {action}?", abort=True)


def _confirm_disruptive(action: str, name: str, yes: bool) -> None:
    if yes:
        return
    typer.confirm(f"Run disruptive action '{action}' on stack '{name}'?", abort=True)


def _filter_logs(text: str, tail: int | None, grep: str | None) -> str:
    lines = text.splitlines(keepends=True)
    if grep:
        lines = [line for line in lines if grep in line]
    if tail is not None:
        lines = [] if tail == 0 else lines[-tail:]
    return "".join(lines)


def _health_check(url: str, timeout: float = 5.0) -> dict[str, Any]:
    try:
        req = Request(url, headers={"User-Agent": "dockgectl"})
        with urlopen(req, timeout=timeout) as response:
            return {"ok": 200 <= response.status < 400, "status": response.status, "url": url}
    except URLError as exc:
        return {"ok": False, "url": url, "error": str(exc)}
    except Exception as exc:  # pragma: no cover - defensive around platform urllib errors
        return {"ok": False, "url": url, "error": str(exc)}


def _service_status_ok(services: dict[str, Any]) -> bool:
    if not services:
        return False
    for value in services.values():
        if isinstance(value, dict):
            raw = value.get("status") or value.get("state") or value.get("Status") or value
        else:
            raw = value
        text = str(raw).lower()
        if not ("running" in text or text in {"3", "true"}):
            return False
    return True


def _verify_stack(client, name: str, endpoint: str | None, health_url: str | None, timeout: float, interval: float, require_services: bool = True) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last: dict[str, Any] = {}
    while True:
        try:
            stack = client.get_stack(name, endpoint=endpoint)
            services = client.service_status(name, endpoint=endpoint)
            health = _health_check(health_url) if health_url else None
            services_ok = _service_status_ok(services) if require_services else True
            health_ok = health is None or bool(health.get("ok"))
            stack_ok = bool(stack)
            ok = stack_ok and services_ok and health_ok
            last = {"ok": ok, "stack": stack, "services": services, "health": health, "require_services": require_services}
            if ok or time.monotonic() >= deadline:
                return last
        except Exception as exc:  # pragma: no cover - exercised through CLI/integration more than unit tests
            last = {"ok": False, "error": str(exc)}
            if time.monotonic() >= deadline:
                return last
        time.sleep(interval)


@app.command("list")
def list_stacks(
    output: str = typer.Option("table", "--output", "-o", help="table|json|yaml"),
    endpoint: str = typer.Option(None, "--endpoint", help="Dockge agent endpoint, empty for main instance"),
    all_endpoints: bool = typer.Option(False, "--all-endpoints", help="List stacks across every configured Dockge agent endpoint"),
):
    _cfg, client = make_client()
    try:
        if all_endpoints:
            data: dict[str, Any] = {}
            for ep in _agent_endpoints(client):
                try:
                    data[ep] = client.list_stacks(endpoint=ep)
                except Exception as exc:
                    data[ep] = {"error": str(exc)}
            dump(data, output)
            return
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


@app.command("ps")
def ps_stack(
    name: str,
    output: str = typer.Option("table", "--output", "-o", help="table|json|yaml"),
    endpoint: str = typer.Option(None, "--endpoint", help="Dockge agent endpoint, empty for main instance"),
):
    _cfg, client = make_client()
    try:
        ep = _endpoint(endpoint)
        stack = client.get_stack(name, endpoint=ep)
        data = {
            "name": name,
            "endpoint": ep or "",
            "status": status_name(stack.get("status")),
            "isManagedByDockge": stack.get("isManagedByDockge"),
            "services": client.service_status(name, endpoint=ep),
            "stack": stack,
        }
        dump(data, output, _ps_table(data))
    finally:
        client.disconnect()


@app.command("logs")
def logs(
    name: str,
    endpoint: str = typer.Option(None, "--endpoint", help="Dockge agent endpoint, empty for main instance"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Keep streaming log output"),
    wait: float = typer.Option(2.0, "--wait", help="Seconds to wait for initial log output without --follow"),
    tail: int = typer.Option(None, "--tail", min=0, help="Show only the last N lines from the received log buffer"),
    grep: str = typer.Option(None, "--grep", help="Only print log lines containing this text"),
):
    _cfg, client = make_client()
    try:
        first = True
        for chunk in client.stack_logs(name, endpoint=_endpoint(endpoint), follow=follow, wait=wait):
            if first:
                chunk = _filter_logs(chunk, tail, grep)
                first = False
            elif grep:
                chunk = _filter_logs(chunk, None, grep)
            if chunk:
                console.file.write(chunk)
                console.file.flush()
    except KeyboardInterrupt:
        pass
    finally:
        client.disconnect()


@app.command("plan")
def plan_stack(
    name: str,
    compose_file: Path = typer.Option(..., "--file", "-f", exists=True, dir_okay=False, help="Compose YAML file"),
    env_file: Path = typer.Option(None, "--env-file", exists=True, dir_okay=False, help="Compose env file"),
    endpoint: str = typer.Option(None, "--endpoint", help="Dockge agent endpoint, empty for main instance"),
    output: str = typer.Option("table", "--output", "-o", help="table|json|yaml"),
):
    _cfg, client = make_client()
    try:
        plan = _build_plan(client, name, _read_text(compose_file), _read_text(env_file), _endpoint(endpoint))
        dump(plan, output, _print_plan_table(plan))
    finally:
        client.disconnect()


@app.command("diff")
def diff_stack(
    name: str,
    compose_file: Path = typer.Option(..., "--file", "-f", exists=True, dir_okay=False, help="Compose YAML file"),
    env_file: Path = typer.Option(None, "--env-file", exists=True, dir_okay=False, help="Compose env file"),
    endpoint: str = typer.Option(None, "--endpoint", help="Dockge agent endpoint, empty for main instance"),
    include_env_values: bool = typer.Option(False, "--include-env-values", help="Also print a raw env diff. Secrets may be exposed."),
):
    _cfg, client = make_client()
    try:
        stack = client.get_stack(name, endpoint=_endpoint(endpoint))
        compose_text = _read_text(compose_file)
        env_text = _read_text(env_file)
        console.print(_diff_text("compose.yaml", _stack_text(stack, COMPOSE_KEYS), compose_text), markup=False, end="")
        delta = _env_delta(_stack_text(stack, ENV_KEYS), env_text)
        console.print("\n# env delta (values redacted for secret-like keys)", markup=False)
        dump(delta, "yaml")
        if include_env_values:
            console.print("\n# raw env diff", markup=False)
            console.print(_diff_text(".env", _stack_text(stack, ENV_KEYS), env_text), markup=False, end="")
    finally:
        client.disconnect()


@app.command("save")
def save_stack(
    name: str,
    compose_file: Path = typer.Option(..., "--file", "-f", exists=True, dir_okay=False, help="Compose YAML file"),
    env_file: Path = typer.Option(None, "--env-file", exists=True, dir_okay=False, help="Compose env file"),
    endpoint: str = typer.Option(None, "--endpoint", help="Dockge agent endpoint, empty for main instance"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Confirm overwriting an existing stack"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show the plan without saving"),
):
    _cfg, client = make_client()
    try:
        ep = _endpoint(endpoint)
        compose_text = _read_text(compose_file)
        env_text = _read_text(env_file)
        plan = _build_plan(client, name, compose_text, env_text, ep)
        if dry_run:
            dump(plan, "yaml")
            return
        _confirm_overwrite(name, bool(plan["exists"]), yes, "save")
        client.save_stack(name, compose_text, env_text, not plan["exists"], endpoint=ep)
        console.print(f"[green]Saved[/green] stack={name} is_add={not plan['exists']}")
    finally:
        client.disconnect()


@app.command("deploy")
def deploy_stack(
    name: str,
    compose_file: Path = typer.Option(..., "--file", "-f", exists=True, dir_okay=False, help="Compose YAML file"),
    env_file: Path = typer.Option(None, "--env-file", exists=True, dir_okay=False, help="Compose env file"),
    endpoint: str = typer.Option(None, "--endpoint", help="Dockge agent endpoint, empty for main instance"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Confirm overwriting an existing stack"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show the plan without deploying"),
):
    _cfg, client = make_client()
    try:
        ep = _endpoint(endpoint)
        compose_text = _read_text(compose_file)
        env_text = _read_text(env_file)
        plan = _build_plan(client, name, compose_text, env_text, ep)
        if dry_run:
            dump(plan, "yaml")
            return
        _confirm_overwrite(name, bool(plan["exists"]), yes, "deploy")
        client.deploy_stack(name, compose_text, env_text, not plan["exists"], endpoint=ep)
        console.print(f"[green]Deployed[/green] stack={name} is_add={not plan['exists']}")
    finally:
        client.disconnect()


@app.command("apply")
def apply_stack(
    name: str,
    compose_file: Path = typer.Option(..., "--file", "-f", exists=True, dir_okay=False, help="Compose YAML file"),
    env_file: Path = typer.Option(None, "--env-file", exists=True, dir_okay=False, help="Compose env file"),
    endpoint: str = typer.Option(None, "--endpoint", help="Dockge agent endpoint, empty for main instance"),
    mode: str = typer.Option("deploy", "--mode", help="deploy|save"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Confirm overwriting an existing stack"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show the plan without applying"),
    verify: bool = typer.Option(True, "--verify/--no-verify", help="Poll stack and service status after applying"),
    health_url: str = typer.Option(None, "--health-url", help="Optional HTTP(S) URL that must return a 2xx/3xx status"),
    timeout: float = typer.Option(120.0, "--timeout", help="Verification timeout in seconds"),
    interval: float = typer.Option(3.0, "--interval", help="Verification poll interval in seconds"),
):
    if mode not in {"deploy", "save"}:
        raise typer.BadParameter("--mode must be deploy or save")
    _cfg, client = make_client()
    try:
        ep = _endpoint(endpoint)
        compose_text = _read_text(compose_file)
        env_text = _read_text(env_file)
        plan = _build_plan(client, name, compose_text, env_text, ep)
        if dry_run:
            dump(plan, "yaml")
            return
        _confirm_overwrite(name, bool(plan["exists"]), yes, mode)
        apply_error: str | None = None
        try:
            if mode == "save":
                client.save_stack(name, compose_text, env_text, not plan["exists"], endpoint=ep)
            else:
                client.deploy_stack(name, compose_text, env_text, not plan["exists"], endpoint=ep)
        except ApiError as exc:
            apply_error = str(exc)
            if "Timed out waiting" not in apply_error:
                raise
            console.print(f"[yellow]Apply event timed out; continuing with verification:[/yellow] {apply_error}")
        result = {"applied": apply_error is None, "apply_error": apply_error, "plan": plan}
        if verify:
            verification = _verify_stack(client, name, ep, health_url, timeout, interval, require_services=(mode == "deploy"))
            result["verification"] = verification
            dump(result, "yaml")
            if not verification.get("ok"):
                raise typer.Exit(1)
        else:
            dump(result, "yaml")
    finally:
        client.disconnect()


def _action(action: str, name: str, endpoint: str | None, yes: bool) -> None:
    if action in {"stop", "down", "delete"}:
        _confirm_disruptive(action, name, yes)
    _cfg, client = make_client()
    try:
        client.stack_action(action, name, endpoint=_endpoint(endpoint))
        console.print(f"[green]{action} OK[/green] stack={name}")
    finally:
        client.disconnect()


@app.command("start")
def start(name: str, endpoint: str = typer.Option(None, "--endpoint")):
    _action("start", name, endpoint, True)


@app.command("stop")
def stop(name: str, endpoint: str = typer.Option(None, "--endpoint"), yes: bool = typer.Option(False, "--yes", "-y")):
    _action("stop", name, endpoint, yes)


@app.command("restart")
def restart(name: str, endpoint: str = typer.Option(None, "--endpoint")):
    _action("restart", name, endpoint, True)


@app.command("update")
def update(name: str, endpoint: str = typer.Option(None, "--endpoint")):
    _action("update", name, endpoint, True)


@app.command("down")
def down(name: str, endpoint: str = typer.Option(None, "--endpoint"), yes: bool = typer.Option(False, "--yes", "-y")):
    _action("down", name, endpoint, yes)


@app.command("delete")
def delete(name: str, endpoint: str = typer.Option(None, "--endpoint"), yes: bool = typer.Option(False, "--yes", "-y")):
    _action("delete", name, endpoint, yes)
