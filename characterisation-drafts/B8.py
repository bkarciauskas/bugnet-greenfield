import unittest

from web_create import host


class B8Test(unittest.TestCase):
    def test_B8(self):
        issue = host().create("B8")
        facts = host().facts
        expected = set(host().signed_in_subscriber_emails(issue.project_id))
        actual = host().recipient_addresses(issue)
        self.assertEqual(expected, actual)
        creator_qualifies = (
            facts.notifications_on and issue.project_id in facts.subscribed_project_ids
        )
        if creator_qualifies:
            self.assertIn(facts.email, actual)
