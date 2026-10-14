"""Conservative live-only BILRESA aborted multipress recognition. Author: OSAZEE."""

class Detector:
    """Accept a fresh short-press sequence once; never replay diagnostics."""

    def __init__(self, window=3.0):
        self.window = window
        self.highwater = {}
        self.baseline = {}
        self.pending = {}

    def seed(self, events):
        for event in events:
            node = int(event["node_id"])
            self.baseline[node] = max(self.baseline.get(node, -1), int(event["event_number"]))
        self.pending.clear()

    def reset_node(self, node):
        for key in list(self.pending):
            if key[0] == node:
                self.pending.pop(key, None)

    def feed(self, event, now, active=True):
        node, endpoint = int(event.node_id), int(event.endpoint_id)
        key = (node, endpoint)
        number = int(event.event_number)
        if number <= max(self.baseline.get(node, -1), self.highwater.get(key, -1)):
            return False
        self.highwater[key] = number
        if not active or event.cluster_id != 59 or endpoint not in (1, 2):
            self.pending.pop(key, None)
            return False
        kind, data = int(event.event_id), event.data or {}
        pending = self.pending.get(key)
        if pending and not 0 <= now - pending["started"] <= self.window:
            self.pending.pop(key, None)
            pending = None
        if kind == 1 and data.get("newPosition") == 1:
            if pending is None:
                self.pending[key] = {"started": now, "initials": 1, "ongoing": False, "released": False}
            else:
                pending["initials"] += 1
                pending["released"] = False
        elif kind == 5 and pending and pending["initials"] >= 2:
            pending["ongoing"] = data.get("currentNumberOfPressesCounted") == 2
        elif kind == 3 and pending:
            pending["released"] = data.get("previousPosition") == 1
        elif kind in (2, 4):
            self.pending.pop(key, None)
        elif kind == 6:
            self.pending.pop(key, None)
            return bool(pending and pending["ongoing"] and pending["released"]
                        and data.get("previousPosition") == 1
                        and data.get("totalNumberOfPressesCounted") == 0)
        return False
