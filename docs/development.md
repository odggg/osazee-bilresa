# Development and release checklist

Author: OSAZEE.

## Tests

Run `python -B -m unittest discover -s tests -v` from the repository root. No Home Assistant installation or external test package is required. Syntax-check the integration with `python -m compileall -q custom_components`.

The detector is a standalone standard-library module. The tests do **not** establish full Home Assistant integration or blueprint runtime compatibility.

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
