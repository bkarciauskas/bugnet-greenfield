import unittest

from web_create import host, matches_general_short, render_culture


class B2Test(unittest.TestCase):
    def test_B2(self):
        issue = host().create("B2")
        facts = host().facts
        culture = render_culture(facts.preferred_locale, facts.default_language)
        self.assertEqual(f"{issue.project_code}-{issue.issue_id}", issue.detail_full_id)
        self.assertEqual(issue.title, issue.detail_title)
        self.assertEqual(facts.display_name, issue.detail_creator)
        matches_general_short(issue.detail_created, culture)
