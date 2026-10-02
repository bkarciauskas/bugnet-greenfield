import unittest

from web_create import host


class B16Test(unittest.TestCase):
    def test_B16(self):
        issue = host().create("B16")
        self.assertEqual("1", issue.vote_count)
        self.assertIn('id="MainContent_VotedLabel"', issue.detail_html)
        self.assertNotIn('id="MainContent_VoteButton"', issue.detail_html)
