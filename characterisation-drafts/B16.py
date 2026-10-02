import unittest

from web_create import assert_creator_vote, host


class B16Test(unittest.TestCase):
    def test_B16(self):
        issue = host().create("B16")
        self.assertEqual(
            f"/Issues/IssueDetail.aspx?id={issue.issue_id}",
            issue.location,
        )
        assert_creator_vote(issue.detail_html)
        self.assertEqual(host().facts.display_name, issue.detail_creator)
