"""Offline execution of the blueprint's click branches. Author: OSAZEE.

This deliberately small interpreter exercises the actual YAML and Jinja, not a
second gesture detector. It does not replace Home Assistant schema/runtime or
physical-device tests. Only the action types used by the click branches are modeled.
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

    def wait(self, step):
        deadline = round(self.clock + float(self.render(step["timeout"]["seconds"])), 6)
        while self.pending and self.pending[0][0] <= deadline:
            at, event_type, data = self.pending.pop(0)
            self.clock = at
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
            elif step.get("action") == "test.marker":
                self.executed.append(step["data"]["gesture"])
            else:
                raise AssertionError(f"Unmodeled action: {step}")

    def run(self, initial):
        at, event_type, data = initial
        self.clock = at
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


if __name__ == "__main__":
    unittest.main()
