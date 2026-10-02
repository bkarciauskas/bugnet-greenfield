import unittest

from web_create import host


class B14Test(unittest.TestCase):
    def test_B14(self):
        issue = host().create("B14")
        body = host().messages_about(issue)[0].body
        self.assertIn(f"Issues/IssueDetail.aspx?id={issue.issue_id}", body)
        self.assertIn("Account/UserProfile.aspx", body)
