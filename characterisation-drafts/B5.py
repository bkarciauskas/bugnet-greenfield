import unittest

from web_create import host, subject_names_issue


class B5Test(unittest.TestCase):
    def test_B5(self):
        issue = host().create("B5")
        messages = host().messages_about(issue)
        self.assertGreaterEqual(len(messages), 1)
        for message in messages:
            subject_names_issue(message.subject, issue.full_id)
