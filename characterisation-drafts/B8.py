import unittest

from web_create import host


class B8Test(unittest.TestCase):
    def test_B8(self):
        issue = host().create("B8")
        facts = host().facts
        expected = host().observable_subscriber_emails(issue.project_id)
        self.assertTrue(expected)
        actual = host().recipient_addresses(issue)
        for address in expected:
            self.assertIn(address, actual)
        creator_qualifies = (
            facts.notifications_on and issue.project_id in facts.subscribed_project_ids
        )
        if creator_qualifies:
            self.assertIn(facts.email, actual)
