---
name: dockge
description: Use when managing Dockge through the local dockgectl CLI, including agent hosts, stacks, stack logs, services, networks, and composerize workflows.
metadata:
  short-description: Manage Dockge with dockgectl
---

# Dockge via dockgectl

Use `dockgectl` as the stable executor for Dockge changes. Prefer it over raw Socket.IO calls unless a required operation is not supported.

## Executor

- Prefer `dockgectl` when it is available on `PATH`.
- If `dockgectl` is not available, run commands from the project directory:

```bash
cd /home/arch/Agents/Jarvis/dockgectl
uv run dockgectl --help
```

- When using the fallback, prefix examples with `uv run` after changing into `/home/arch/Agents/Jarvis/dockgectl`.

## Core rules

- Use `dockgectl ... -o json` for inspection when subsequent reasoning depends on exact state.
- Prefer `dockgectl stack plan` / `dockgectl stack diff` before overwriting an existing stack.
- Prefer `dockgectl stack apply --verify` for stack save/deploy work that needs post-change validation.
- Do not write real tokens, passwords, or private instance URLs into docs or command examples.
- `dockgectl` wraps Dockge's internal Socket.IO protocol; if an event is unsupported, inspect the CLI source before falling back to raw protocol calls.
- Destructive or disruptive actions such as `stack stop`, `stack down`, `stack delete`, and overwriting with `stack deploy` require explicit user intent.
- After mutations, verify with `dockgectl stack get NAME -o json`; for service-level changes, also run `dockgectl service status NAME -o json`. If a Dockge event times out but the service may still be converging, use `stack apply --verify`, service status, logs, and direct health checks before calling the deploy failed.

## Common commands

Configure profiles and login:

```bash
dockgectl config profile add home --url https://dockge.example.com --use
dockgectl auth login --username admin
dockgectl auth status
```

Use `DOCKGECTL_PROFILE=name` for one-off commands.

Inspect:

```bash
dockgectl doctor -o json
dockgectl agent list -o json
dockgectl stack list -o json
dockgectl stack list --all-endpoints -o json
dockgectl stack get app -o json
dockgectl stack ps app -o json
dockgectl stack logs app --tail 200
dockgectl service status app -o json
dockgectl service status app --all-endpoints -o json
dockgectl network list -o json
```

Manage stacks:

```bash
dockgectl stack plan app -f compose.yml --env-file .env
dockgectl stack diff app -f compose.yml --env-file .env
dockgectl stack apply app -f compose.yml --env-file .env --yes
dockgectl stack start app
dockgectl stack restart app
dockgectl stack stop app --yes
dockgectl stack down app --yes
dockgectl stack delete app --yes
```

Manage services:

```bash
dockgectl service restart app web
dockgectl service status app -o json
dockgectl service status app --all-endpoints -o json
```

Work with existing Dockge agent endpoints:

```bash
dockgectl agent list -o json
dockgectl stack list --endpoint remote.example.com -o json
dockgectl stack logs app --endpoint remote.example.com
DOCKGECTL_ENDPOINT=remote.example.com dockgectl stack get app -o json
```
