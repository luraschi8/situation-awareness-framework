"""Tests for the collective ledger (ledger.py)."""

import json
import os
import shutil
import tempfile
import unittest

from skills.saf_core.lib.ledger import (
    is_action_done,
    sync_action,
    get_today_actions,
)
from skills.saf_core.lib.fs import load_json, save_json
from skills.saf_core.lib import paths


class _LedgerFixture(unittest.TestCase):
    """Base fixture providing a temp workspace with ledger path helpers."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self.shared = os.path.join(self.workspace, "memory", "shared")
        os.makedirs(self.shared)

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def ledger_path(self):
        return paths.resolve(paths.LEDGER_FILE, self.workspace)

    def write_ledger(self, data):
        save_json(self.ledger_path(), data)

    def read_ledger(self):
        return load_json(self.ledger_path())


class TestSyncAction(_LedgerFixture):

    def test_creates_ledger_and_records_action(self):
        success = sync_action(
            "test_agent", "morning_briefing", {"status": "ok"},
            workspace_root=self.workspace,
        )
        self.assertTrue(success)
        self.assertTrue(os.path.exists(self.ledger_path()))
        data = self.read_ledger()
        self.assertIn("morning_briefing", data["actions"])
        self.assertEqual(data["actions"]["morning_briefing"]["agent"], "test_agent")

    def test_stores_origin_when_provided(self):
        sync_action(
            "saf", "morning_briefing", {"status": "sent"},
            workspace_root=self.workspace, origin="registry",
        )
        data = self.read_ledger()
        self.assertEqual(data["actions"]["morning_briefing"]["origin"], "registry")

    def test_omits_origin_when_not_provided(self):
        sync_action(
            "saf", "morning_briefing", {"status": "sent"},
            workspace_root=self.workspace,
        )
        data = self.read_ledger()
        self.assertNotIn("origin", data["actions"]["morning_briefing"])


class TestGetTodayActions(_LedgerFixture):

    def test_returns_empty_when_no_ledger(self):
        result = get_today_actions(
            workspace_root=self.workspace, today_iso="2026-04-06",
        )
        self.assertEqual(result["already_done_today"], [])

    def test_returns_todays_actions(self):
        self.write_ledger({
            "last_updated": "2026-04-06T10:00:00Z",
            "actions": {
                "morning_briefing": {
                    "agent": "saf",
                    "timestamp": "2026-04-06T10:00:00Z",
                    "context": {},
                },
                "old_action": {
                    "agent": "saf",
                    "timestamp": "2026-04-05T10:00:00Z",
                    "context": {},
                },
            },
        })
        result = get_today_actions(
            workspace_root=self.workspace, today_iso="2026-04-06",
        )
        self.assertIn("morning_briefing", result["already_done_today"])
        self.assertNotIn("old_action", result["already_done_today"])


class TestIsActionDone(_LedgerFixture):

    def test_daily_true_when_done_today(self):
        self.write_ledger({
            "last_updated": "2026-04-06T10:00:00Z",
            "actions": {
                "briefing": {
                    "agent": "saf",
                    "timestamp": "2026-04-06T10:00:00Z",
                    "context": {},
                }
            },
        })
        self.assertTrue(is_action_done(
            "briefing", "daily",
            workspace_root=self.workspace, today_iso="2026-04-06",
        ))

    def test_daily_false_when_done_yesterday(self):
        self.write_ledger({
            "last_updated": "2026-04-05T10:00:00Z",
            "actions": {
                "briefing": {
                    "agent": "saf",
                    "timestamp": "2026-04-05T10:00:00Z",
                    "context": {},
                }
            },
        })
        self.assertFalse(is_action_done(
            "briefing", "daily",
            workspace_root=self.workspace, today_iso="2026-04-06",
        ))

    def test_weekly_true_when_done_earlier_this_week(self):
        # 2026-04-06 is Monday (week 15). 2026-04-08 is Wednesday (same week).
        self.write_ledger({
            "last_updated": "2026-04-06T10:00:00Z",
            "actions": {
                "weekly_review": {
                    "agent": "saf",
                    "timestamp": "2026-04-06T10:00:00Z",
                    "context": {},
                }
            },
        })
        self.assertTrue(is_action_done(
            "weekly_review", "weekly",
            workspace_root=self.workspace, today_iso="2026-04-08",
        ))

    def test_weekly_false_when_done_last_week(self):
        # 2026-04-03 is Friday (week 14). 2026-04-06 is Monday (week 15).
        self.write_ledger({
            "last_updated": "2026-04-03T10:00:00Z",
            "actions": {
                "weekly_review": {
                    "agent": "saf",
                    "timestamp": "2026-04-03T10:00:00Z",
                    "context": {},
                }
            },
        })
        self.assertFalse(is_action_done(
            "weekly_review", "weekly",
            workspace_root=self.workspace, today_iso="2026-04-06",
        ))

    def test_missing_action_returns_false(self):
        self.write_ledger({
            "last_updated": "",
            "actions": {},
        })
        self.assertFalse(is_action_done(
            "nonexistent", "daily",
            workspace_root=self.workspace, today_iso="2026-04-06",
        ))

    def test_unknown_frequency_falls_back_to_daily(self):
        self.write_ledger({
            "last_updated": "2026-04-06T10:00:00Z",
            "actions": {
                "something": {
                    "agent": "saf",
                    "timestamp": "2026-04-06T10:00:00Z",
                    "context": {},
                }
            },
        })
        self.assertTrue(is_action_done(
            "something", "hourly",
            workspace_root=self.workspace, today_iso="2026-04-06",
        ))


if __name__ == "__main__":
    unittest.main()
