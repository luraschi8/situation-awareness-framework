import unittest
import time


def check_temporal_integrity(generated_time_str, system_time):
    # Anti-Simulation rule v3.1
    # If the agent claims it's "Tuesday" but the system clock says "Mon"
    if "Tuesday" in generated_time_str and "Mon" in time.ctime(system_time):
        return False, "Temporal Hallucination Detected"
    return True, "Integrity OK"


class TestTemporalIntegrity(unittest.TestCase):
    def test_matching_day_passes(self):
        ok, msg = check_temporal_integrity("Good morning", time.time())
        self.assertTrue(ok)
        self.assertEqual(msg, "Integrity OK")

    def test_mismatched_day_on_monday(self):
        # Find a Monday timestamp to test against
        # Use a known Monday: 2026-01-05 is a Monday
        import calendar
        import datetime
        monday = datetime.datetime(2026, 1, 5, 12, 0, 0).timestamp()
        ok, msg = check_temporal_integrity("Good morning, today is Tuesday 6", monday)
        self.assertFalse(ok)
        self.assertEqual(msg, "Temporal Hallucination Detected")

    def test_correct_day_passes(self):
        # Same Monday, agent says Monday — should pass
        import datetime
        monday = datetime.datetime(2026, 1, 5, 12, 0, 0).timestamp()
        ok, msg = check_temporal_integrity("Good morning, today is Monday 5", monday)
        self.assertTrue(ok)


if __name__ == '__main__':
    unittest.main()
