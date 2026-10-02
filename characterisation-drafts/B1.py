import unittest

from web_create import host


class B1Test(unittest.TestCase):
    def test_B1(self):
        issue = host().create("B1")
        self.assertEqual(302, issue.redirect_status)
        self.assertEqual(
            f"/Issues/IssueDetail.aspx?id={issue.issue_id}",
            issue.location,
        )
