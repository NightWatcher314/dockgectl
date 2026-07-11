# Changelog

## v0.2.3 - 2026-07-12

- Identify dockgectl through Socket.IO handshake metadata so compatible Dockge
  servers can connect only the requested Agent instead of logging in to every
  configured Agent for each short-lived CLI session.
- Handle structured Agent readiness, authentication, and proxy errors without
  waiting for an ambiguous Socket.IO timeout.
- Retry only explicit `AGENT_NOT_READY` responses for a fixed allowlist of
  read-only events; never automatically retry stack or service mutations.
- Preserve an existing stack `.env` when `--env-file` is omitted, allow an
  explicitly empty env file to clear it, and verify submitted env content by
  reading the stack back after save, deploy, or apply.

## v0.2.2 - 2026-07-08

- Make remote `stack list` requests more tolerant of transient Dockge agent
  timeouts by retrying one `requestStackList` call before failing.
- Ignore `stackList` pushes for other agent endpoints while waiting for the
  requested endpoint, avoiding cross-endpoint races.
- Update README and Dockge skill guidance for the remote endpoint stack-list
  behavior.

## v0.2.1 - 2026-06-13

- Fix `stack apply --verify` service-status parsing for Dockge responses that
  group service records in lists.
- Treat `healthy`, `started`, and `up` service states as successful verification
  states while still rejecting unhealthy or exited states.
- Update README and Dockge skill guidance for the corrected verification
  behavior.

## v0.2.0 - 2026-06-12

- Add `stack plan`, `stack diff`, and `stack apply --verify` for safer stack changes.
- Add `stack logs --tail` and `--grep` filtering.
- Add `stack ps` and `--all-endpoints` inspection for stacks and services.
- Add `-o json|yaml|table` support to `doctor` and `auth status`.
- Add confirmation and `--dry-run` safeguards for overwriting and disruptive actions.
- Update README and Dockge skill guidance for the safer workflow.
