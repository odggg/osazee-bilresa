"""Offline execution of blueprint click and dimming branches. Author: OSAZEE.

This deliberately small interpreter exercises the actual YAML and Jinja, not a
second gesture detector. It does not replace Home Assistant schema/runtime or
physical-device tests. Light calls are recorded, never sent to real devices.
"""
from datetime import datetime, timezone
from pathlib import Path
import re
from types import SimpleNamespace
import unittest

from jinja2 import StrictUndefined
from jinja2.nativetypes import NativeEnvironment
import yaml


class Input(str):
    """Keep blueprint input references distinct from literal strings."""


class BlueprintLoader(yaml.SafeLoader):
    pass


BlueprintLoader.add_constructor("!input", lambda loader, node: Input(loader.construct_scalar(node)))
BLUEPRINT = Path(__file__).resolve().parents[1] / "blueprints/automation/OSAZEE/ikea_bilresa_dual_button.yaml"
with BLUEPRINT.open(encoding="utf-8") as blueprint_file:
    CONFIG = yaml.load(blueprint_file, Loader=BlueprintLoader)


def defaults(inputs):
    result = {}
    for key, definition in inputs.items():
        if "input" in definition:
            result.update(defaults(definition["input"]))
        else:
            result[key] = definition["default"]
    return result


def timestamp(value, default=0):
    if isinstance(value, datetime):
        return value.timestamp()
    try:
        return float(value)
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(value).timestamp()
        except (TypeError, ValueError):
            return default


def native_event(at, entity, kind="multi_press_2", *, old="valid", restored=False,
                 advancing=True, missing=False):
    old_state = SimpleNamespace(state=str(999 + at) if old == "valid" else old, attributes={})
    new_state = SimpleNamespace(state=str(1000 + at) if advancing else old_state.state,
                                attributes={"event_type": kind, "restored": restored})
    return (at, "state_changed", {"entity_id": entity, "old_state": old_state,
                                  "new_state": None if missing else new_state})


def raw_event(at, entity):
    return (at, "osazee_bilresa_multipress_aborted",
            {"entity_id": entity, "event_type": "multi_press_aborted", "presses_at_least": 3})


class Stopped(Exception):
    pass


