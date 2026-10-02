import unittest

from web_create import host


class B4Test(unittest.TestCase):
    def test_B4(self):
        issue = host().create("B4")
        self.assertEqual(302, issue.redirect_status)
        self.assertEqual("", issue.owner_value)
        self.assertEqual("", issue.assignee_value)
        expected = set(host().signed_in_subscriber_emails(issue.project_id))
        self.assertEqual(expected, host().recipient_addresses(issue))
