import unittest

from web_create import host


class U2Test(unittest.TestCase):
    def test_U2(self):
        issue = host().create("U2")
        self.assertEqual(302, issue.redirect_status)
        messages = host().mail_for(issue)
        self.assertTrue(messages)
        for message in messages:
            self.assertNotIn(message.key, issue.keys_at_redirect)
