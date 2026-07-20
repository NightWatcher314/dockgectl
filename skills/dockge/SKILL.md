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

- Use `dockgectl ... -o json` for inspection when subsequent reasoning depends on exact state, but treat raw `stack get` and `stack ps` JSON as secret-bearing because they can include Compose content and `composeENV`.
- Never print, paste, or persist raw `stack get` / `stack ps` output in chat, logs, docs, or reports. Redirect it to a mode-0600 temporary file, extract only explicitly required non-secret fields, then delete the file.
- Prefer `dockgectl stack plan` / `dockgectl stack diff` before overwriting an existing stack.
- Prefer `dockgectl stack apply --verify` for stack save/deploy work that needs post-change validation.
- Do not write real tokens, passwords, or private instance URLs into docs or command examples.
- `dockgectl` wraps Dockge's internal Socket.IO protocol; if an event is unsupported, inspect the CLI source before falling back to raw protocol calls.
- On compatible Dockge versions, each CLI session lazily connects only the requested Agent endpoint. An unrelated offline Agent must not block the target endpoint.
- Only explicit `AGENT_NOT_READY` responses for read-only events are retried once. Never automatically retry ambiguous Socket.IO timeouts or stack/service mutations.
- Destructive or disruptive actions such as `stack stop`, `stack down`, `stack delete`, and overwriting with `stack deploy` require explicit user intent.
- Before applying an existing stack, enforce a Compose field allowlist: compare the live Compose with the proposed file, list the exact YAML paths that changed, and abort if any path is outside the task-approved set. For a single image update, for example, allow only `services.<target>.image` and assert dependency service images such as Redis and Postgres are unchanged. Do not rely on broad regex replacement or a visual diff alone.
- After mutations, verify the intended fields through a secret-safe readback, then run `dockgectl service status NAME -o json`. If a Dockge event times out but the service may still be converging, use `stack apply --verify`, service status, logs, and direct health checks before calling the deploy failed. `stack apply --verify` accepts service states such as `running`, `healthy`, `started`, and `up`; `health: null` only means no `--health-url` was supplied.

## Secret-safe inspection

`stack get` and `stack ps` embed the raw stack object. Their JSON may contain the full Compose file and `composeENV`; `-o json` does not redact those fields.

```bash
tmp="$(mktemp)"
chmod 600 "$tmp"
dockgectl stack get app -o json >"$tmp"
jq '{name, status, isManagedByDockge}' "$tmp"
rm -f "$tmp"

# Prefer the narrower command when only runtime service state is needed.
dockgectl service status app -o json
```

Adjust the `jq` allowlist only for the exact non-secret fields required by the task. Never select `composeENV`, Compose bodies, `stack`, or unknown nested objects for display. If raw secret-bearing output was exposed, stop copying it, identify the affected credentials, rotate them, and verify both provider and consumer readback.

## Compose change gate

Before `stack save`, `stack deploy`, or `stack apply` on an existing stack:

1. Save the current raw stack JSON only to a mode-0600 temporary file.
2. Extract the current Compose to another protected temporary file without printing it.
3. Parse current and proposed YAML structurally and enumerate changed field paths.
4. Define the task-approved allowlist before mutation, for example `services.web.image`.
5. Abort when an added, removed, or changed path is not allowlisted.
6. Explicitly assert critical sibling/dependency fields remain equal.
7. Run `dockgectl stack diff`; keep env values redacted and never use `--include-env-values` in recorded output.
8. Apply only after the structural gate and human-readable diff agree.

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

`stack logs --tail` is supported by dockgectl 0.2.3 and later. If an older installed binary rejects it, do not claim the service failed; use `dockgectl stack logs app | tail -n 200` or upgrade the CLI, then re-check `dockgectl stack logs --help`.

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

For remote endpoint stack inventory, `dockgectl stack list --endpoint ENDPOINT`
retries one explicit `AGENT_NOT_READY` response and ignores `stackList` pushes
from other endpoints while waiting for the requested endpoint. It does not
retry an ambiguous Socket.IO timeout. If it still fails, verify the target
agent with `dockgectl agent list -o json` before falling back to direct host
inspection.
