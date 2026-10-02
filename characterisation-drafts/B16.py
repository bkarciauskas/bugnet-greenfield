import unittest

from web_create import host


class B16Test(unittest.TestCase):
    def test_B16(self):
        issue = host().create("B16")
        self.assertEqual(
            f"/Issues/IssueDetail.aspx?id={issue.issue_id}",
            issue.location,
        )
        self.assertEqual("1", issue.vote_count)
        self.assertEqual(host().facts.display_name, issue.detail_creator)
