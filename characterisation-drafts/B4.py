import unittest

from web_create import host, message_recipients, qualifying_subscribers


class B4Test(unittest.TestCase):
    def test_B4(self):
        admin = host()
        project_id = admin.project_id()
        was_subscribed = project_id in admin.facts.subscribed_project_ids
        creator_email = admin.facts.email.lower()
        admin.set_subscribed(project_id, False)
        try:
            expected = {
                person.email.lower()
                for person in qualifying_subscribers(admin.people(), project_id)
            }
            self.assertNotIn(creator_email, expected)
            issue = admin.create("B4")
            self.assertEqual("", issue.owner_value)
            self.assertEqual("", issue.assignee_value)
            messages = admin.messages_about(issue, expected_count=len(expected))
            self.assertEqual(expected, message_recipients(messages))
        finally:
            if was_subscribed:
                admin.set_subscribed(project_id, True)
