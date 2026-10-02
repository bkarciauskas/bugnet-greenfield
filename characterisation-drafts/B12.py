import unittest

from web_create import host


class B12Test(unittest.TestCase):
    def test_B12(self):
        issue = host().create("B12")
        fields = host().messages_about(issue)[0].fields
        self.assertEqual("0", issue.milestone_id)
        self.assertEqual("0", issue.category_id)
        self.assertEqual("Unassigned", fields["Milestone"])
        self.assertEqual("Unassigned", fields["Category"])
        self.assertEqual(issue.priority_name, fields["Priority"])
        self.assertEqual(issue.type_name, fields["Type"])
