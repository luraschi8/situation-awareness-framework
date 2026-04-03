import unittest
from skills.saf_core.lib.router import get_relevant_domains


class TestRouter(unittest.TestCase):

    # --- Single domain matching ---

    def test_work_keywords(self):
        self.assertIn("work", get_relevant_domains("I have a deadline tomorrow"))
        self.assertIn("work", get_relevant_domains("Let's schedule a meeting"))

    def test_family_keywords(self):
        self.assertIn("family", get_relevant_domains("How are the kids doing?"))
        self.assertIn("family", get_relevant_domains("Any school events this week?"))

    def test_projects_keywords(self):
        self.assertIn("projects", get_relevant_domains("I need to deploy the latest build"))
        self.assertIn("projects", get_relevant_domains("Let's review the coding task"))

    def test_infrastructure_keywords(self):
        self.assertIn("infrastructure", get_relevant_domains("The server is down"))
        self.assertIn("infrastructure", get_relevant_domains("Turn off the lights"))

    # --- Multi-domain matching ---

    def test_multi_domain_work_and_family(self):
        domains = get_relevant_domains("I have a meeting after the kids' school event")
        self.assertIn("work", domains)
        self.assertIn("family", domains)

    def test_multi_domain_projects_and_infrastructure(self):
        domains = get_relevant_domains("Deploy the project to the server")
        self.assertIn("projects", domains)
        self.assertIn("infrastructure", domains)

    # --- Fallback ---

    def test_unrecognized_message_returns_general(self):
        self.assertEqual(get_relevant_domains("Hello there"), ["general"])

    def test_empty_message_returns_general(self):
        self.assertEqual(get_relevant_domains(""), ["general"])

    # --- Edge cases ---

    def test_case_insensitive(self):
        self.assertIn("work", get_relevant_domains("MEETING at 3pm"))
        self.assertIn("family", get_relevant_domains("The KIDS are home"))

    def test_no_substring_false_positive(self):
        # "home" is an infrastructure keyword but "homework" is not about home
        self.assertNotIn("infrastructure", get_relevant_domains("I need to do homework"))
        # "report" is a work keyword but "reported" in casual context shouldn't match
        self.assertNotIn("work", get_relevant_domains("She reportedly left early"))

    def test_whole_word_match(self):
        # "home" as a standalone word should still match
        self.assertIn("infrastructure", get_relevant_domains("I'm heading home now"))


if __name__ == '__main__':
    unittest.main()
