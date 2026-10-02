import unittest

from web_create import host


class B13Test(unittest.TestCase):
    def test_B13(self):
        issue = host().create("B13")
        fields = host().mail_for(issue)[0].fields
        self.assertNotEqual("0", issue.status_id)
        self.assertNotEqual("0", issue.resolution_id)
        self.assertNotIn("Status", fields)
        self.assertNotIn("Resolution", fields)
