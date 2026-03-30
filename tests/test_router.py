import unittest
import sys
sys.path.append('skills/saf-core/lib')
from router import route_intent

class TestRouter(unittest.TestCase):
    def test_route_work(self):
        domains = route_intent("How is my Taxfix schedule?")
        self.assertIn("work", domains)

    def test_route_family(self):
        domains = route_intent("What is María doing?")
        self.assertIn("family", domains)

    def test_route_general(self):
        domains = route_intent("Hello Jarvis")
        self.assertEqual(domains, ["general"])

if __name__ == '__main__':
    unittest.main()
