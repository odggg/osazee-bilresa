# Development and release checklist

Author: OSAZEE.

## Tests

Install the pinned test dependencies with `python -m pip install -r tests/requirements.txt`,
then run `python -B -m unittest discover -s tests -v` from the repository root.
No Home Assistant installation is required. Syntax-check the integration with
`python -m compileall -q custom_components`.

The detector is a standalone standard-library module. Blueprint click tests load
the actual YAML and execute its Jinja/branch/wait/stop logic using a bounded,
marker-action-only interpreter and a simulated clock. They cover both-button double
clicks in both orders, both hold modes, multi-action ordering, empty assignments,
remote isolation, adjustable timing, invalid/restored/stale states and legacy/native/raw
triple-click precedence. The interpreter deliberately rejects unmodeled action types;
it does not run services or simulate hardware. These tests do **not** establish full
Home Assistant schema/integration/runtime compatibility or physical-device behavior.

## Packaging

- Exactly one component: `custom_components/osazee_bilresa/`.
- Minimum tested Core version: 2026.8.0; firmware: BILRESA dual-button 1.9.15.
- Blueprint source URL remains stable; do not rename/remove existing input keys.
- Bump manifest and diagnostics versions together; update CHANGELOG.
- No live config exports, credentials, logs, personal entity IDs or `.storage/` files.
- Keep raw triple recognition labelled **at least three**.
- Brand icon is an original schematic remote graphic, not an IKEA logo.

## Before calling a release stable

- Physically test every button and combined gesture on more than one remote.
- Confirm lone/delayed clicks never run combined actions.
- Confirm raw duplicates and diagnostic history cannot replay actions.
- Test startup, native Matter reload, server disconnect/reconnect and integration removal.
- Test custom hold mode, dimming release, duplicate/incomplete remote selection and long action sequences.
- Validate blueprint schemas/templates in the minimum supported Core version.
- Run Home Assistant hassfest and HACS validation before requesting default-catalog inclusion.

## Repository settings

HACS's general publishing checks require a repository description and topics. Set these in GitHub's **About** settings:

Description: `IKEA BILRESA Matter blueprint and optional rapid multipress bridge for Home Assistant.`

Topics: `home-assistant`, `hacs`, `blueprint`, `matter`, `ikea-bilresa`.

The initial publication includes the repository description and topics above. HACS catalog submission is separate from publishing this repository; no default-catalog listing is claimed here. Check the HACS validation job before distributing an update.