class ClickRunner:
    """Model a single HA run with timed bus events and marker-only actions."""

    def __init__(self, pending=(), **overrides):
        self.clock = 0.0
        self.pending = sorted(pending, key=lambda item: item[0])
        self.executed = []
        self.inputs = defaults(CONFIG["blueprint"]["input"])
        for key in self.inputs:
            if key.endswith("_action"):
                self.inputs[key] = [{"action": "test.marker", "data": {"gesture": key}}]
        self.inputs.update(remote_list=[
            {"name": "A", "button_1": "event.a1", "button_2": "event.a2"},
            {"name": "B", "button_1": "event.b1", "button_2": "event.b2"},
        ], raw_triple_enabled=True)
        self.inputs.update(overrides)
        self.context = {}
        self.env = NativeEnvironment(undefined=StrictUndefined)
        self.env.tests["match"] = lambda value, pattern: re.match(pattern, value) is not None
        self.env.globals.update(as_timestamp=timestamp,
                                now=lambda: datetime.fromtimestamp(1000 + self.clock, timezone.utc))

    def render(self, value):
        if isinstance(value, Input):
            return self.inputs[str(value)]
        if isinstance(value, str) and ("{{" in value or "{%" in value):
            return self.env.from_string(value).render(self.context)
        return value

    def truth(self, value):
        value = self.render(value)
        if isinstance(value, str):
            return value.strip().lower() == "true"
        return bool(value)

    def conditions(self, conditions):
        if isinstance(conditions, list):
            return all(self.conditions(item) for item in conditions)
        if isinstance(conditions, str):
            return self.truth(conditions)
        kind = conditions["condition"]
        if kind == "template":
            return self.truth(conditions["value_template"])
        if kind == "trigger":
            ids = conditions["id"]
            return self.context["trigger"].id in (ids if isinstance(ids, list) else [ids])
        if kind == "or":
            return any(self.conditions(item) for item in conditions["conditions"])
        if kind == "and":
            return self.conditions(conditions["conditions"])
        raise AssertionError(f"Unmodeled condition: {kind}")

    def variables(self, variables):
        for key, value in variables.items():
            self.context[key] = self.render(value)

    def receive_event(self, event_type, data):
        """Hook for simulated entity state updates; the click tests need none."""

    def wait(self, step):
        deadline = round(self.clock + float(self.render(step["timeout"]["seconds"])), 6)
        while self.pending and self.pending[0][0] <= deadline:
            at, event_type, data = self.pending.pop(0)
            self.clock = at
            self.receive_event(event_type, data)
            for trigger in step["wait_for_trigger"]:
                if not self.truth(trigger.get("enabled", True)):
                    continue
                if event_type == trigger["event_type"] and all(
                    data.get(key) == self.render(value) for key, value in trigger.get("event_data", {}).items()
                ):
                    self.context["wait"] = SimpleNamespace(completed=True, trigger=SimpleNamespace(
                        id=trigger["id"], event=SimpleNamespace(data=data)))
                    return
        self.clock = deadline
        self.context["wait"] = SimpleNamespace(completed=False, trigger=None)

    def sequence(self, sequence):
        for step in self.render(sequence):
            if "variables" in step:
                self.variables(step["variables"])
            elif "wait_for_trigger" in step:
                self.wait(step)
            elif "repeat" in step:
                if "for_each" in step["repeat"]:
                    previous_repeat = self.context.get("repeat")
                    for index, item in enumerate(self.render(step["repeat"]["for_each"]), 1):
                        self.context["repeat"] = SimpleNamespace(item=item, index=index)
                        self.sequence(step["repeat"]["sequence"])
                    if previous_repeat is None:
                        self.context.pop("repeat", None)
                    else:
                        self.context["repeat"] = previous_repeat
                    continue
                for _ in range(100):
                    if not self.conditions(step["repeat"]["while"]):
                        break
                    self.sequence(step["repeat"]["sequence"])
                else:
                    raise AssertionError("Unbounded wait loop")
            elif "if" in step:
                self.sequence(step.get("then" if self.conditions(step["if"]) else "else", []))
            elif "choose" in step:
                for branch in step["choose"]:
                    if self.conditions(branch["conditions"]):
                        self.sequence(branch["sequence"])
                        break
                else:
                    self.sequence(step.get("default", []))
            elif "sequence" in step:
                self.sequence(step["sequence"])
            elif "stop" in step:
                raise Stopped
            else:
                self.action(step)

    def action(self, step):
        if step.get("action") == "test.marker":
            self.executed.append(step["data"]["gesture"])
        else:
            raise AssertionError(f"Unmodeled action: {step}")

    def run(self, initial):
        at, event_type, data = initial
        self.clock = at
        self.receive_event(event_type, data)
        self.context["trigger"] = SimpleNamespace(
            id="remote_event" if event_type == "state_changed" else "raw_triple",
            platform="event", event=SimpleNamespace(data=data))
        self.variables(CONFIG["variables"])
        if self.conditions(CONFIG["conditions"]):
            try:
                self.sequence(CONFIG["actions"])
            except Stopped:
                pass
        return self.executed


