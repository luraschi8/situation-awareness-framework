"""End-to-end integration tests for SAF.

These tests simulate a full multi-turn agent session without requiring
OpenClaw (or any real LLM) to be installed. They exercise the complete
pipeline + adapter + renderer + ledger round-trip in a temporary
workspace with real file I/O.

A "mock agent" helper simulates the agent's behavior:
  1. Reads the briefing file written by the adapter
  2. Optionally "responds" with action tags
  3. The adapter parses the response and records it

This proves that SAF correctly:
  - Initializes a workspace from saf-init-style config
  - Runs the full pipeline across multiple turns
  - Deduplicates actions across turns (and simulated restarts)
  - Routes messages to the right domains
  - Renders briefings that accurately reflect pipeline state
  - Persists state on disk in a way that survives adapter re-instantiation
"""

import json
import os
import shutil
import tempfile
import unittest

from skills.saf_core.lib import paths
from unittest.mock import patch

from skills.saf_core.lib.domains import (
    ARCHETYPE_KEYWORDS,
    DEFAULT_PHASES,
    DEFAULT_WORK_DAYS,
)
from skills.saf_openclaw.adapter import OpenClawAdapter, OpenClawHost


class _Workspace:
    """Helper that builds a realistic SAF workspace on disk.

    Mirrors what saf-init would create: domain directories with setup
    files, router config with archetype keywords, and user state with
    timezone + phases.
    """

    def __init__(self, root, archetype="professional", timezone="UTC"):
        self.root = root
        self.archetype = archetype
        self.timezone = timezone

    def build(self, proactive_actions=None):
        self._write_user_state()
        self._write_router_config()
        self._write_domains()
        if proactive_actions is not None:
            self._write_proactive_actions(proactive_actions)

    def _write_proactive_actions(self, actions_dict):
        path = os.path.join(self.root, paths.PROACTIVE_ACTIONS_FILE)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump({"actions": actions_dict}, f)

    def _write_user_state(self):
        path = os.path.join(self.root, paths.USER_STATE_FILE)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump({
                "timezone": self.timezone,
                "work_days": DEFAULT_WORK_DAYS,
                "phases": DEFAULT_PHASES,
            }, f)

    def _write_router_config(self):
        path = os.path.join(self.root, paths.ROUTER_CONFIG_FILE)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        keywords = ARCHETYPE_KEYWORDS[self.archetype]
        with open(path, "w") as f:
            json.dump(keywords, f)

    def _write_domains(self):
        keywords = ARCHETYPE_KEYWORDS[self.archetype]
        for domain_name in keywords.keys():
            domain_dir = os.path.join(self.root, paths.DOMAINS_DIR, domain_name)
            os.makedirs(domain_dir, exist_ok=True)
            with open(os.path.join(domain_dir, "setup.md"), "w") as f:
                f.write(f"# {domain_name} Domain\n\nTest content.")

    def read_ledger(self):
        path = os.path.join(self.root, paths.LEDGER_FILE)
        if not os.path.exists(path):
            return None
        with open(path) as f:
            return json.load(f)

    def read_briefing(self):
        path = os.path.join(self.root, paths.BRIEFING_FILE)
        if not os.path.exists(path):
            return None
        with open(path) as f:
            return f.read()


class _MockAgent:
    """Simulates an agent's behavior in a SAF-enabled session.

    Reads the briefing file the adapter just wrote, optionally generates
    a response with action tags, and passes it back to the adapter.
    """

    def __init__(self, adapter):
        self.adapter = adapter
        self.last_briefing = None
        self.last_response = None

    def receive_message(self, user_message):
        """Simulates the pre-message hook: run pipeline + write briefing.

        Mirrors what hooks/saf-pre-message/handler.py does in production.
        """
        ctx = self.adapter.on_pre_message(user_message)
        self.adapter.write_briefing(ctx)
        self.last_briefing = self._read_briefing()
        return self.last_briefing

    def respond_with_action(self, action_id, status="sent"):
        """Generates a fake response including a SAF action tag."""
        self.last_response = (
            f'Here is my response. <saf-action id="{action_id}" status="{status}"/>'
        )
        self.adapter.on_post_message(self.last_response)
        return self.last_response

    def respond_plain(self, text="OK"):
        """Generates a response without any action tags."""
        self.last_response = text
        self.adapter.on_post_message(text)
        return self.last_response

    def _read_briefing(self):
        path = self.adapter.briefing_path()
        if not os.path.exists(path):
            return None
        with open(path) as f:
            return f.read()


