# dockgectl

[English](README.md) | [中文](README-zh.md)

`dockgectl` is a Python CLI for automating [Dockge](https://github.com/louislam/dockge) through the same Socket.IO protocol used by the Dockge web UI.

`dockgectl` is built as an AI-native operations tool. The repository includes a Codex skill at [`skills/dockge/SKILL.md`](skills/dockge/SKILL.md), so an AI agent can manage Dockge with explicit safety rules, command shapes, and verification steps instead of guessing raw Socket.IO events.

It focuses on Dockge stack workflows: listing and inspecting stacks, saving and deploying compose files, running stack lifecycle actions, checking service status, restarting services, listing Docker networks exposed by Dockge, and converting `docker run` commands to Compose YAML.

Dockge does not currently expose a broad documented REST API for stack operations. `dockgectl` wraps Dockge 1.x internal Socket.IO events and has been tested against Dockge `1.5.1-nightwatcher.0`; compatibility with other Dockge versions is not guaranteed. Older Dockge servers safely ignore the dockgectl handshake hint and retain their existing eager Agent behavior.

## AI-Native Skill

The included `dockge` skill teaches agents to use `dockgectl` as the stable executor for Dockge changes.

Key rules encoded in the skill:

- Use `dockgectl ... -o json` for inspection when exact state matters.
- Do not write real tokens, passwords, or private instance URLs into docs or command examples.
- Prefer supported `dockgectl` commands over raw Socket.IO calls.
- Require explicit user intent for disruptive actions such as `stack stop`, `stack down`, `stack delete`, and overwriting with `stack deploy`.
- Structurally compare Compose before overwriting an existing stack. Treat `stack diff` as secret-bearing when Compose may contain literal credentials.
- Use `dockgectl stack apply --verify` for save/deploy plus post-change stack and service polling, but capture its output in a mode-0600 temporary file and emit only allowlisted verification fields.
- Verify stack mutations with `dockgectl stack get NAME -o json`; verify service-level changes with `dockgectl service status NAME -o json`.
- Treat raw `stack get` / `stack ps` JSON as secret-bearing because it can contain Compose and `composeENV`; redirect it to a protected file and display only allowlisted fields.
- Before applying an existing stack, structurally allowlist the exact Compose YAML paths permitted to change and abort on any unrelated field change.

## Install

With Homebrew:

```bash
brew tap NightWatcher314/homebrew-formula
brew install dockgectl
```

For development:

```bash
uv sync
uv run dockgectl --help
```

## Configure

Create a profile and log in:

```bash
dockgectl config profile add home --url https://dockge.example.com --use
dockgectl auth login --username admin
dockgectl auth status
```

Use a specific profile for one command:

```bash
DOCKGECTL_PROFILE=home dockgectl stack list
```

Inspect the active configuration and connectivity:

```bash
dockgectl config get
dockgectl doctor -o json
dockgectl auth status -o json
```

Useful environment variables:

```bash
DOCKGECTL_URL=https://dockge.example.com
DOCKGECTL_TOKEN=...
DOCKGECTL_USERNAME=admin
DOCKGECTL_PASSWORD=...
DOCKGECTL_ENDPOINT=
DOCKGECTL_INSECURE=1
```

## Stacks

List and inspect stacks:

```bash
dockgectl stack list
dockgectl stack list --all-endpoints -o json
dockgectl stack get app -o json
dockgectl stack ps app
dockgectl stack logs app --tail 200
dockgectl stack logs app --follow --grep ERROR
```

`--tail` is supported in dockgectl 0.2.3 and later. For an older installed binary, use `dockgectl stack logs app | tail -n 200` or upgrade after checking `dockgectl stack logs --help`.

Preview, save, deploy, or apply a stack:

```bash
dockgectl stack plan app -f compose.yml --env-file .env
dockgectl stack diff app -f compose.yml --env-file .env
dockgectl stack save app -f compose.yml --env-file .env --yes
dockgectl stack deploy app -f compose.yml --env-file .env --yes
dockgectl stack apply app -f compose.yml --env-file .env --yes --health-url https://app.example.com/health
```

`stack save`, `stack deploy`, and `stack apply` prompt before overwriting an existing stack unless `--yes` is supplied. Use `--dry-run` to print the plan without mutating Dockge. Omitting `--env-file` preserves the current stack env; pass an explicitly empty env file to clear it. After a mutation, dockgectl reads the stack back and verifies the submitted env content. `stack diff` redacts secret-like env values by default, but does not redact literal credentials inside Compose; capture it rather than recording it when Compose may contain secrets. `--include-env-values` prints raw env diffs and can expose secrets. `stack apply --verify` keeps polling `stack get` and `service status`, but its output includes `verification.stack` with full `composeYAML` and `composeENV`; redirect the result to a protected file and emit only `applied`, `apply_error`, `verification.ok`, `verification.services`, and `verification.health`. If the Dockge Socket.IO event times out but the service converges, verification can still report the real outcome. Service verification accepts common Dockge/Docker healthy states such as `running`, `healthy`, `started`, and `up`.

Before applying a changed Compose file, parse the live and proposed YAML structurally and allowlist the exact paths that may change, such as `services.web.image`. Abort if any other field changes, and explicitly assert dependency service images remain unchanged. Do not use broad regex replacement for service-scoped mutations.

Run stack actions:

```bash
dockgectl stack start app
dockgectl stack stop app --yes
dockgectl stack restart app
dockgectl stack update app
dockgectl stack down app --yes
dockgectl stack delete app --yes
```

For an existing Dockge agent endpoint:

```bash
dockgectl agent list
dockgectl stack list --endpoint remote.example.com
dockgectl stack logs app --endpoint remote.example.com
```

On compatible Dockge servers, a CLI session connects only the requested Agent;
an unrelated offline Agent does not block the command. Read-only Agent events
retry once only when Dockge explicitly returns `AGENT_NOT_READY`. Ambiguous
Socket.IO timeouts and all stack/service mutations are never automatically
retried. `stack list --endpoint ENDPOINT` also waits only for a `stackList` push
matching the requested endpoint.

## Services

Inspect and manage services inside a stack:

```bash
dockgectl service status app -o json
dockgectl service status app --all-endpoints -o json
dockgectl service start app web
dockgectl service stop app web --yes
dockgectl service restart app web
```

## Networks and Composerize

```bash
dockgectl network list
dockgectl composerize 'docker run --name web nginx:alpine'
```

## Authentication and Storage

By default, `dockgectl` saves Dockge JWT tokens but not passwords. To save a password in the active profile:

```bash
DOCKGECTL_PASSWORD='...' dockgectl auth login --username admin --save-password
```

Later logins can reuse the saved password:

```bash
dockgectl auth login --use-saved-password
```

The config file is stored at `~/.config/dockgectl/config.json` with mode `0600` where possible, but saved passwords are still plaintext. Only use `--save-password` on machines you trust.

## License

MIT
