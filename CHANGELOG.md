# Changelog

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
