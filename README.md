<img src="custom_components/osazee_bilresa/brand/icon.png" width="96" alt="OSAZEE BILRESA icon">

# The ULTIMATE IKEA Bilresa Blueprint — 12 Gestures, Triple Clicks, Dual-Button Combos, Dimming & Multi-Remote Control

**Author: OSAZEE · Public beta 0.1.0b1 · MIT license**

Two buttons. A whole room of possibilities. Turn your **IKEA BILRESA dual-button Matter remote** into a flexible Home Assistant controller with **dimming, single, double and triple clicks, both-button clicks and holds**, and multi-step actions. Start with one remote, add more with shared controls, and choose exactly what every gesture does.

## Summary — everything in one blueprint

### Twelve gesture assignments, not just two buttons

| Control | Available gestures |
| --- | --- |
| Button 1 | Single click, double click, triple click, hold |
| Button 2 | Single click, double click, triple click, hold |
| Both buttons together, on the same remote | Short press, double click, triple click, hold |

- **Your actions, your devices:** every gesture has its own Home Assistant action editor. Toggle lights or plugs, control covers, activate scenes, call scripts, or build a sequence containing several actions, conditions and delays. Use **Add action** to extend a sequence; leave a gesture empty to do nothing. Nothing is preassigned to personal devices.
- **Combined gestures take priority:** a recognized both-button gesture selects the combined action sequence instead of the individual button sequences. Buttons from different remotes are never combined. **Both buttons - Double click** matches two native `multi_press_2` events within the recognition window, then waits one further window for a possible legacy third click before running once. An empty combined assignment still suppresses the individual actions for that recognized combination.

### Choose custom holds or built-in dimming

- **Custom actions mode:** freely assign both single-button holds. No controlled light or other target device is required by the blueprint.
- **Light dimming mode:** hold Button 1 to brighten and Button 2 to dim one selected light. Tune the full brightness ramp from **1–10 seconds**, release-event latency compensation from **0–1 second**, and the release transition from **0–2 seconds**. Defaults are **3 seconds**, **0.06 seconds** and **0.2 seconds** respectively; release stops the ramp at an estimated brightness.
- **Clear mode separation:** dimming reserves the two single-button holds, so their custom action lists are ignored. All click actions and both-button gestures remain configurable in either mode. Home Assistant keeps the unused fields visible; they are explicitly labelled.

### One remote or a shared set — with timing you control

- **Add remote, not another copy of your setup:** start with the single **Remote 1** entry, select its two native button event entities, and add further named remotes with entity pickers. All remotes in that automation immediately share its assignments and later edits. Separate automations can use different assignments while sharing the installed blueprint logic.
- **Adjustable 250 ms recognition window:** set the cooldown from **100–1500 ms**, in **10 ms** steps, to balance response speed and combination tolerance. Matching uses event arrival in Home Assistant, not the remote's internal click-counting timeout; the hardware may add reporting delay. Double-click actions wait for the window to expire.
- **Defensive configuration handling:** incomplete remote entries are ignored. Duplicate button-entity selections disable gesture handling until corrected rather than creating ambiguous assignments.

### Rapid triple clicks, with a purpose-built Matter companion

- **Native and bridged recognition:** the blueprint handles native `multi_press_3` when supplied. The optional **OSAZEE BILRESA** companion exposes the otherwise hidden aborted-multipress signal used by firmware **1.9.15** for rapid **3+ clicks**. A legacy double-then-single fallback is also present, but depends on the integration's events.
- **Local event-driven operation:** the companion uses the existing Matter client and discovers eligible dual-button remotes. No re-pairing, additional host, credentials, manual node IDs, separate Matter connection, or Core/Matter-server patch is needed. Only remotes selected in your blueprint automation can run its actions.
- **Recovery and visibility:** subscription reconciliation handles replaced Matter clients after reload; a **30-second local-reference watchdog** is a fallback, not device polling. Event-to-entity lookup uses the current registry, and diagnostics expose the emitted-event counter and last source event for troubleshooting.

### Safeguards, sharing and maintainability

