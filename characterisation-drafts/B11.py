import unittest

from web_create import host


class B11Test(unittest.TestCase):
    def test_B11(self):
        issue = host().create("B11")
        fields = host().messages_about(issue)[0].fields
        self.assertEqual(
            ["Title", "Project", "Created By", "Milestone", "Category", "Priority", "Type", "Description"],
            [name for name in fields if name in {
                "Title", "Project", "Created By", "Milestone", "Category",
                "Priority", "Type", "Description",
            }],
        )
        self.assertEqual(issue.title, fields["Title"])
        self.assertEqual(issue.project_name, fields["Project"])
        self.assertEqual(host().facts.display_name, fields["Created By"])
        self.assertEqual(issue.priority_name, fields["Priority"])
        self.assertEqual(issue.type_name, fields["Type"])
        self.assertEqual(issue.description, fields["Description"])
        self.assertIn("Milestone", fields)
        self.assertIn("Category", fields)
