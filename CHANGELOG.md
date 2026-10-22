# Changelog

Author: OSAZEE.

## Unreleased

- **2026-10-22:** Replace the single **Light to dim** picker with **Lights to dim**,
  supporting one or more light entities. Keep the `light_entity` key and accept
  legacy scalar inputs as well as lists.
- Dim each light from its own starting brightness and estimate its release level
  separately. Share the brighten/dim-down sequence using a YAML anchor.
- Skip unavailable/unknown lights and duplicate selections. Brighten off lights
  from 1%; leave off lights off when dimming down. Continue remaining light commands
  if an individual service call fails. Keep the 30-second bounded release wait.
- Add multi-light dimming regression tests with recorded service calls, without
  controlling real lights. No companion integration update is required.

- Add **Both buttons - Double click** as the twelfth gesture assignment, with a
  backward-compatible empty action-list default and multiple actions per gesture.
- Match native double-click events from the same remote in either button order;
  after the existing legacy triple-click decision window, run the combined sequence
  once and suppress both individual double-click actions, even with an empty list.
- Preserve triple-click precedence, recognition-window bounds and fresh-event guards.
- Add offline blueprint sequence regression tests alongside the Matter detector tests.

## 0.1.0b1 — 2026-10-14

Initial public beta.

- Multi-remote blueprint with expandable remote entries and shared action assignments.
- Freely configurable multi-action sequences for single, double, triple, hold and combined gestures.
- Optional single-button hold-to-dim mode.
- Adjustable 250 ms recognition window.
- Optional live Matter aborted-multipress bridge for firmware 1.9.15.
- Replay floors, event-number deduplication and startup/pending-sequence guards.
- English setup documentation, minimal diagnostics and detector regression tests.

Known limitations: raw triple means **at least three**; the companion uses Core Matter internal interfaces; some hardware gesture combinations still need beta testing.
