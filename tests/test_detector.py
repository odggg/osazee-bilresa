"""Detector regression tests. Author: OSAZEE."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

_spec = importlib.util.spec_from_file_location(
    "bilresa_detector", Path(__file__).resolve().parents[1]
    / "custom_components" / "osazee_bilresa" / "detector.py"
)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
Detector = _module.Detector


class DetectorTests(unittest.TestCase):
    def event(self, number, kind, data, node=10, endpoint=1, cluster=59):
        return SimpleNamespace(node_id=node, endpoint_id=endpoint,
                               cluster_id=cluster, event_id=kind,
                               event_number=number, data=data)

    def run_sequence(self, detector, start=1, node=10, endpoint=1,
                     times=None, completion=0, active=True, cluster=59):
        rows = [
            (1, {"newPosition": 1}),
            (3, {"previousPosition": 1}),
            (1, {"newPosition": 1}),
            (5, {"currentNumberOfPressesCounted": 2}),
            (3, {"previousPosition": 1}),
            (6, {"previousPosition": 1, "totalNumberOfPressesCounted": completion}),
        ]
        times = times or [0, .1, .2, .21, .3, .4]
        return [detector.feed(self.event(start+i, kind, data, node, endpoint, cluster),
                              times[i], active=active)
                for i, (kind, data) in enumerate(rows)]

    def test_valid_aborted_sequence(self):
        self.assertEqual(self.run_sequence(Detector()), [False]*5 + [True])

    def test_duplicate_sequence(self):
        detector = Detector()
        self.run_sequence(detector)
        self.assertEqual(self.run_sequence(detector), [False]*6)

    def test_duplicate_completion(self):
        detector = Detector()
        self.run_sequence(detector)
        self.assertFalse(detector.feed(self.event(
            6, 6, {"previousPosition": 1, "totalNumberOfPressesCounted": 0}), .5))

    def test_history_is_only_a_floor(self):
        detector = Detector()
        detector.seed([{"node_id": 10, "event_number": 6}])
        self.assertEqual(self.run_sequence(detector), [False]*6)
        self.assertTrue(self.run_sequence(detector, start=7)[-1])

    def test_seed_uses_maximum_not_last(self):
        detector = Detector()
        detector.seed([{"node_id": 10, "event_number": 30},
                       {"node_id": 10, "event_number": 6}])
        self.assertEqual(self.run_sequence(detector, start=7), [False]*6)

    def test_stale_completion(self):
        self.assertEqual(self.run_sequence(Detector(), times=[0,.1,.2,.21,.3,4]),
                         [False]*6)

    def test_delayed_second_press(self):
        self.assertEqual(self.run_sequence(Detector(), times=[0,.1,4,4.1,4.2,4.3]),
                         [False]*6)

    def test_startup_is_inactive(self):
        detector = Detector()
        self.assertEqual(self.run_sequence(detector, active=False), [False]*6)
        self.assertTrue(self.run_sequence(detector, start=7)[-1])

    def test_no_initial_sequence(self):
        self.assertFalse(Detector().feed(self.event(
            1, 6, {"previousPosition": 1, "totalNumberOfPressesCounted": 0}), 0))

    def test_only_one_initial_press(self):
        detector = Detector()
        rows = [(1, {"newPosition": 1}),
                (5, {"currentNumberOfPressesCounted": 2}),
                (3, {"previousPosition": 1}),
                (6, {"previousPosition": 1, "totalNumberOfPressesCounted": 0})]
        self.assertFalse(any(detector.feed(self.event(i+1,k,d), i*.1)
                             for i,(k,d) in enumerate(rows)))

    def test_no_ongoing_event(self):
        detector = Detector()
        for i, kind in enumerate([1, 3, 1, 3]):
            detector.feed(self.event(i+1, kind, {"newPosition":1,"previousPosition":1}), i*.1)
        self.assertFalse(detector.feed(self.event(
            5,6,{"previousPosition":1,"totalNumberOfPressesCounted":0}),.5))

    def test_ongoing_count_must_be_two(self):
        detector = Detector()
        for i, kind in enumerate([1,3,1,5,3]):
            detector.feed(self.event(i+1,kind,{"newPosition":1,"previousPosition":1,
                           "currentNumberOfPressesCounted":1}),i*.1)
        self.assertFalse(detector.feed(self.event(
            6,6,{"previousPosition":1,"totalNumberOfPressesCounted":0}),.6))

    def test_single_completion_rejected(self):
        self.assertFalse(self.run_sequence(Detector(), completion=1)[-1])

    def test_double_completion_rejected(self):
        self.assertFalse(self.run_sequence(Detector(), completion=2)[-1])

    def test_release_required(self):
        detector = Detector()
        for i,kind in enumerate([1,3,1,5]):
            detector.feed(self.event(i+1,kind,{"newPosition":1,"previousPosition":1,
                           "currentNumberOfPressesCounted":2}),i*.1)
        self.assertFalse(detector.feed(self.event(
            5,6,{"previousPosition":1,"totalNumberOfPressesCounted":0}),.5))

    def test_wrong_cluster_rejected(self):
        self.assertEqual(self.run_sequence(Detector(),cluster=6),[False]*6)

    def test_wrong_endpoint_rejected(self):
        self.assertEqual(self.run_sequence(Detector(),endpoint=3),[False]*6)

    def test_remote_and_endpoint_isolation(self):
        detector=Detector()
        self.assertTrue(self.run_sequence(detector,node=10,endpoint=1)[-1])
        self.assertTrue(self.run_sequence(detector,node=11,endpoint=1)[-1])
        self.assertTrue(self.run_sequence(detector,node=10,endpoint=2)[-1])

    def test_reset_removes_pending(self):
        detector=Detector()
        for i,kind in enumerate([1,3,1,5,3]):
            detector.feed(self.event(i+1,kind,{"newPosition":1,"previousPosition":1,
                           "currentNumberOfPressesCounted":2}),i*.1)
        detector.reset_node(10)
        self.assertFalse(detector.feed(self.event(
            6,6,{"previousPosition":1,"totalNumberOfPressesCounted":0}),.6))

    def test_long_press_cancels(self):
        detector=Detector()
        for i,kind in enumerate([1,3,1,5,2,3]):
            detector.feed(self.event(i+1,kind,{"newPosition":1,"previousPosition":1,
                           "currentNumberOfPressesCounted":2}),i*.1)
        self.assertFalse(detector.feed(self.event(
            7,6,{"previousPosition":1,"totalNumberOfPressesCounted":0}),.7))

    def test_normal_completion_clears_pending(self):
        detector=Detector()
        self.run_sequence(detector,completion=2)
        self.assertFalse(detector.feed(self.event(
            7,6,{"previousPosition":1,"totalNumberOfPressesCounted":0}),.7))

    def test_new_detector_does_not_restore_pending(self):
        self.run_sequence(Detector())
        self.assertFalse(Detector().feed(self.event(
            100,6,{"previousPosition":1,"totalNumberOfPressesCounted":0}),.7))

    def test_changed_event_timestamps_do_not_affect_detection(self):
        detector=Detector()
        results=[]
        rows=[(1,{"newPosition":1}),(3,{"previousPosition":1}),
              (1,{"newPosition":1}),(5,{"currentNumberOfPressesCounted":2}),
              (3,{"previousPosition":1}),
              (6,{"previousPosition":1,"totalNumberOfPressesCounted":0})]
        for i,(kind,data) in enumerate(rows):
            event=self.event(i+1,kind,data)
            event.timestamp=[9000,0,-100,1,5,9500][i]
            results.append(detector.feed(event,i*.1))
        self.assertEqual(results,[False]*5+[True])

    def test_fresh_next_gesture(self):
        detector=Detector()
        self.assertTrue(self.run_sequence(detector)[-1])
        self.assertTrue(self.run_sequence(detector,start=7,
                        times=[2,2.1,2.2,2.21,2.3,2.4])[-1])


if __name__ == "__main__":
    unittest.main()
