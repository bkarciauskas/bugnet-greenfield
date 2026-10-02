import unittest

from web_create import add_issue_template, host, message_culture, template_fields


class B12Test(unittest.TestCase):
    def test_B12(self):
        issue = host().create("B12")
        facts = host().facts
        message = host().messages_about(issue)[0]
        culture = message_culture(message, host().people(), facts.default_language)
        labels = add_issue_template(culture).labels
        fields = template_fields(message.body, culture, facts.email_format)
        self.assertEqual("0", issue.milestone_id)
        self.assertEqual("0", issue.category_id)
        self.assertEqual("Unassigned", fields[labels[3]])
        self.assertEqual("Unassigned", fields[labels[4]])
        self.assertEqual(issue.priority_name, fields[labels[5]])
        self.assertEqual(issue.type_name, fields[labels[6]])
