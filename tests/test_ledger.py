import unittest
import os
import json
import sys
sys.path.append('skills/saf-core/lib')
from ledger import sync_action

class TestLedger(unittest.TestCase):
    def setUp(self):
        self.test_path = "memory/shared/collective-ledger.json"
        if os.path.exists(self.test_path):
            os.remove(self.test_path)

    def test_sync_action_creation(self):
        success = sync_action("test_agent", "morning_briefing", {"status": "ok"})
        self.assertTrue(success)
        self.assertTrue(os.path.exists(self.test_path))
        with open(self.test_path, 'r') as f:
            data = json.load(f)
            self.assertIn("morning_briefing", data["actions"])
            self.assertEqual(data["actions"]["morning_briefing"]["agent"], "test_agent")

if __name__ == '__main__':
    unittest.main()
