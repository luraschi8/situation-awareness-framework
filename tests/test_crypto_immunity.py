import unittest
import time
import json
import os
from skills.saf_core.lib import crypto_engine

class TestCryptoImmunity(unittest.TestCase):
    def setUp(self):
        # Mutual trust setup
        self.agent_id = "test_agent"
        self.pub_key = "test_pub_key"
        with open(crypto_engine.KEY_PATH, 'w') as f:
            json.dump({self.agent_id: {"public_key": self.pub_key}}, f)

    def test_valid_message(self):
        body = "Hello Agent"
        sig = crypto_engine.sign_message(body, self.pub_key)
        envelope = {
            "sender_id": self.agent_id,
            "body": body,
            "signature": sig,
            "timestamp": time.time()
        }
        ok, msg = crypto_engine.verify_envelope(envelope)
        self.assertTrue(ok)

    def test_forged_signature(self):
        envelope = {
            "sender_id": self.agent_id,
            "body": "Malicious Message",
            "signature": "fake_signature",
            "timestamp": time.time()
        }
        ok, msg = crypto_engine.verify_envelope(envelope)
        self.assertFalse(ok)
        self.assertEqual(msg, "Cryptographic Mismatch (Possible Tampering)")

    def test_replay_attack(self):
        body = "Old action"
        sig = crypto_engine.sign_message(body, self.pub_key)
        envelope = {
            "sender_id": self.agent_id,
            "body": body,
            "signature": sig,
            "timestamp": time.time() - 60  # 1 minute ago
        }
        ok, msg = crypto_engine.verify_envelope(envelope)
        self.assertFalse(ok)
        self.assertIn("expired", msg)

if __name__ == '__main__':
    unittest.main()
