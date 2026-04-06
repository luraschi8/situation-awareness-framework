"""Tests for the OpenClaw adapter's markdown briefing renderer."""

import unittest

from skills.saf_core.lib.context import DomainCandidate, ProactiveAction, SAFContext
from skills.saf_openclaw.renderer import render_briefing


def _sample_temporal():
    return {
        "utc_time": "2026-04-05T10:30:00+00:00",
        "timezone": "Europe/Berlin",
        "local_time": "2026-04-05T12:30:00+02:00",
        "hour": 12,
        "day_phase": "MORNING",
        "day_of_week": "Sunday",
        "day_type": "rest_day",
        "iso_date": "2026-04-05",
        "weekday_number": 6,
    }


class TestRenderBriefing(unittest.TestCase):

    def test_contains_all_six_section_headers(self):
        ctx = SAFContext(temporal=_sample_temporal(), dedup={})
        out = render_briefing(ctx)
        self.assertIn("## 1. Temporal Context", out)
        self.assertIn("## 2. Relevant Domains", out)
        self.assertIn("## 3. Available Proactive Actions", out)
        self.assertIn("## 4. Already Done Today", out)
        self.assertIn("## 5. Blocked Actions", out)
        self.assertIn("## 6. Instructions", out)

    def test_temporal_section_renders_all_fields(self):
        ctx = SAFContext(temporal=_sample_temporal(), dedup={})
        out = render_briefing(ctx)
        self.assertIn("Europe/Berlin", out)
        self.assertIn("MORNING", out)
        self.assertIn("rest_day", out)
        self.assertIn("Sunday", out)
        self.assertIn("2026-04-05", out)

    def test_domains_section_lists_files(self):
        ctx = SAFContext(
            temporal=_sample_temporal(),
            dedup={},
            candidate_domains=[
                DomainCandidate(
                    name="work",
                    path="memory/domains/work",
                    files=["setup.md", "meetings.md"],
                    reason='matched message: "schedule"',
                )
            ],
        )
        out = render_briefing(ctx)
        self.assertIn("**work**", out)
        self.assertIn("`setup.md`", out)
        self.assertIn("`meetings.md`", out)
        self.assertIn("memory/domains/work/", out)

    def test_empty_domains_explained(self):
        ctx = SAFContext(temporal=_sample_temporal(), dedup={})
        out = render_briefing(ctx)
        self.assertIn("No specific domains matched", out)

    def test_available_actions_renders_description_and_domains(self):
        ctx = SAFContext(
            temporal=_sample_temporal(),
            dedup={},
            available_actions=[
                ProactiveAction(
                    id="morning_briefing",
                    description="Summarize today's schedule",
                    domains=["work", "projects"],
                    frequency="daily",
                ),
            ],
        )
        out = render_briefing(ctx)
        self.assertIn("morning_briefing", out)
        self.assertIn("Summarize today's schedule", out)
        self.assertIn("work, projects", out)

    def test_available_actions_shows_requires_trigger(self):
        ctx = SAFContext(
            temporal=_sample_temporal(),
            dedup={},
            available_actions=[
                ProactiveAction(
                    id="meeting_prep",
                    description="Prepare for meeting",
                    requires_trigger="calendar_event",
                ),
            ],
        )
        out = render_briefing(ctx)
        self.assertIn("requires: calendar_event", out)

    def test_empty_available_actions_says_none(self):
        ctx = SAFContext(temporal=_sample_temporal(), dedup={})
        out = render_briefing(ctx)
        self.assertIn("None right now", out)

    def test_already_done_section_lists_actions(self):
        ctx = SAFContext(
            temporal=_sample_temporal(),
            dedup={"already_done_today": ["morning_briefing", "pet_reminder"]},
        )
        out = render_briefing(ctx)
        self.assertIn("`morning_briefing`", out)
        self.assertIn("`pet_reminder`", out)

    def test_empty_already_done_says_nothing_yet(self):
        ctx = SAFContext(
            temporal=_sample_temporal(),
            dedup={"already_done_today": []},
        )
        out = render_briefing(ctx)
        self.assertIn("Nothing yet", out)

    def test_blocked_actions_show_reasons(self):
        ctx = SAFContext(
            temporal=_sample_temporal(),
            dedup={},
            blocked_actions={"morning_briefing": "already_done_today"},
        )
        out = render_briefing(ctx)
        self.assertIn("morning_briefing", out)
        self.assertIn("already_done_today", out)

    def test_instructions_mention_action_tag_syntax(self):
        ctx = SAFContext(
            temporal=_sample_temporal(),
            dedup={},
            agent_instructions=[
                'If you execute a proactive action, tag it in your response: '
                '<saf-action id="<action_id>" status="sent"/>'
            ],
        )
        out = render_briefing(ctx)
        self.assertIn("<saf-action", out)

    def test_instructions_are_numbered(self):
        ctx = SAFContext(
            temporal=_sample_temporal(),
            dedup={},
            agent_instructions=["First", "Second", "Third"],
        )
        out = render_briefing(ctx)
        self.assertIn("1. First", out)
        self.assertIn("2. Second", out)
        self.assertIn("3. Third", out)

    def test_briefing_is_not_empty(self):
        ctx = SAFContext(temporal=_sample_temporal(), dedup={})
        out = render_briefing(ctx)
        self.assertTrue(len(out) > 100)

    def test_briefing_has_auto_generated_warning(self):
        ctx = SAFContext(temporal=_sample_temporal(), dedup={})
        out = render_briefing(ctx)
        self.assertIn("auto-generated", out)
        self.assertIn("Do not edit", out)


if __name__ == "__main__":
    unittest.main()
