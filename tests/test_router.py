import unittest
from skills.saf_core.lib.router import route_intent

class TestRouter(unittest.TestCase):
    def test_route_work(self):
        domains = route_intent("How is my meeting schedule?")
        self.assertIn("work", domains)

    def test_route_family(self):
        domains = route_intent("What is the family doing today?")
        self.assertIn("family", domains)

    def test_route_general(self):
        domains = route_intent("Hello there")
        self.assertEqual(domains, ["general"])

if __name__ == '__main__':
    unittest.main()
