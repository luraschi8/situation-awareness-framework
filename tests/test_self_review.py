"""Tests for saf_core.lib.self_review — the Self-Improvement Engine."""

import json
import os
import shutil
import tempfile
import time
import unittest

from skills.saf_core.lib import self_review, paths
from skills.saf_core.lib.fs import save_json


class _WorkspaceFixture(unittest.TestCase):
    """Base providing a temp workspace with helpers."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmpdir, "memory", "shared"), exist_ok=True)
        os.makedirs(os.path.join(self.tmpdir, "memory", "domains"), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def write_config(self, filename, data):
        path = os.path.join(self.tmpdir, "memory", "shared", filename)
        save_json(path, data)

    def create_domain(self, name, files=None):
        domain_path = os.path.join(self.tmpdir, "memory", "domains", name)
        os.makedirs(domain_path, exist_ok=True)
        for filename in (files or []):
            fpath = os.path.join(domain_path, filename)
            with open(fpath, "w") as f:
                f.write(f"# {filename}\n")
        return domain_path

    def write_template(self):
        """Write a minimal protocol template for render tests."""
        tpl_dir = os.path.join(self.tmpdir, "templates")
        os.makedirs(tpl_dir, exist_ok=True)
        tpl_path = os.path.join(tpl_dir, "self-review-protocol.md")
        with open(tpl_path, "w") as f:
            f.write(
                "# Review\n"
                "Timestamp: {{ timestamp }}\n"
                "Last: {{ last_review_timestamp }}\n"
                "Mode: {{ review_mode }}\n"
                "Threshold: {{ staleness_threshold_days }}\n"
                "Workspace: {{ workspace_root }}\n"
                "{{ permissions }}\n"
                "{{ domain_audit_table }}\n"
                "{{ ledger_patterns }}\n"
            )
        return tpl_path


# -----------------------------------------------------------------------
# TestDomainAuditInfo / build_review_context
# -----------------------------------------------------------------------

class TestBuildReviewContext(_WorkspaceFixture):

    def test_empty_workspace(self):
        ctx = self_review.build_review_context(self.tmpdir)
        self.assertEqual(ctx.domains, [])
        self.assertEqual(ctx.review_mode, "full")
        self.assertIsInstance(ctx.timestamp, str)

    def test_domains_enumerated(self):
        self.create_domain("work", ["setup.md", "meetings.md"])
        self.create_domain("projects", ["roadmap.md"])
        ctx = self_review.build_review_context(self.tmpdir)
        names = [d.name for d in ctx.domains]
        self.assertIn("work", names)
        self.assertIn("projects", names)

    def test_file_mtimes_collected(self):
        self.create_domain("work", ["setup.md"])
        ctx = self_review.build_review_context(self.tmpdir)
        work = next(d for d in ctx.domains if d.name == "work")
        self.assertIn("setup.md", work.file_mtimes)
        # mtime should be today's date
        today = time.strftime("%Y-%m-%d")
        self.assertEqual(work.file_mtimes["setup.md"], today)

    def test_has_index_detected(self):
        self.create_domain("work", ["setup.md", "_index.md"])
        ctx = self_review.build_review_context(self.tmpdir)
        work = next(d for d in ctx.domains if d.name == "work")
        self.assertTrue(work.has_index)

    def test_no_index_detected(self):
        self.create_domain("work", ["setup.md"])
        ctx = self_review.build_review_context(self.tmpdir)
        work = next(d for d in ctx.domains if d.name == "work")
        self.assertFalse(work.has_index)

    def test_hidden_files_skipped(self):
        domain_path = self.create_domain("work", ["setup.md"])
        # Create a dotfile
        with open(os.path.join(domain_path, ".hidden"), "w") as f:
            f.write("secret")
        ctx = self_review.build_review_context(self.tmpdir)
        work = next(d for d in ctx.domains if d.name == "work")
        self.assertNotIn(".hidden", work.files)
        self.assertEqual(len(work.files), 1)

    def test_review_mode_from_config(self):
        ctx = self_review.build_review_context(
            self.tmpdir, config={"review_mode": "lightweight"},
        )
        self.assertEqual(ctx.review_mode, "lightweight")

    def test_staleness_threshold_from_config(self):
        ctx = self_review.build_review_context(
            self.tmpdir, config={"staleness_threshold_days": 7},
        )
        self.assertEqual(ctx.staleness_threshold_days, 7)

    def test_ledger_summary_populated(self):
        self.write_config("collective-ledger.json", {
            "last_updated": "2026-04-06T10:00:00Z",
            "actions": {
                "morning_briefing": {
                    "agent": "saf",
                    "timestamp": "2026-04-06T08:00:00Z",
                    "context": {"status": "sent"},
                }
            },
        })
        ctx = self_review.build_review_context(self.tmpdir)
        self.assertEqual(ctx.ledger_summary["total_actions_recorded"], 1)
        self.assertIn("morning_briefing", ctx.ledger_summary["action_ids"])

    def test_last_review_timestamp_from_ledger(self):
        self.write_config("collective-ledger.json", {
            "last_updated": "2026-04-06T10:00:00Z",
            "actions": {
                "knowledge_audit": {
                    "agent": "saf",
                    "timestamp": "2026-03-30T20:00:00Z",
                    "context": {"status": "sent"},
                }
            },
        })
        ctx = self_review.build_review_context(self.tmpdir)
        self.assertEqual(ctx.last_review_timestamp, "2026-03-30T20:00:00Z")

    def test_last_review_empty_when_never_run(self):
        ctx = self_review.build_review_context(self.tmpdir)
        self.assertEqual(ctx.last_review_timestamp, "")


# -----------------------------------------------------------------------
# TestValidateWorkspace
# -----------------------------------------------------------------------

class TestValidateWorkspace(_WorkspaceFixture):

    def test_empty_workspace_is_valid(self):
        result = self_review.validate_workspace(self.tmpdir)
        self.assertTrue(result.valid)
        self.assertEqual(result.errors, [])

    def test_valid_proactive_actions(self):
        self.write_config("proactive-actions.json", {
            "actions": {
                "morning_briefing": {
                    "description": "Test",
                    "trigger": {"phase": ["MORNING"], "day_type": "workday"},
                    "frequency": "daily",
                    "enabled": True,
                    "skip_modes": ["vacation"],
                }
            }
        })
        result = self_review.validate_workspace(self.tmpdir)
        self.assertTrue(result.valid)

    def test_missing_description_is_error(self):
        self.write_config("proactive-actions.json", {
            "actions": {
                "bad_action": {
                    "trigger": {"phase": ["MORNING"]},
                    "frequency": "daily",
                }
            }
        })
        result = self_review.validate_workspace(self.tmpdir)
        self.assertFalse(result.valid)
        self.assertTrue(any("description" in e for e in result.errors))

    def test_invalid_frequency_is_error(self):
        self.write_config("proactive-actions.json", {
            "actions": {
                "bad_action": {
                    "description": "Test",
                    "frequency": "hourly",
                }
            }
        })
        result = self_review.validate_workspace(self.tmpdir)
        self.assertFalse(result.valid)
        self.assertTrue(any("frequency" in e for e in result.errors))

    def test_invalid_day_of_week_is_error(self):
        self.write_config("proactive-actions.json", {
            "actions": {
                "bad_action": {
                    "description": "Test",
                    "trigger": {"day_of_week": [7]},
                }
            }
        })
        result = self_review.validate_workspace(self.tmpdir)
        self.assertFalse(result.valid)

    def test_invalid_timezone_is_error(self):
        self.write_config("user-state.json", {"timezone": "Not/A/Timezone"})
        result = self_review.validate_workspace(self.tmpdir)
        self.assertFalse(result.valid)
        self.assertTrue(any("timezone" in e for e in result.errors))

    def test_valid_user_state(self):
        self.write_config("user-state.json", {
            "timezone": "UTC",
            "work_days": [0, 1, 2, 3, 4],
            "phases": {"MORNING": [6, 12]},
            "mode": "normal",
            "suppressed_actions": [],
        })
        result = self_review.validate_workspace(self.tmpdir)
        self.assertTrue(result.valid)

    def test_invalid_work_days_is_error(self):
        self.write_config("user-state.json", {"work_days": [0, 1, 8]})
        result = self_review.validate_workspace(self.tmpdir)
        self.assertFalse(result.valid)

    def test_invalid_phase_bounds_is_error(self):
        self.write_config("user-state.json", {"phases": {"BAD": [25, 30]}})
        result = self_review.validate_workspace(self.tmpdir)
        self.assertFalse(result.valid)

    def test_valid_router_config(self):
        self.write_config("router-config.json", {
            "work": ["meeting", "office"],
            "projects": ["coding"],
        })
        result = self_review.validate_workspace(self.tmpdir)
        self.assertTrue(result.valid)

    def test_invalid_router_config_keywords(self):
        self.write_config("router-config.json", {"work": "not_a_list"})
        result = self_review.validate_workspace(self.tmpdir)
        self.assertFalse(result.valid)

    def test_unknown_trigger_keys_are_warnings(self):
        self.write_config("proactive-actions.json", {
            "actions": {
                "test": {
                    "description": "Test",
                    "trigger": {"phase": ["MORNING"], "custom_field": True},
                }
            }
        })
        result = self_review.validate_workspace(self.tmpdir)
        self.assertTrue(result.valid)  # warnings don't fail
        self.assertTrue(any("unknown trigger" in w for w in result.warnings))

    def test_skip_modes_must_be_list(self):
        self.write_config("proactive-actions.json", {
            "actions": {
                "test": {
                    "description": "Test",
                    "skip_modes": "vacation",
                }
            }
        })
        result = self_review.validate_workspace(self.tmpdir)
        self.assertFalse(result.valid)


# -----------------------------------------------------------------------
# TestSnapshotRestore
# -----------------------------------------------------------------------

class TestSnapshotRestore(_WorkspaceFixture):

    def test_snapshot_creates_copies(self):
        self.write_config("proactive-actions.json", {"actions": {}})
        self.write_config("user-state.json", {"timezone": "UTC"})
        self_review.snapshot_configs(self.tmpdir)

        snapshot_dir = paths.resolve(paths.SNAPSHOT_DIR, self.tmpdir)
        self.assertTrue(os.path.exists(
            os.path.join(snapshot_dir, "proactive-actions.json")
        ))
        self.assertTrue(os.path.exists(
            os.path.join(snapshot_dir, "user-state.json")
        ))
        self.assertTrue(os.path.exists(
            os.path.join(snapshot_dir, "meta.json")
        ))

    def test_has_stale_snapshot(self):
        self.assertFalse(self_review.has_stale_snapshot(self.tmpdir))
        self.write_config("proactive-actions.json", {"actions": {}})
        self_review.snapshot_configs(self.tmpdir)
        self.assertTrue(self_review.has_stale_snapshot(self.tmpdir))

    def test_restore_puts_files_back(self):
        original = {"actions": {"test": {"description": "Original"}}}
        self.write_config("proactive-actions.json", original)
        self_review.snapshot_configs(self.tmpdir)

        # Agent corrupts the config
        modified = {"actions": {"test": {"bad": "data"}}}
        self.write_config("proactive-actions.json", modified)

        # Restore
        restored = self_review.restore_snapshot(self.tmpdir)
        self.assertTrue(restored)

        # Verify original content is back
        path = os.path.join(self.tmpdir, "memory", "shared", "proactive-actions.json")
        with open(path) as f:
            data = json.load(f)
        self.assertEqual(data["actions"]["test"]["description"], "Original")

    def test_restore_without_snapshot_returns_false(self):
        self.assertFalse(self_review.restore_snapshot(self.tmpdir))

    def test_cleanup_removes_snapshot(self):
        self.write_config("proactive-actions.json", {"actions": {}})
        self_review.snapshot_configs(self.tmpdir)
        self.assertTrue(self_review.has_stale_snapshot(self.tmpdir))

        self_review.cleanup_snapshot(self.tmpdir)
        self.assertFalse(self_review.has_stale_snapshot(self.tmpdir))

    def test_snapshot_missing_config_files_ok(self):
        # No config files exist — snapshot should still work
        ts = self_review.snapshot_configs(self.tmpdir)
        self.assertIsInstance(ts, str)
        self.assertTrue(self_review.has_stale_snapshot(self.tmpdir))


# -----------------------------------------------------------------------
# TestRenderReviewPrompt
# -----------------------------------------------------------------------

class TestRenderReviewPrompt(_WorkspaceFixture):

    def test_template_filled_no_leftover_placeholders(self):
        tpl_path = self.write_template()
        self.create_domain("work", ["setup.md"])
        ctx = self_review.build_review_context(self.tmpdir)
        result = self_review.render_review_prompt(ctx, template_path=tpl_path)
        self.assertNotIn("{{ ", result)
        self.assertNotIn(" }}", result)

    def test_contains_timestamp(self):
        tpl_path = self.write_template()
        ctx = self_review.build_review_context(self.tmpdir)
        result = self_review.render_review_prompt(ctx, template_path=tpl_path)
        self.assertIn(ctx.timestamp, result)

    def test_lightweight_mode_forbids_config_changes(self):
        tpl_path = self.write_template()
        ctx = self_review.build_review_context(
            self.tmpdir, config={"review_mode": "lightweight"},
        )
        result = self_review.render_review_prompt(ctx, template_path=tpl_path)
        self.assertIn("Do NOT modify", result)

    def test_full_mode_includes_validation_command(self):
        tpl_path = self.write_template()
        ctx = self_review.build_review_context(
            self.tmpdir, config={"review_mode": "full"},
        )
        result = self_review.render_review_prompt(ctx, template_path=tpl_path)
        self.assertIn("skills.saf_core.validate", result)

    def test_domain_table_rendered(self):
        tpl_path = self.write_template()
        self.create_domain("work", ["setup.md", "meetings.md"])
        ctx = self_review.build_review_context(self.tmpdir)
        result = self_review.render_review_prompt(ctx, template_path=tpl_path)
        self.assertIn("work", result)
        self.assertIn("setup.md", result)

    def test_empty_domains_handled(self):
        tpl_path = self.write_template()
        ctx = self_review.build_review_context(self.tmpdir)
        result = self_review.render_review_prompt(ctx, template_path=tpl_path)
        self.assertIn("No domains found", result)


# -----------------------------------------------------------------------
# TestExecuteSelfReview
# -----------------------------------------------------------------------

class _MockHost:
    """Minimal SAFHost for tests."""

    def __init__(self, workspace_root):
        self._root = workspace_root
        self.logs = []

    def workspace_root(self):
        return self._root

    def log(self, level, message):
        self.logs.append((level, message))


class _MockRunner:
    """Mock SelfReviewRunner that returns a canned response."""

    def __init__(self, response="Review complete."):
        self.response = response
        self.calls = []

    def run_review(self, prompt, workspace_root):
        self.calls.append((prompt, workspace_root))
        return self.response


class TestExecuteSelfReview(_WorkspaceFixture):

    def test_valid_review_cleans_snapshot(self):
        self.write_template()
        self.write_config("proactive-actions.json", {"actions": {}})
        runner = _MockRunner()
        host = _MockHost(self.tmpdir)

        result = self_review.execute_self_review(runner, host)
        self.assertTrue(result.valid)
        self.assertFalse(self_review.has_stale_snapshot(self.tmpdir))
        self.assertEqual(len(runner.calls), 1)

    def test_invalid_post_state_restores_snapshot(self):
        self.write_template()
        original = {
            "actions": {
                "test": {"description": "OK", "frequency": "daily"}
            }
        }
        self.write_config("proactive-actions.json", original)

        # Runner that corrupts the config during review
        class CorruptingRunner:
            def __init__(self, tmpdir):
                self._tmpdir = tmpdir

            def run_review(self, prompt, workspace_root):
                bad = {"actions": {"test": {"frequency": "hourly"}}}
                path = os.path.join(
                    self._tmpdir, "memory", "shared", "proactive-actions.json",
                )
                with open(path, "w") as f:
                    json.dump(bad, f)
                return "Done"

        host = _MockHost(self.tmpdir)

        result = self_review.execute_self_review(
            CorruptingRunner(self.tmpdir), host,
        )
        self.assertFalse(result.valid)

        # Snapshot should have been restored
        path = os.path.join(
            self.tmpdir, "memory", "shared", "proactive-actions.json",
        )
        with open(path) as f:
            data = json.load(f)
        self.assertEqual(data["actions"]["test"]["description"], "OK")
        self.assertTrue(any("error" in l for l, m in host.logs))

    def test_stale_snapshot_restored_before_new_review(self):
        self.write_template()
        original = {"actions": {"a": {"description": "Original"}}}
        self.write_config("proactive-actions.json", original)

        # Create a stale snapshot
        self_review.snapshot_configs(self.tmpdir)

        # Corrupt config (simulating crashed prior run)
        self.write_config("proactive-actions.json", {"actions": {}})

        host = _MockHost(self.tmpdir)

        self_review.execute_self_review(_MockRunner(), host)

        # Should have logged the stale snapshot restoration
        self.assertTrue(any("stale snapshot" in m for l, m in host.logs))


if __name__ == "__main__":
    unittest.main()