class BlueprintClickTests(unittest.TestCase):
    def test_all_templates_compile_and_input_references_exist(self):
        runner = ClickRunner()

        def check(value):
            if isinstance(value, Input):
                self.assertIn(str(value), runner.inputs)
            elif isinstance(value, str) and ("{{" in value or "{%" in value):
                runner.env.from_string(value)
            elif isinstance(value, dict):
                for item in value.values():
                    check(item)
            elif isinstance(value, list):
                for item in value:
                    check(item)

        check(CONFIG)

    def test_new_input_has_empty_default_and_action_selector(self):
        item = CONFIG["blueprint"]["input"]["gesture_actions"]["input"]["double_both_action"]
        self.assertEqual(item["default"], [])
        self.assertEqual(item["selector"], {"action": {}})

    def test_both_double_orders_remotes_and_modes(self):
        for remote in ("a", "b"):
            for first, second in ((1, 2), (2, 1)):
                for mode in ("custom", "dim"):
                    with self.subTest(remote=remote, first=first, mode=mode):
                        runner = ClickRunner([native_event(.04, f"event.{remote}{second}")], hold_mode=mode)
                        self.assertEqual(runner.run(native_event(0, f"event.{remote}{first}")), ["double_both_action"])

    def test_combined_double_suppresses_individuals_even_if_empty(self):
        runner = ClickRunner([native_event(.02, "event.a2")], double_both_action=[])
        self.assertEqual(runner.run(native_event(0, "event.a1")), [])

    def test_combined_double_runs_multiple_actions_once_in_order(self):
        actions = [{"action": "test.marker", "data": {"gesture": name}} for name in ("first", "second")]
        runner = ClickRunner([native_event(.02, "event.a2"), native_event(.03, "event.a2", advancing=False)],
                             double_both_action=actions)
        self.assertEqual(runner.run(native_event(0, "event.a1")), ["first", "second"])

    def test_lone_double_preserves_individual_action(self):
        for button in (1, 2):
            self.assertEqual(ClickRunner().run(native_event(0, f"event.a{button}")), [f"double_button_{button}_action"])

    def test_other_remote_never_forms_combined_double(self):
        runner = ClickRunner([native_event(.02, "event.b2")])
        self.assertEqual(runner.run(native_event(0, "event.a1")), ["double_button_1_action"])

    def test_late_double_does_not_combine(self):
        runner = ClickRunner([native_event(.251, "event.a2")])
        self.assertEqual(runner.run(native_event(0, "event.a1")), ["double_button_1_action"])

    def test_configurable_window_is_honored(self):
        for cooldown, expected in ((100, "double_button_1_action"), (500, "double_both_action")):
            runner = ClickRunner([native_event(.2, "event.a2")], cooldown_ms=cooldown)
            self.assertEqual(runner.run(native_event(0, "event.a1")), [expected])

    def test_invalid_partner_events_do_not_combine(self):
        for kwargs in ({"old": "unavailable"}, {"old": "unknown"}, {"restored": True},
                       {"advancing": False}, {"missing": True}):
            with self.subTest(kwargs=kwargs):
                runner = ClickRunner([native_event(.02, "event.a2", **kwargs)])
                self.assertEqual(runner.run(native_event(0, "event.a1")), ["double_button_1_action"])

    def test_invalid_initial_events_do_nothing(self):
        for kwargs in ({"old": "unavailable"}, {"restored": True}, {"advancing": False}, {"missing": True}):
            runner = ClickRunner([native_event(.02, "event.a2")])
            self.assertEqual(runner.run(native_event(0, "event.a1", **kwargs)), [])

    def test_invalid_event_does_not_extend_original_pairing_deadline(self):
        runner = ClickRunner([native_event(.24, "event.a2", restored=True), native_event(.3, "event.a2")])
        self.assertEqual(runner.run(native_event(0, "event.a1")), ["double_button_1_action"])

    def test_invalid_event_followed_by_valid_partner(self):
        runner = ClickRunner([native_event(.02, "event.a2", restored=True), native_event(.04, "event.a2")])
        self.assertEqual(runner.run(native_event(0, "event.a1")), ["double_both_action"])

    def test_mixed_single_and_double_never_form_combined_double(self):
        runner = ClickRunner([native_event(.02, "event.a2", "multi_press_1")])
        self.assertEqual(runner.run(native_event(0, "event.a1")), ["double_button_1_action"])

    def test_legacy_third_clicks_keep_precedence(self):
        for first, second in ((1, 2), (2, 1)):
            for third, fourth in ((1, 2), (2, 1)):
                with self.subTest(first=first, third=third):
                    pending = [native_event(.02, f"event.a{second}"),
                               native_event(.04, f"event.a{third}", "multi_press_1"),
                               native_event(.06, f"event.a{fourth}", "multi_press_1")]
                    self.assertEqual(ClickRunner(pending).run(native_event(0, f"event.a{first}")), ["triple_both_action"])

    def test_one_legacy_third_click_does_not_also_run_combined_double(self):
        for first, second in ((1, 2), (2, 1)):
            for third in (1, 2):
                pending = [native_event(.02, f"event.a{second}"), native_event(.04, f"event.a{third}", "multi_press_1")]
                self.assertEqual(ClickRunner(pending).run(native_event(0, f"event.a{first}")), [f"triple_button_{third}_action"])

    def test_native_and_raw_triples_still_use_triple_actions(self):
        for raw in (False, True):
            for first, second in ((1, 2), (2, 1)):
                factory = raw_event if raw else lambda at, entity: native_event(at, entity, "multi_press_3")
                self.assertEqual(ClickRunner([factory(.02, f"event.a{second}")]).run(factory(0, f"event.a{first}")),
                                 ["triple_both_action"])

    def test_combined_single_unchanged(self):
        runner = ClickRunner([native_event(.02, "event.a2", "multi_press_1")])
        self.assertEqual(runner.run(native_event(0, "event.a1", "multi_press_1")), ["short_both_action"])

    def test_combined_hold_unchanged_in_both_modes(self):
        for mode in ("custom", "dim"):
            for first, second in ((1, 2), (2, 1)):
                runner = ClickRunner([native_event(.02, f"event.a{second}", "long_press")], hold_mode=mode)
                self.assertEqual(runner.run(native_event(0, f"event.a{first}", "long_press")), ["long_both_action"])

    def test_duplicate_and_incomplete_remote_configuration_do_nothing(self):
        for remotes in ([{"name": "Incomplete"}], [
            {"name": "Duplicate", "button_1": "event.a1", "button_2": "event.a1"}
        ]):
            runner = ClickRunner([native_event(.02, "event.a2")], remote_list=remotes)
            self.assertEqual(runner.run(native_event(0, "event.a1")), [])

    def test_fresh_run_does_not_inherit_pending_combination(self):
        first_run = ClickRunner()
        self.assertEqual(first_run.run(native_event(0, "event.a1")), ["double_button_1_action"])
        self.assertEqual(ClickRunner().run(native_event(0, "event.a2")), ["double_button_2_action"])


