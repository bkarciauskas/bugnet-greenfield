import unittest

from web_create import host


class B5Test(unittest.TestCase):
    def test_B5(self):
        issue = host().create("B5")
        messages = host().messages_about(issue)
        self.assertEqual(1, len(messages))
        self.assertIn(issue.full_id, messages[0].subject)
