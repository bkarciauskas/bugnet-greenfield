import unittest

from web_create import host


class B5Test(unittest.TestCase):
    def test_B5(self):
        issue = host().create("B5")
        messages = host().messages_about(issue)
        self.assertGreaterEqual(len(messages), 1)
        for message in messages:
            self.assertIn(issue.full_id, message.subject)
