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
- Do not write real tokens, passwords, or private instance URLs into docs or command examples.
- `dockgectl` wraps Dockge's internal Socket.IO protocol; if an event is unsupported, inspect the CLI source before falling back to raw protocol calls.
- Destructive or disruptive actions such as `stack stop`, `stack down`, `stack delete`, and overwriting with `stack deploy` require explicit user intent.
- After mutations, verify with `dockgectl stack get NAME -o json`; for service-level changes, also run `dockgectl service status NAME -o json`.

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
dockgectl doctor
dockgectl agent list -o json
dockgectl stack list -o json
dockgectl stack get app -o json
dockgectl stack logs app
dockgectl service status app -o json
dockgectl network list -o json
```

Manage stacks:

```bash
dockgectl stack deploy app -f compose.yml --env-file .env
dockgectl stack start app
dockgectl stack restart app
dockgectl stack stop app
dockgectl stack down app
dockgectl stack delete app
```

Manage services:

```bash
dockgectl service restart app web
dockgectl service status app -o json
```

Work with existing Dockge agent endpoints:

```bash
dockgectl agent list -o json
dockgectl stack list --endpoint remote.example.com -o json
dockgectl stack logs app --endpoint remote.example.com
DOCKGECTL_ENDPOINT=remote.example.com dockgectl stack get app -o json
```
