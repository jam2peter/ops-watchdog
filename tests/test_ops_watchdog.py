import json
import tempfile
import unittest
from pathlib import Path

from src import ops_watchdog


class OpsWatchdogTests(unittest.TestCase):
    def setUp(self):
        self.current = {
            "audit:workflow": {
                "source": "audit",
                "id": "workflow",
                "name": "Workflow",
                "status": "PASS",
            }
        }

    def test_baseline_is_silent(self):
        decision = ops_watchdog.decide(None, self.current)
        self.assertFalse(decision["notify"])
        self.assertEqual(decision["reason"], "baseline_created")

    def test_unchanged_is_silent(self):
        previous = {
            "schema_version": 1,
            "systems": self.current,
        }
        decision = ops_watchdog.decide(previous, self.current)
        self.assertFalse(decision["notify"])
        self.assertEqual(decision["reason"], "no_change")

    def test_worsening_notifies_once(self):
        previous = {
            "schema_version": 1,
            "systems": self.current,
        }
        changed = {
            "audit:workflow": {
                **self.current["audit:workflow"],
                "status": "DEGRADED",
            }
        }
        decision = ops_watchdog.decide(previous, changed)
        self.assertTrue(decision["notify"])
        self.assertEqual(len(decision["events"]), 1)
        self.assertEqual(decision["events"][0]["transition"], "worsened")

    def test_recovery_notifies(self):
        previous = {
            "schema_version": 1,
            "systems": {
                "monitor:cpu": {
                    "source": "monitor",
                    "id": "cpu",
                    "name": "CPU",
                    "status": "BLOCKED",
                }
            },
        }
        current = {
            "monitor:cpu": {
                "source": "monitor",
                "id": "cpu",
                "name": "CPU",
                "status": "PASS",
            }
        }
        decision = ops_watchdog.decide(previous, current)
        self.assertTrue(decision["notify"])
        self.assertEqual(decision["events"][0]["transition"], "recovered")

    def test_multiple_sources_are_namespaced(self):
        sources = {
            "audit": {
                "schema_version": 1,
                "systems": [{"id": "up", "name": "Audit up", "status": "PASS"}],
            },
            "monitor": {
                "schema_version": 1,
                "systems": [{"id": "up", "name": "Monitor up", "status": "PASS"}],
            },
        }
        normalized = ops_watchdog.normalize_sources(sources)
        self.assertIn("audit:up", normalized)
        self.assertIn("monitor:up", normalized)

    def test_state_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text(
                json.dumps({"schema_version": 1, "systems": self.current}),
                encoding="utf-8",
            )
            state = ops_watchdog.load_state(path)
            self.assertEqual(state["systems"], self.current)


if __name__ == "__main__":
    unittest.main()