- **Fresh gestures only:** restored, unknown, unavailable and non-advancing native event states are rejected. Pending recognition is discarded on reload/restart. The companion rejects duplicate event numbers and stale/incomplete sequences; historical diagnostics establish a replay-protection baseline and never dispatch actions. Startup-time raw events do not emit gestures.
- **One selected sequence per recognized gesture:** single execution mode prevents overlapping runs. New gestures are ignored while the current sequence or dimming run is active, so keep long-running custom sequences in mind. This does not disable or coordinate other automations that also listen to the remote.
- **Ready to share:** English blueprint inputs and documentation, author **OSAZEE**, **MIT license**, a direct blueprint-import button, optional HACS custom-repository or manual companion installation, configurable examples, diagnostics, and **24 detector regression tests plus blueprint-sequence tests**, with CI/HACS validation. Blueprint and companion updates are separate: re-import the blueprint for new logic; update the companion through HACS.

**Compatibility and beta limits:** requires Home Assistant Core **2026.8.0+**, a **dual-button BILRESA paired through Matter**, and two enabled native button event entities. The companion does not support the scroll-wheel model, ZHA or Zigbee2MQTT. On firmware **1.9.15**, rapid triple clicks need the companion and **Raw triple-click bridge** enabled: **four or more clicks can trigger the same action; exact-three detection is not available**. Triple recognition remains experimental, broader physical testing is needed, and future Core/firmware compatibility is not guaranteed. Cover movement/stop can be configured in your action lists; daily brightness schedules are separate automations, not built-in features.

This is an independent community project, not an official IKEA or Home Assistant integration.

## Install

