"""Tests for the proactive action registry (actions.py)."""

import json
import os
import tempfile
import unittest

from skills.saf_core.lib.actions import get_applicable_actions, load_actions


def _write_registry(workspace, registry):
    """Write a proactive-actions.json into a temporary workspace."""
    shared = os.path.join(workspace, "memory", "shared")
    os.makedirs(shared, exist_ok=True)
    with open(os.path.join(shared, "proactive-actions.json"), "w") as f:
        json.dump(registry, f)


def _temporal(phase="MORNING", day_type="workday", weekday_number=0):
    """Build a minimal temporal context dict for testing."""
    return {
        "day_phase": phase,
        "day_type": day_type,
        "weekday_number": weekday_number,
        "iso_date": "2026-04-06",
    }


class TestLoadActions(unittest.TestCase):

    def test_returns_empty_when_no_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = load_actions(workspace_root=tmp)
            self.assertEqual(result, {"actions": {}})

    def test_reads_valid_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = {
                "actions": {
                    "morning_briefing": {
                        "description": "Good morning",
                        "trigger": {"phase": ["MORNING"]},
                        "frequency": "daily",
                        "domains": ["work"],
                        "enabled": True,
                    }
                }
            }
            _write_registry(tmp, registry)
            result = load_actions(workspace_root=tmp)
            self.assertIn("morning_briefing", result["actions"])


class TestGetApplicableActions(unittest.TestCase):

    def _setup(self, actions_dict):
        """Write a registry and return the workspace path."""
        self._tmp = tempfile.mkdtemp()
        _write_registry(self._tmp, {"actions": actions_dict})
        return self._tmp

    def tearDown(self):
        if hasattr(self, "_tmp"):
            import shutil
            shutil.rmtree(self._tmp, ignore_errors=True)

    def test_applicable_morning_workday(self):
        ws = self._setup({
            "morning_briefing": {
                "description": "Briefing",
                "trigger": {"phase": ["MORNING"], "day_type": "workday"},
                "frequency": "daily",
                "domains": ["work"],
                "enabled": True,
            }
        })
        result = get_applicable_actions(_temporal(), workspace_root=ws)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, "morning_briefing")
        self.assertEqual(result[0].frequency, "daily")
        self.assertEqual(result[0].domains, ["work"])

    def test_filters_wrong_phase(self):
        ws = self._setup({
            "morning_briefing": {
                "description": "Briefing",
                "trigger": {"phase": ["MORNING"]},
                "enabled": True,
            }
        })
        result = get_applicable_actions(
            _temporal(phase="EVENING"), workspace_root=ws,
        )
        self.assertEqual(len(result), 0)

    def test_filters_wrong_day_type(self):
        ws = self._setup({
            "morning_briefing": {
                "description": "Briefing",
                "trigger": {"phase": ["MORNING"], "day_type": "workday"},
                "enabled": True,
            }
        })
        result = get_applicable_actions(
            _temporal(day_type="rest_day"), workspace_root=ws,
        )
        self.assertEqual(len(result), 0)

    def test_day_of_week_match(self):
        ws = self._setup({
            "weekly_review": {
                "description": "Review",
                "trigger": {"day_of_week": [0]},
                "frequency": "weekly",
                "enabled": True,
            }
        })
        result = get_applicable_actions(
            _temporal(weekday_number=0), workspace_root=ws,
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, "weekly_review")

    def test_day_of_week_no_match(self):
        ws = self._setup({
            "weekly_review": {
                "description": "Review",
                "trigger": {"day_of_week": [0]},
                "frequency": "weekly",
                "enabled": True,
            }
        })
        result = get_applicable_actions(
            _temporal(weekday_number=3), workspace_root=ws,
        )
        self.assertEqual(len(result), 0)

    def test_disabled_action_excluded(self):
        ws = self._setup({
            "morning_briefing": {
                "description": "Briefing",
                "trigger": {"phase": ["MORNING"]},
                "enabled": False,
            }
        })
        result = get_applicable_actions(_temporal(), workspace_root=ws)
        self.assertEqual(len(result), 0)

    def test_missing_trigger_matches_any(self):
        ws = self._setup({
            "always_action": {
                "description": "Always available",
                "trigger": {},
                "enabled": True,
            }
        })
        result = get_applicable_actions(
            _temporal(phase="NIGHT", day_type="rest_day", weekday_number=5),
            workspace_root=ws,
        )
        self.assertEqual(len(result), 1)

    def test_requires_field_passed_through(self):
        ws = self._setup({
            "meeting_prep": {
                "description": "Prepare for meeting",
                "trigger": {"requires": "calendar_event"},
                "enabled": True,
            }
        })
        result = get_applicable_actions(_temporal(), workspace_root=ws)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].requires_trigger, "calendar_event")

    def test_all_conditions_and_together(self):
        ws = self._setup({
            "monday_morning_work": {
                "description": "Only Mon morning workdays",
                "trigger": {
                    "phase": ["MORNING"],
                    "day_type": "workday",
                    "day_of_week": [0],
                },
                "enabled": True,
            }
        })
        # All match
        result = get_applicable_actions(
            _temporal(phase="MORNING", day_type="workday", weekday_number=0),
            workspace_root=ws,
        )
        self.assertEqual(len(result), 1)

        # Phase wrong
        result = get_applicable_actions(
            _temporal(phase="EVENING", day_type="workday", weekday_number=0),
            workspace_root=ws,
        )
        self.assertEqual(len(result), 0)

        # Day type wrong
        result = get_applicable_actions(
            _temporal(phase="MORNING", day_type="rest_day", weekday_number=0),
            workspace_root=ws,
        )
        self.assertEqual(len(result), 0)

        # Weekday wrong
        result = get_applicable_actions(
            _temporal(phase="MORNING", day_type="workday", weekday_number=3),
            workspace_root=ws,
        )
        self.assertEqual(len(result), 0)


if __name__ == "__main__":
    unittest.main()