class DimmingRunner(ClickRunner):
    """Record light services, with a fake state registry and no hardware I/O."""

    def __init__(self, lights, pending=(), failed_entities=(), service_latency=0, **overrides):
        inputs = {"hold_mode": "dim", "light_entity": list(lights), "latency_compensation_seconds": 0}
        inputs.update(overrides)
        super().__init__(pending, **inputs)
        self.registry = {entity: SimpleNamespace(state=state, attributes={"brightness": brightness})
                         for entity, (state, brightness) in lights.items()}
        self.calls = []
        self.failed_entities = failed_entities
        self.service_latency = service_latency
        self.env.globals.update(
            states=lambda entity: self.registry[entity].state if entity in self.registry else "unknown",
            state_attr=lambda entity, attr: self.registry[entity].attributes.get(attr) if entity in self.registry else None,
            is_state=lambda entity, state: entity in self.registry and self.registry[entity].state == state,
            is_state_attr=lambda entity, attr, value: entity in self.registry and self.registry[entity].attributes.get(attr) == value,
            has_value=lambda entity: entity in self.registry and self.registry[entity].state not in ("unknown", "unavailable"),
        )

    def receive_event(self, event_type, data):
        if event_type == "state_changed":
            if data["new_state"] is None:
                self.registry.pop(data["entity_id"], None)
            else:
                self.registry[data["entity_id"]] = data["new_state"]

    def action(self, step):
        if step.get("action") != "light.turn_on":
            return super().action(step)
        entity = self.render(step["target"]["entity_id"])
        data = {key: self.render(value) for key, value in step["data"].items()}
        self.calls.append({"entity": entity, "data": data, "at": self.clock})
        self.clock = round(self.clock + self.service_latency, 6)
        while self.pending and self.pending[0][0] <= self.clock:
            _, event_type, event_data = self.pending.pop(0)
            self.receive_event(event_type, event_data)
        if entity in self.failed_entities:
            if not step.get("continue_on_error", False):
                raise AssertionError("One failed light must not abort the other lights")
            return
        # Model immediate initialization/final commands, not the physical ramp.
        if not data.get("transition") or data.get("transition") == self.inputs["release_transition_seconds"]:
            brightness = data.get("brightness", round(data.get("brightness_pct", 0) * 255 / 100))
            self.registry[entity] = SimpleNamespace(state="on" if brightness else "off",
                                                    attributes={"brightness": brightness})

    def final_brightness(self):
        return {call["entity"]: call["data"]["brightness"] for call in self.calls
                if call["data"].get("transition") == self.inputs["release_transition_seconds"]}


