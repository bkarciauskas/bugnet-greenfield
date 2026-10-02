import unittest

from web_create import add_issue_template, host, message_culture, template_fields


class B11Test(unittest.TestCase):
    def test_B11(self):
        issue = host().create("B11")
        facts = host().facts
        message = host().messages_about(issue)[0]
        culture = message_culture(message, host().people(), facts.default_language)
        labels = add_issue_template(culture).labels
        fields = template_fields(message.body, culture, facts.email_format)
        title, project, created, _milestone, _category, priority, issue_type, description = labels
        self.assertEqual(list(labels), list(fields))
        self.assertEqual(issue.title, fields[title])
        self.assertEqual(issue.project_name, fields[project])
        self.assertEqual(facts.display_name, fields[created])
        self.assertEqual(issue.priority_name, fields[priority])
        self.assertEqual(issue.type_name, fields[issue_type])
        self.assertEqual(issue.description, fields[description])