[![Import blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fodggg%2Fosazee-bilresa%2Fblob%2Fmain%2Fblueprints%2Fautomation%2FOSAZEE%2Fikea_bilresa_dual_button.yaml)

[![Open repository in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=odggg&repository=osazee-bilresa&category=integration)

**These install two different things.** Importing the blueprint does not install the companion integration. HACS installs the integration, not the blueprint.

- **Normal clicks, combined presses and holds:** import the blueprint; the companion is optional.
- **Rapid triple clicks on firmware 1.9.15:** install and configure the companion too, then enable **Raw triple-click bridge** in your automation.

### Requirements

- Home Assistant Core **2026.8.0 or newer**. Other versions are not yet verified.
- BILRESA **dual-button**, paired through Home Assistant's **Matter** integration.
- Two enabled native `event.*` button entities for every remote.
- HACS is optional; manual integration installation is supported.
- The scroll-wheel BILRESA, ZHA and Zigbee2MQTT are **not supported by the companion**.

### 1. Install the companion (for rapid triple clicks)

In HACS, use the button above or add `https://github.com/odggg/osazee-bilresa` as a **Custom repository**, category **Integration**. Download **OSAZEE BILRESA**, restart Home Assistant, then go to **Settings → Devices & services → Add integration → OSAZEE BILRESA**.

No host, credentials or device pairing are required. The companion uses the existing Matter client and discovers eligible native button entities.

**Manual alternative:** copy only `custom_components/osazee_bilresa/` from this repository into your Home Assistant `config/custom_components/` directory, restart, and add the integration as above. Do not copy your whole Home Assistant configuration into this repository.

This repository is not listed in the default HACS catalog. During beta, use the custom-repository method.

### 2. Import the blueprint

Click **Import blueprint** above, or open **Settings → Automations & scenes → Blueprints → Import blueprint** and paste:

```text
https://github.com/odggg/osazee-bilresa/blob/main/blueprints/automation/OSAZEE/ikea_bilresa_dual_button.yaml
```

Create an automation from the blueprint. The default entry is **Remote 1**: edit it and choose its **Button 1** and **Button 2** event entities. Use **Add** in the **Add remote** list for additional remotes.

All remotes in one automation share the same action assignments. Use a separate automation for a different set of assignments. Never select the same button entity twice; incomplete entries are ignored, and duplicate selections disable gesture handling until corrected.

### 3. Assign actions

Every gesture accepts a list of actions. Use Home Assistant's **Add action** control to run several actions in order; an empty list does nothing.

| Gesture | Configurable actions |
| --- | --- |
| Button 1 / Button 2 | Single click, double click, triple click, hold |
| Both buttons on the same remote | Short press, double click, triple click, hold |

**Single-button hold behavior:**

- **Custom actions:** both hold action lists are available; no controlled light is required.
- **Light dimming:** select one light in the optional dimming section. Button 1 brightens and Button 2 dims. The two custom single-button hold lists remain visible but are ignored. Combined holds and all click actions remain configurable.

The **Recognition window / cooldown** defaults to **250 ms** and can be adjusted from **100–1500 ms**. It measures the gap between related events as received by Home Assistant, not the remote's internal click-counting timeout. Lower values respond faster but make combined presses harder to recognize. The remote may add its own delay before reporting a completed gesture.

Enable **Raw triple-click bridge** only after configuring the companion.

**Both-button double clicks:** double-click both buttons on the same remote. Their native double-click events must arrive within the recognition window. The blueprint then waits one further window to distinguish the existing legacy triple-click fallback; native/raw triple events use their own recognition branches. This is event matching, not a new hardware gesture event. The companion is not required for combined double clicks. Re-import the blueprint to add **Both buttons - Double click** to an existing setup; its action list defaults to empty.

## Important: triple means at least three

BILRESA firmware **1.9.15** advertises `MultiPressMax=2`. Three or more quick clicks can produce `MultiPressComplete` with `totalNumberOfPressesCounted=0`; the native Matter event entity does not expose that completion.

The companion converts this **aborted multipress** into a live event for the blueprint. This means:

- Three quick clicks can run the triple-click action.
- **Four or more quick clicks may run the same action. Exact-three detection is not available with this firmware.**
- Both-button triple detection needs matching completions from the **same remote** within the configured window.
- Native `multi_press_3` is also handled when an integration provides it.
- The legacy double-then-single fallback depends on events supplied by the integration; it is not a promise that slow or spaced clicks will count as a triple.

The companion requires a fresh initial-press sequence, ongoing count 2, short release and aborted completion within three seconds. Historical diagnostics establish event-number floors only and are never fired as gestures. Pending recognition is cleared on reload/reconnect; repeated event numbers are ignored. Events received during Home Assistant startup do not emit gestures.

## Behavior and limitations

- A recognized combined gesture selects the combined action instead of both individual actions.
- The automation uses **single** mode: new gestures are ignored while the current action sequence is running, including a hold-to-dim run. Keep action lists short if fast response matters.
- Combination matching never joins buttons from two different remotes.
- Existing automations listening to these remotes can still collide. Move their assignments here or disable overlapping automations yourself.
- The blueprint ships with **no assigned lights, plugs, covers or personal entity IDs**.
- Cover movement/stop and scheduled brightness resets are **not built-in defaults**. Configure cover actions in the relevant action lists; daily schedules belong in separate automations. See [examples](docs/examples.md).
- This beta relies on internal interfaces of the Core Matter integration. Back up before updating Home Assistant; compatibility with future Core/device firmware versions is not guaranteed.

## Updating

**Integration:** update through HACS and restart when requested.

**Blueprint:** use **Re-import blueprint** in Home Assistant. Updates are not automatically downloaded with integration updates. Keep input keys stable so existing assignments continue to work.

Several remotes in the same automation always share its assignments. Separate automations share blueprint logic after the locally installed blueprint is updated/reloaded, but retain their own assignments.

## Troubleshooting

1. Confirm both native button event entities are enabled and change on a normal click.
2. Confirm **OSAZEE BILRESA** is loaded and **Raw triple-click bridge** is enabled in the blueprint automation.
3. Download the companion's diagnostics. `emitted_since_setup` increases for recognized raw gestures; `last_event` identifies the source button.
4. Check the automation trace and that the target entities are available.
5. Try one triple, then pause before retrying. Because actions may toggle, two successful tests can cancel each other visually.

Diagnostics contain entity/config-entry identifiers, not Matter credentials. Review/redact them before posting publicly. Report bugs at [GitHub Issues](https://github.com/odggg/osazee-bilresa/issues) with Core version, remote model/firmware, gesture and whether the raw counter increased.

## Testing and beta status

The raw triple signal and actual light toggling have been observed on a physical dual-button remote. This is not a complete hardware certification for every gesture, every remote or all firmware versions.

The automated tests cover detector sequences, duplicates, diagnostic replay, startup rejection, stale/missing events and remote/endpoint isolation. Additional offline tests execute the actual blueprint's click branches with simulated event timing: combined double clicks in either button order, single/double/triple separation, both hold modes, multiple actions, empty assignments, remote isolation and invalid-state guards. They are not a substitute for Home Assistant runtime or hardware testing. See [development and release checklist](docs/development.md). Combined gestures, dimming and reload/reconnect behavior still need broader physical beta testing.

## License

[MIT](LICENSE), copyright © 2026 **OSAZEE**.