class BlueprintDimmingTests(unittest.TestCase):
    def runner(self, lights, direction=1, release=1.25, **overrides):
        return DimmingRunner(lights, [native_event(release, f"event.a{direction}", "long_release")], **overrides)

    def test_light_selector_supports_multiple_entities_and_preserves_input_key(self):
        item = CONFIG["blueprint"]["input"]["dimming"]["input"]["light_entity"]
        self.assertTrue(item["selector"]["entity"]["multiple"])
        self.assertEqual(item["default"], [])

    def test_multiple_lights_brighten_from_their_own_levels(self):
        runner = self.runner({"light.one": ("on", 50), "light.two": ("on", 150)})
        runner.run(native_event(0, "event.a1", "long_press"))
        self.assertEqual(runner.final_brightness(), {"light.one": 135, "light.two": 235})
        ramps = [call for call in runner.calls if call["at"] == .25]
        self.assertEqual([call["entity"] for call in ramps], ["light.one", "light.two"])
        self.assertAlmostEqual(ramps[0]["data"]["transition"], 205 / 255 * 3)
        self.assertAlmostEqual(ramps[1]["data"]["transition"], 105 / 255 * 3)

    def test_multiple_lights_dim_down_from_their_own_levels(self):
        runner = self.runner({"light.one": ("on", 100), "light.two": ("on", 200)}, direction=2)
        runner.run(native_event(0, "event.a2", "long_press"))
        self.assertEqual(runner.final_brightness(), {"light.one": 15, "light.two": 115})

    def test_legacy_scalar_selection_and_single_item_list_are_equivalent(self):
        for direction in (1, 2):
            results = []
            for selection in ("light.one", ["light.one"]):
                runner = self.runner({"light.one": ("on", 128)}, direction, light_entity=selection)
                runner.run(native_event(0, f"event.a{direction}", "long_press"))
                results.append(runner.calls)
            self.assertEqual(results[0], results[1])

    def test_unavailable_unknown_and_missing_lights_are_skipped(self):
        runner = self.runner({"light.one": ("on", 50), "light.offline": ("unavailable", None),
                              "light.unknown": ("unknown", None)},
                             light_entity=["light.one", "light.offline", "light.unknown", "light.missing"])
        runner.run(native_event(0, "event.a1", "long_press"))
        self.assertEqual({call["entity"] for call in runner.calls}, {"light.one"})

    def test_all_unavailable_or_empty_selection_does_not_call_lights(self):
        for selection in ([], "", None, ["light.offline"]):
            runner = self.runner({"light.offline": ("unavailable", None)}, light_entity=selection)
            runner.run(native_event(0, "event.a1", "long_press"))
            self.assertEqual(runner.calls, [])

    def test_off_light_starts_at_one_percent_when_brightening(self):
        runner = self.runner({"light.one": ("off", 200), "light.two": ("on", 50)})
        runner.run(native_event(0, "event.a1", "long_press"))
        self.assertEqual(runner.calls[0]["data"], {"brightness_pct": 1})
        self.assertEqual(runner.final_brightness(), {"light.one": 88, "light.two": 135})

    def test_off_lights_are_not_turned_on_by_dim_down(self):
        runner = self.runner({"light.one": ("off", 200), "light.two": ("on", 100)}, direction=2)
        runner.run(native_event(0, "event.a2", "long_press"))
        self.assertEqual({call["entity"] for call in runner.calls}, {"light.two"})
        self.assertEqual(runner.registry["light.one"].state, "off")

    def test_brightness_stays_between_zero_and_255(self):
        for direction, expected in ((1, 255), (2, 0)):
            runner = self.runner({"light.one": ("on", 128)}, direction, release=5)
            runner.run(native_event(0, f"event.a{direction}", "long_press"))
            self.assertEqual(runner.final_brightness(), {"light.one": expected})

    def test_duplicate_selection_is_deduplicated(self):
        runner = self.runner({"light.one": ("on", 128)}, light_entity=["light.one", "light.one"])
        runner.run(native_event(0, "event.a1", "long_press"))
        self.assertEqual(len(runner.calls), 2)

    def test_custom_mode_does_not_control_selected_lights(self):
        runner = self.runner({"light.one": ("on", 128)}, hold_mode="custom")
        self.assertEqual(runner.run(native_event(0, "event.a1", "long_press")), ["hold_button_1_action"])
        self.assertEqual(runner.calls, [])

    def test_combined_hold_does_not_start_dimming(self):
        runner = DimmingRunner({"light.one": ("on", 128)}, [native_event(.1, "event.a2", "long_press")])
        self.assertEqual(runner.run(native_event(0, "event.a1", "long_press")), ["long_both_action"])
        self.assertEqual(runner.calls, [])

    def test_early_release_before_pairing_window_ends_does_not_dim(self):
        runner = self.runner({"light.one": ("on", 128)}, release=.1)
        runner.run(native_event(0, "event.a1", "long_press"))
        self.assertEqual(runner.calls, [])

    def test_invalid_or_other_remote_release_does_not_finish_dimming(self):
        pending = [native_event(.5, "event.b1", "long_release"),
                   native_event(.75, "event.a1", "long_release", restored=True),
                   native_event(1.25, "event.a1", "long_release")]
        runner = DimmingRunner({"light.one": ("on", 50)}, pending)
        runner.run(native_event(0, "event.a1", "long_press"))
        self.assertEqual(runner.final_brightness(), {"light.one": 135})

    def test_missing_release_has_a_bounded_timeout(self):
        runner = DimmingRunner({"light.one": ("on", 50)})
        runner.run(native_event(0, "event.a1", "long_press"))
        self.assertAlmostEqual(runner.clock, 30.25)
        self.assertEqual(runner.final_brightness(), {"light.one": 255})

    def test_release_during_service_calls_is_not_missed(self):
        for direction in (1, 2):
            runner = DimmingRunner({"light.one": ("on", 50), "light.two": ("on", 150)},
                                   [native_event(.3, f"event.a{direction}", "long_release")], service_latency=.1)
            runner.run(native_event(0, f"event.a{direction}", "long_press"))
            self.assertLess(runner.clock, 1)
            self.assertEqual(set(runner.final_brightness()), {"light.one", "light.two"})

    def test_light_becoming_unavailable_before_release_is_not_called_again(self):
        unavailable = (.5, "state_changed", {"entity_id": "light.one", "old_state": None,
                                            "new_state": SimpleNamespace(state="unavailable", attributes={})})
        runner = DimmingRunner({"light.one": ("on", 50), "light.two": ("on", 150)},
                              [unavailable, native_event(1.25, "event.a1", "long_release")])
        runner.run(native_event(0, "event.a1", "long_press"))
        self.assertEqual(runner.final_brightness(), {"light.two": 235})

    def test_one_failed_light_does_not_abort_remaining_targets(self):
        runner = self.runner({"light.one": ("on", 50), "light.two": ("on", 150)}, failed_entities=["light.one"])
        runner.run(native_event(0, "event.a1", "long_press"))
        self.assertEqual(runner.final_brightness()["light.two"], 235)

    def test_ramp_time_latency_compensation_and_release_transition(self):
        runner = self.runner({"light.one": ("on", 50)}, brightness_ramp_seconds=5,
                             latency_compensation_seconds=.2, release_transition_seconds=.5)
        runner.run(native_event(0, "event.a1", "long_press"))
        self.assertEqual(runner.final_brightness(), {"light.one": 111})
        self.assertEqual(runner.calls[-1]["data"]["transition"], .5)


if __name__ == "__main__":
    unittest.main()
