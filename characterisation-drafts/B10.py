import unittest

from web_create import ADDED_TEMPLATE_MARK, UPDATED_TEMPLATE_MARK, host


class B10Test(unittest.TestCase):
    def test_B10(self):
        issue = host().create("B10")
        message = host().messages_about(issue)[0]
        email_format = host().facts.email_format
        body = message.body
        self.assertIn(ADDED_TEMPLATE_MARK, body)
        self.assertNotIn(UPDATED_TEMPLATE_MARK, body)
        if email_format == "2":
            self.assertEqual("text/html", message.content_type)
        elif email_format == "1":
            self.assertNotEqual("text/html", message.content_type)
        else:
            self.fail("unread mail format setting")
        self.assert_in_order(
            body,
            [
                ADDED_TEMPLATE_MARK,
                issue.title,
                issue.project_name,
                host().facts.display_name,
                issue.priority_name,
                issue.type_name,
                issue.description,
            ],
        )

    def assert_in_order(self, body, parts):
        start = 0
        for part in parts:
            at = body.find(part, start)
            self.assertGreaterEqual(at, 0, part)
            start = at + len(part)