class _IntegrationFixture(unittest.TestCase):
    """Base class providing a freshly bootstrapped workspace + adapter."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.workspace = _Workspace(self.tmpdir, archetype="professional")
        self.workspace.build()
        self.host = OpenClawHost(workspace_root=self.tmpdir)
        self.adapter = OpenClawAdapter(host=self.host)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def new_agent(self):
        return _MockAgent(self.adapter)


class TestFreshSessionBootstrap(_IntegrationFixture):
    """A brand-new session should produce a briefing with temporal context
    but no domain matches and no dedup state."""

    def test_bootstrap_writes_briefing_with_temporal_context(self):
        ctx = self.adapter.on_bootstrap()
        self.adapter.write_briefing(ctx)
        briefing = self.workspace.read_briefing()

        self.assertIsNotNone(briefing)
        self.assertIn("## 1. Temporal Context", briefing)
        self.assertIn("UTC", briefing)
        self.assertIn("## 2. Relevant Domains", briefing)
        self.assertIn("## 3. Available Proactive Actions", briefing)
        self.assertIn("## 4. Already Done Today", briefing)
        self.assertIn("Nothing yet", briefing)
        self.assertIn("## 5. Blocked Actions", briefing)
        self.assertIn("## 6. Instructions", briefing)

    def test_bootstrap_has_no_candidate_domains(self):
        ctx = self.adapter.on_bootstrap()
        self.assertEqual(ctx.candidate_domains, [])


class TestMultiTurnDedup(_IntegrationFixture):
    """The canonical SAF value prop: an action done in turn 1 must be
    blocked in turn 2, across pipeline invocations."""

    def test_action_tagged_in_turn_1_is_blocked_in_turn_2(self):
        agent = self.new_agent()

        # Turn 1: user asks something, agent sends the morning briefing
        agent.receive_message("What's on my schedule today?")
        agent.respond_with_action("morning_briefing", "sent")

        # Turn 2: user asks again — SAF should see the action in the ledger
        agent.receive_message("Send me the morning briefing please")

        ctx = self.adapter.on_pre_message("anything")
        self.assertIn("morning_briefing", ctx.dedup["already_done_today"])
        self.assertIn("morning_briefing", ctx.blocked_actions)
        self.assertEqual(
            ctx.blocked_actions["morning_briefing"], "already_done_today"
        )

    def test_briefing_in_turn_2_warns_about_blocked_action(self):
        agent = self.new_agent()
        agent.receive_message("Schedule?")
        agent.respond_with_action("morning_briefing")

        agent.receive_message("Send briefing")
        briefing = agent.last_briefing

        # The blocked-actions section should list the action
        self.assertIn("## 5. Blocked Actions (do not execute)", briefing)
        self.assertIn("morning_briefing", briefing)
        self.assertIn("already_done_today", briefing)

    def test_multiple_actions_all_recorded(self):
        agent = self.new_agent()
        agent.receive_message("anything")
        agent.respond_with_action("action_a", "sent")
        agent.receive_message("anything")
        agent.respond_with_action("action_b", "sent")
        agent.receive_message("anything")
        agent.respond_with_action("action_c", "sent")

        ctx = self.adapter.on_pre_message("query")
        self.assertIn("action_a", ctx.dedup["already_done_today"])
        self.assertIn("action_b", ctx.dedup["already_done_today"])
        self.assertIn("action_c", ctx.dedup["already_done_today"])

    def test_plain_response_does_not_write_ledger(self):
        agent = self.new_agent()
        agent.receive_message("hi")
        agent.respond_plain("Hello!")

        ledger = self.workspace.read_ledger()
        # No actions → no ledger file should be created
        self.assertIsNone(ledger)


class TestRestartPersistence(_IntegrationFixture):
    """Simulates an agent restart: the ledger must persist and dedup must
    continue working even with a fresh adapter instance."""

    def test_ledger_survives_adapter_reinstantiation(self):
        # Turn 1 with adapter A
        adapter_a = OpenClawAdapter(host=self.host)
        adapter_a.on_pre_message("schedule?")
        adapter_a.on_post_message(
            '<saf-action id="persistent_action" status="sent"/>'
        )

        # Simulate a restart by creating a completely new adapter instance
        adapter_b = OpenClawAdapter(host=OpenClawHost(workspace_root=self.tmpdir))

        # The new adapter should see the action in the ledger
        ctx = adapter_b.on_pre_message("any query")
        self.assertIn("persistent_action", ctx.dedup["already_done_today"])
        self.assertIn("persistent_action", ctx.blocked_actions)


class TestDomainRouting(_IntegrationFixture):
    """The router correctly identifies relevant domains based on message
    content, and the briefing lists the specific files to load."""

    def test_work_message_matches_work_domain(self):
        agent = self.new_agent()
        # Uses plural "meetings" to verify router.COMMON_SUFFIXES works
        # end-to-end: plural/verb forms should match singular keywords.
        briefing = agent.receive_message("I have several meetings today")

        self.assertIn("**work**", briefing)
        self.assertIn("`setup.md`", briefing)
        self.assertIn("memory/domains/work/", briefing)

    def test_unrelated_message_shows_no_domains(self):
        agent = self.new_agent()
        briefing = agent.receive_message("just saying hi")

        self.assertIn("No specific domains matched", briefing)

    def test_multi_domain_message_matches_multiple(self):
        agent = self.new_agent()
        briefing = agent.receive_message(
            "Deploy the project before the meeting deadline"
        )

        # Both "projects" (deploy) and "work" (meeting, deadline) should match
        self.assertIn("**work**", briefing)
        self.assertIn("**projects**", briefing)


class TestBriefingLifecycle(_IntegrationFixture):
    """The briefing file is regenerated on every turn and reflects
    current pipeline state."""

    def test_briefing_overwritten_on_each_pre_message(self):
        # Turn 1
        ctx1 = self.adapter.on_pre_message("send the morning briefing")
        self.adapter.write_briefing(ctx1)
        briefing1 = self.workspace.read_briefing()

        # Turn 2
        ctx2 = self.adapter.on_pre_message("deploy the project")
        self.adapter.write_briefing(ctx2)
        briefing2 = self.workspace.read_briefing()

        # Briefings should differ (different message → different routing)
        self.assertNotEqual(briefing1, briefing2)

    def test_briefing_path_is_stable(self):
        # The path never changes; only the content does
        path1 = self.adapter.briefing_path()
        self.adapter.write_briefing(self.adapter.on_bootstrap())
        path2 = self.adapter.briefing_path()
        self.assertEqual(path1, path2)

    def test_briefing_contains_action_tag_instructions(self):
        ctx = self.adapter.on_bootstrap()
        self.adapter.write_briefing(ctx)
        briefing = self.workspace.read_briefing()

        # Agent needs to know how to tag its actions
        self.assertIn("<saf-action", briefing)
        self.assertIn("status=", briefing)


class TestFullRealisticSession(_IntegrationFixture):
    """A multi-turn realistic session that exercises all the core flows
    together: bootstrap → routing → action → dedup → different domain."""

    def test_realistic_four_turn_session(self):
        agent = self.new_agent()

        # --- Turn 1: bootstrap ---
        self.adapter.on_bootstrap()
        self.adapter.write_briefing(self.adapter.on_bootstrap())
        initial_briefing = self.workspace.read_briefing()
        self.assertIn("Nothing yet", initial_briefing)

        # --- Turn 2: user asks about work (plural form), agent responds ---
        agent.receive_message("What meetings do I have this morning?")
        self.assertIn("**work**", agent.last_briefing)
        agent.respond_with_action("work_briefing", "sent")

        # --- Turn 3: user asks about a project (verb form) ---
        agent.receive_message("Are we deploying today?")
        self.assertIn("**projects**", agent.last_briefing)
        # work_briefing should now appear as blocked
        self.assertIn("work_briefing", agent.last_briefing)
        self.assertIn("already_done_today", agent.last_briefing)
        # Agent executes a different action
        agent.respond_with_action("deploy_status_check", "sent")

        # --- Turn 4: user asks generic question, both actions still blocked ---
        agent.receive_message("anything else?")
        ctx = self.adapter.on_pre_message("status?")
        self.assertIn("work_briefing", ctx.blocked_actions)
        self.assertIn("deploy_status_check", ctx.blocked_actions)

        # Ledger should have both actions persisted
        ledger = self.workspace.read_ledger()
        self.assertIsNotNone(ledger)
        self.assertIn("work_briefing", ledger["actions"])
        self.assertIn("deploy_status_check", ledger["actions"])


class TestArchitecturalBoundaries(_IntegrationFixture):
    """Verify SAF does NOT do things it shouldn't — this test enforces the
    deterministic/agentic boundary at runtime."""

    def test_pipeline_never_reads_domain_file_contents(self):
        # Write a file with content that would cause problems if SAF read it
        domain_dir = os.path.join(self.tmpdir, paths.DOMAINS_DIR, "work")
        os.makedirs(domain_dir, exist_ok=True)
        sensitive_file = os.path.join(domain_dir, "sensitive.md")
        with open(sensitive_file, "w") as f:
            f.write("SECRET_TOKEN_THAT_MUST_NOT_LEAK")

        agent = self.new_agent()
        briefing = agent.receive_message("I have a meeting to prepare for")

        # SAF should list the filename but NEVER the file contents
        self.assertIn("sensitive.md", briefing)
        self.assertNotIn("SECRET_TOKEN_THAT_MUST_NOT_LEAK", briefing)

    def test_saf_context_is_immutable(self):
        # The frozen dataclass should reject field reassignment
        ctx = self.adapter.on_bootstrap()
        with self.assertRaises(Exception):
            ctx.temporal = {}  # type: ignore


def _morning_workday_patch():
    """Returns a patch that makes temporal return a consistent MORNING/workday."""
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


class TestProactiveActionLifecycle(unittest.TestCase):
    """Integration tests for the full proactive action lifecycle:
    registry → pipeline → briefing → execution → dedup."""

    REGISTRY = {
        "morning_briefing": {
            "description": "Summarize today's schedule",
            "trigger": {"phase": ["MORNING"], "day_type": "workday"},
            "frequency": "daily",
            "domains": ["work"],
            "enabled": True,
        },
        "weekly_review": {
            "description": "Review the week",
            "trigger": {"phase": ["MORNING"], "day_of_week": [0]},
            "frequency": "weekly",
            "domains": ["work", "projects"],
            "enabled": True,
        },
    }

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.workspace = _Workspace(self.tmpdir, archetype="professional")
        self.workspace.build(proactive_actions=self.REGISTRY)
        self.host = OpenClawHost(workspace_root=self.tmpdir)
        self.adapter = OpenClawAdapter(host=self.host)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def new_agent(self):
        return _MockAgent(self.adapter)

    def test_registry_action_appears_in_briefing(self):
        agent = self.new_agent()
        with _morning_workday_patch():
            briefing = agent.receive_message("hello")
        self.assertIn("## 3. Available Proactive Actions", briefing)
        self.assertIn("morning_briefing", briefing)
        self.assertIn("Summarize today's schedule", briefing)

    def test_registry_action_blocked_after_execution(self):
        agent = self.new_agent()
        with _morning_workday_patch():
            agent.receive_message("hello")
            agent.respond_with_action("morning_briefing", "sent")

            # Turn 2: morning_briefing should be blocked
            ctx = self.adapter.on_pre_message("anything")
        self.assertIn("morning_briefing", ctx.blocked_actions)
        self.assertEqual(
            ctx.blocked_actions["morning_briefing"], "already_done_daily",
        )
        # Should not appear in available_actions
        available_ids = [a.id for a in ctx.available_actions]
        self.assertNotIn("morning_briefing", available_ids)

    def test_weekly_action_stays_blocked_within_week(self):
        agent = self.new_agent()
        with _morning_workday_patch():
            agent.receive_message("hello")
            agent.respond_with_action("weekly_review", "sent")

            # Same day, weekly_review should still be blocked
            ctx = self.adapter.on_pre_message("anything")
        self.assertIn("weekly_review", ctx.blocked_actions)
        self.assertEqual(
            ctx.blocked_actions["weekly_review"], "already_done_weekly",
        )

    def test_action_domains_surfaced_even_without_keyword_match(self):
        """Available actions should inject their domains into the briefing
        even if the user message doesn't match those domains by keyword."""
        agent = self.new_agent()
        with _morning_workday_patch():
            # "hello" matches no router keywords, but morning_briefing
            # has domains=["work"] which should appear
            briefing = agent.receive_message("hello")
        self.assertIn("**work**", briefing)


if __name__ == "__main__":
    unittest.main()
