"""Tests for saf_core.pipeline orchestration."""

import json
import os
import tempfile
import time
import unittest
from unittest.mock import patch

from skills.saf_core.lib import pipeline
from skills.saf_core.lib.context import SAFContext


class StubHost:
    """Minimal SAFHost implementation for tests."""

    def __init__(self, workspace_root):
        self._root = workspace_root
        self.logs = []

    def workspace_root(self):
        return self._root

    def log(self, level, message):
        self.logs.append((level, message))


class _WorkspaceFixture(unittest.TestCase):
    """Base class providing a temporary SAF workspace for pipeline tests."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.host = StubHost(self.tmpdir)
        # Create memory/shared/ so config files can be written
        os.makedirs(os.path.join(self.tmpdir, "memory", "shared"), exist_ok=True)
        os.makedirs(os.path.join(self.tmpdir, "memory", "domains"), exist_ok=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def write_config(self, filename, data):
        path = os.path.join(self.tmpdir, "memory", "shared", filename)
        with open(path, "w") as f:
            json.dump(data, f)

    def create_domain(self, name, files):
        """Creates a domain directory with empty files."""
        domain_path = os.path.join(self.tmpdir, "memory", "domains", name)
        os.makedirs(domain_path, exist_ok=True)
        for filename in files:
            with open(os.path.join(domain_path, filename), "w") as f:
                f.write(f"# {filename}\n")
        return domain_path


class TestPipelineProcess(_WorkspaceFixture):
    """Tests for pipeline.process() — the core orchestrator."""

    def test_returns_saf_context(self):
        ctx = pipeline.process("Hello", self.host)
        self.assertIsInstance(ctx, SAFContext)
        self.assertIn("utc_time", ctx.temporal)
        self.assertIn("day_phase", ctx.temporal)

    def test_empty_message_yields_no_domains(self):
        self.create_domain("work", ["setup.md"])
        ctx = pipeline.process("", self.host)
        # Empty message should not match any keyword, so no candidate domains
        self.assertEqual(ctx.candidate_domains, [])

    def test_matching_keyword_yields_domain(self):
        self.create_domain("work", ["setup.md", "meetings.md"])
        ctx = pipeline.process("I have a meeting tomorrow", self.host)
        domain_names = [c.name for c in ctx.candidate_domains]
        self.assertIn("work", domain_names)
        work = next(c for c in ctx.candidate_domains if c.name == "work")
        self.assertIn("setup.md", work.files)
        self.assertIn("meetings.md", work.files)

    def test_missing_domain_dir_is_omitted_gracefully(self):
        # router.py matches "work" domain by default, but no directory exists
        ctx = pipeline.process("I have a meeting tomorrow", self.host)
        self.assertEqual(ctx.candidate_domains, [])

    def test_dedup_populated_from_ledger(self):
        # Write a ledger entry for today
        today = time.strftime("%Y-%m-%d", time.gmtime())
        ledger_data = {
            "last_updated": f"{today}T10:00:00Z",
            "actions": {
                "morning_briefing": {
                    "agent": "saf",
                    "timestamp": f"{today}T08:00:00Z",
                    "context": {"status": "sent"},
                }
            },
        }
        self.write_config("collective-ledger.json", ledger_data)

        ctx = pipeline.process("Hello", self.host)
        self.assertIn("morning_briefing", ctx.dedup["already_done_today"])
        # Already-done actions should be blocked
        self.assertIn("morning_briefing", ctx.blocked_actions)
        self.assertEqual(
            ctx.blocked_actions["morning_briefing"], "already_done_today"
        )

    def test_instructions_mention_action_tag_syntax(self):
        ctx = pipeline.process("Hello", self.host)
        joined = "\n".join(ctx.agent_instructions)
        self.assertIn("<saf-action", joined)
        self.assertIn("status=", joined)

    def test_instructions_mention_domains_when_matched(self):
        self.create_domain("work", ["setup.md"])
        ctx = pipeline.process("I have a meeting", self.host)
        joined = "\n".join(ctx.agent_instructions)
        self.assertIn("work", joined)

    def test_instructions_mention_blocked_actions(self):
        today = time.strftime("%Y-%m-%d", time.gmtime())
        self.write_config(
            "collective-ledger.json",
            {
                "last_updated": f"{today}T10:00:00Z",
                "actions": {
                    "morning_briefing": {
                        "agent": "saf",
                        "timestamp": f"{today}T08:00:00Z",
                        "context": {},
                    }
                },
            },
        )
        ctx = pipeline.process("Hello", self.host)
        joined = "\n".join(ctx.agent_instructions)
        self.assertIn("morning_briefing", joined)

    def test_candidate_domains_excludes_hidden_files(self):
        # Files starting with _ (like _index.md) should not be listed
        self.create_domain("work", ["setup.md", "_index.md"])
        ctx = pipeline.process("I have a meeting", self.host)
        work = next(c for c in ctx.candidate_domains if c.name == "work")
        self.assertIn("setup.md", work.files)
        self.assertNotIn("_index.md", work.files)


class TestPipelineProactiveActions(_WorkspaceFixture):
    """Tests for proactive action registry integration in the pipeline."""

    def _write_registry(self, actions_dict):
        self.write_config("proactive-actions.json", {"actions": actions_dict})

    def _morning_workday_context(self):
        """Patch temporal to return a consistent MORNING/workday context."""
        return patch(
            "skills.saf_core.lib.temporal.get_temporal_context",
            return_value={
                "utc_time": "2026-04-06T08:00:00+00:00",
                "timezone": "UTC",
                "local_time": "2026-04-06T08:00:00+00:00",
                "hour": 8,
                "day_phase": "MORNING",
                "day_of_week": "Monday",
                "day_type": "workday",
                "iso_date": "2026-04-06",
                "weekday_number": 0,
            },
        )

    def test_available_actions_populated_from_registry(self):
        self._write_registry({
            "morning_briefing": {
                "description": "Summarize the day",
                "trigger": {"phase": ["MORNING"], "day_type": "workday"},
                "frequency": "daily",
                "domains": ["work"],
                "enabled": True,
            }
        })
        with self._morning_workday_context():
            ctx = pipeline.process("Hello", self.host)
        self.assertEqual(len(ctx.available_actions), 1)
        self.assertEqual(ctx.available_actions[0].id, "morning_briefing")

    def test_available_actions_empty_when_no_registry(self):
        with self._morning_workday_context():
            ctx = pipeline.process("Hello", self.host)
        self.assertEqual(ctx.available_actions, [])

    def test_done_action_moves_to_blocked(self):
        self._write_registry({
            "morning_briefing": {
                "description": "Summarize the day",
                "trigger": {"phase": ["MORNING"], "day_type": "workday"},
                "frequency": "daily",
                "domains": ["work"],
                "enabled": True,
            }
        })
        self.write_config("collective-ledger.json", {
            "last_updated": "2026-04-06T07:00:00Z",
            "actions": {
                "morning_briefing": {
                    "agent": "saf",
                    "timestamp": "2026-04-06T07:00:00Z",
                    "context": {"status": "sent"},
                }
            },
        })
        with self._morning_workday_context():
            ctx = pipeline.process("Hello", self.host)
        self.assertEqual(ctx.available_actions, [])
        self.assertIn("morning_briefing", ctx.blocked_actions)
        self.assertEqual(
            ctx.blocked_actions["morning_briefing"], "already_done_daily",
        )

    def test_weekly_action_blocked_when_done_this_week(self):
        self._write_registry({
            "weekly_review": {
                "description": "Weekly review",
                "trigger": {"phase": ["MORNING"], "day_of_week": [0]},
                "frequency": "weekly",
                "domains": ["work"],
                "enabled": True,
            }
        })
        # Done earlier this week (same ISO week as 2026-04-06)
        self.write_config("collective-ledger.json", {
            "last_updated": "2026-04-06T07:00:00Z",
            "actions": {
                "weekly_review": {
                    "agent": "saf",
                    "timestamp": "2026-04-06T07:00:00Z",
                    "context": {"status": "sent"},
                }
            },
        })
        with self._morning_workday_context():
            ctx = pipeline.process("Hello", self.host)
        self.assertEqual(ctx.available_actions, [])
        self.assertIn("weekly_review", ctx.blocked_actions)
        self.assertEqual(
            ctx.blocked_actions["weekly_review"], "already_done_weekly",
        )

    def test_action_domains_merged_with_message_domains(self):
        self.create_domain("work", ["setup.md"])
        self.create_domain("projects", ["roadmap.md"])
        self._write_registry({
            "morning_briefing": {
                "description": "Briefing",
                "trigger": {"phase": ["MORNING"]},
                "frequency": "daily",
                "domains": ["projects"],
                "enabled": True,
            }
        })
        with self._morning_workday_context():
            # "meeting" triggers the "work" domain via message routing
            ctx = pipeline.process("I have a meeting", self.host)
        domain_names = [c.name for c in ctx.candidate_domains]
        self.assertIn("work", domain_names)
        self.assertIn("projects", domain_names)

    def test_instructions_mention_available_actions(self):
        self._write_registry({
            "morning_briefing": {
                "description": "Briefing",
                "trigger": {"phase": ["MORNING"]},
                "frequency": "daily",
                "enabled": True,
            }
        })
        with self._morning_workday_context():
            ctx = pipeline.process("Hello", self.host)
        joined = "\n".join(ctx.agent_instructions)
        self.assertIn("morning_briefing", joined)
        self.assertIn("Available proactive actions", joined)


class TestPipelineRecordAction(_WorkspaceFixture):
    """Tests for pipeline.record_action() — Step 6 ledger write."""

    def test_records_action_to_ledger(self):
        pipeline.record_action("test_action", "sent", self.host)
        ledger_path = os.path.join(
            self.tmpdir, "memory", "shared", "collective-ledger.json"
        )
        self.assertTrue(os.path.exists(ledger_path))
        with open(ledger_path) as f:
            data = json.load(f)
        self.assertIn("test_action", data["actions"])
        self.assertEqual(
            data["actions"]["test_action"]["context"], {"status": "sent"}
        )

    def test_record_then_dedup_roundtrip(self):
        pipeline.record_action("roundtrip_action", "sent", self.host)
        ctx = pipeline.process("Hello", self.host)
        self.assertIn("roundtrip_action", ctx.dedup["already_done_today"])
        self.assertIn("roundtrip_action", ctx.blocked_actions)

    def test_record_overwrites_same_action_id(self):
        pipeline.record_action("my_action", "pending", self.host)
        pipeline.record_action("my_action", "sent", self.host)
        ledger_path = os.path.join(
            self.tmpdir, "memory", "shared", "collective-ledger.json"
        )
        with open(ledger_path) as f:
            data = json.load(f)
        self.assertEqual(
            data["actions"]["my_action"]["context"]["status"], "sent"
        )


if __name__ == "__main__":
    unittest.main()
