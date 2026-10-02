import unittest

from web_create import host, issue_added_subject


class B9Test(unittest.TestCase):
    def test_B9(self):
        issue = host().create("B9")
        facts = host().facts
        culture = facts.preferred_locale or facts.default_language
        pattern = issue_added_subject(culture)
        self.assertNotIn("{1}", pattern)
        expected = pattern.replace("{0}", issue.full_id)
        checked = 0
        for message in host().messages_about(issue):
            if facts.email not in message.to:
                continue
            self.assertEqual(expected, message.subject)
            checked += 1
        self.assertGreater(checked, 0)
