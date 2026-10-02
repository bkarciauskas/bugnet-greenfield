import unittest

from web_create import host, message_recipients, qualifying_subscribers


class B8Test(unittest.TestCase):
    def test_B8(self):
        admin = host()
        member = admin.register_member(subscribe=True)
        try:
            issue = admin.create("B8")
            expected_people = qualifying_subscribers(admin.people(), issue.project_id)
            expected = {person.email.lower() for person in expected_people}
            self.assertGreaterEqual(len(expected), 2)
            self.assertIn(admin.facts.email.lower(), expected)
            messages = admin.messages_about(issue, expected_count=len(expected))
            actual = message_recipients(messages)
            self.assertEqual(expected, actual)
            for address in expected:
                addressed = [
                    message
                    for message in messages
                    if address in message_recipients([message])
                ]
                self.assertEqual(1, len(addressed))
                self.assertIn(issue.full_id, addressed[0].subject)
        finally:
            admin.release_member(member)
