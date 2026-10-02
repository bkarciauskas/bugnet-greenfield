import unittest

import email.utils

from web_create import host, issue_added_subject, render_culture


class B9Test(unittest.TestCase):
    def test_B9(self):
        issue = host().create("B9")
        facts = host().facts
        by_email = {person.email.lower(): person for person in host().people()}
        messages = host().messages_about(issue)
        self.assertGreaterEqual(len(messages), 1)
        for message in messages:
            _name, address = email.utils.parseaddr(message.to)
            person = by_email.get(address.lower())
            self.assertIsNotNone(person, address)
            culture = render_culture(person.preferred_locale, facts.default_language)
            pattern = issue_added_subject(culture)
            self.assertNotIn("{1}", pattern)
            self.assertEqual(pattern.replace("{0}", issue.full_id), message.subject)
