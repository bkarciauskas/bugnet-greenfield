import unittest

from web_create import assert_add_issue_template, host


class B10Test(unittest.TestCase):
    def test_B10(self):
        issue = host().create("B10")
        message = host().messages_about(issue)[0]
        assert_add_issue_template(message.body, host().facts.email_format)
        self.assert_in_order(
            message.body,
            [
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
