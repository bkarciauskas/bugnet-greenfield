import unittest

from web_create import host, matches_general_short


class B2Test(unittest.TestCase):
    def test_B2(self):
        issue = host().create("B2")
        facts = host().facts
        self.assertEqual(f"{issue.project_code}-{issue.issue_id}", issue.detail_full_id)
        self.assertEqual(issue.title, issue.detail_title)
        self.assertEqual(facts.display_name, issue.detail_creator)
        self.assertTrue(facts.preferred_locale)
        matches_general_short(issue.detail_created, facts.preferred_locale)
