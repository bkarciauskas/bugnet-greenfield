import unittest

from web_create import host


class B9Test(unittest.TestCase):
    def test_B9(self):
        issue = host().create("B9")
        subject = host().mail_for(issue)[0].subject
        self.assertTrue(issue.project_name)
        self.assertIn(issue.full_id, subject)
        self.assertNotIn(issue.project_name, subject)
