import unittest

from web_create import assert_add_issue_template, host, message_culture


class B10Test(unittest.TestCase):
    def test_B10(self):
        issue = host().create("B10")
        facts = host().facts
        message = host().messages_about(issue)[0]
        culture = message_culture(message, host().people(), facts.default_language)
        assert_add_issue_template(message.body, facts.email_format, culture)
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
