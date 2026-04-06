"""Tests for the OpenClaw adapter implementation."""

import json
import os
import shutil
import tempfile
import time
import unittest

from skills.saf_core.lib.context import SAFContext
from skills.saf_core.lib import paths
from skills.saf_openclaw.adapter import (
    OpenClawAdapter,
    OpenClawHost,
    _parse_action_tags,
)


class _AdapterFixture(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmpdir, "memory", "shared"), exist_ok=True)
        os.makedirs(os.path.join(self.tmpdir, "memory", "domains"), exist_ok=True)
        self.host = OpenClawHost(workspace_root=self.tmpdir)
        self.adapter = OpenClawAdapter(host=self.host)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class TestOpenClawHost(unittest.TestCase):

    def test_workspace_root_from_constructor(self):
        host = OpenClawHost(workspace_root="/custom/path")
        self.assertEqual(host.workspace_root(), "/custom/path")

    def test_workspace_root_from_env(self):
        os.environ["OPENCLAW_WORKSPACE"] = "/env/path"
        try:
            host = OpenClawHost()
            self.assertEqual(host.workspace_root(), "/env/path")
        finally:
            del os.environ["OPENCLAW_WORKSPACE"]


class TestAdapterLifecycle(_AdapterFixture):

    def test_on_bootstrap_returns_context(self):
        ctx = self.adapter.on_bootstrap()
        self.assertIsInstance(ctx, SAFContext)
        self.assertIn("day_phase", ctx.temporal)

    def test_on_pre_message_returns_context(self):
        ctx = self.adapter.on_pre_message("I have a meeting tomorrow")
        self.assertIsInstance(ctx, SAFContext)
        # Pipeline already tested for keyword matching; we just verify the
        # adapter plumbs the message through correctly.
        self.assertIn("day_phase", ctx.temporal)

    def test_write_briefing_creates_file(self):
        ctx = self.adapter.on_bootstrap()
        path = self.adapter.write_briefing(ctx)
        self.assertTrue(os.path.exists(path))
        self.assertEqual(
            path, os.path.join(self.tmpdir, paths.BRIEFING_FILE)
        )

    def test_write_briefing_contains_section_headers(self):
        ctx = self.adapter.on_bootstrap()
        path = self.adapter.write_briefing(ctx)
        with open(path) as f:
            content = f.read()
        self.assertIn("## 1. Temporal Context", content)
        self.assertIn("## 6. Instructions", content)

    def test_write_briefing_is_atomic(self):
        # Write twice, verify no .tmp file is left behind
        ctx = self.adapter.on_bootstrap()
        self.adapter.write_briefing(ctx)
        self.adapter.write_briefing(ctx)
        tmp_path = self.adapter.briefing_path() + ".tmp"
        self.assertFalse(os.path.exists(tmp_path))


class TestActionTagParsing(unittest.TestCase):

    def test_parses_single_tag(self):
        response = 'Done. <saf-action id="morning_briefing" status="sent"/>'
        tags = _parse_action_tags(response)
        self.assertEqual(tags, [("morning_briefing", "sent")])

    def test_parses_multiple_tags(self):
        response = (
            'Sent briefing. <saf-action id="morning_briefing" status="sent"/> '
            'and checkin. <saf-action id="afternoon_checkin" status="sent"/>'
        )
        tags = _parse_action_tags(response)
        self.assertEqual(
            tags,
            [("morning_briefing", "sent"), ("afternoon_checkin", "sent")],
        )

    def test_parses_tag_without_self_closing_slash(self):
        response = 'Response text <saf-action id="test" status="ok">'
        tags = _parse_action_tags(response)
        self.assertEqual(tags, [("test", "ok")])

    def test_no_tags_returns_empty_list(self):
        response = "Just a normal response with no tags."
        tags = _parse_action_tags(response)
        self.assertEqual(tags, [])

    def test_malformed_tag_is_ignored(self):
        response = '<saf-action id="missing_status"/>'
        tags = _parse_action_tags(response)
        self.assertEqual(tags, [])


class TestPostMessageRecordsActions(_AdapterFixture):

    def test_on_post_message_records_tagged_action(self):
        response = 'Done. <saf-action id="test_action" status="sent"/>'
        self.adapter.on_post_message(response)

        ledger_path = os.path.join(
            self.tmpdir, "memory", "shared", "collective-ledger.json"
        )
        self.assertTrue(os.path.exists(ledger_path))
        with open(ledger_path) as f:
            data = json.load(f)
        self.assertIn("test_action", data["actions"])
        self.assertEqual(
            data["actions"]["test_action"]["context"]["status"], "sent"
        )

    def test_on_post_message_with_no_tags_is_noop(self):
        self.adapter.on_post_message("Just a normal response.")
        ledger_path = os.path.join(
            self.tmpdir, "memory", "shared", "collective-ledger.json"
        )
        # No ledger should be created if there were no actions to record
        self.assertFalse(os.path.exists(ledger_path))

    def test_on_post_message_records_multiple_actions(self):
        response = (
            '<saf-action id="action_a" status="sent"/> '
            '<saf-action id="action_b" status="sent"/>'
        )
        self.adapter.on_post_message(response)
        ctx = self.adapter.on_pre_message("follow-up")
        self.assertIn("action_a", ctx.dedup["already_done_today"])
        self.assertIn("action_b", ctx.dedup["already_done_today"])


if __name__ == "__main__":
    unittest.main()
