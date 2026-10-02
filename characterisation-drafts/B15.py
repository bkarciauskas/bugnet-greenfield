import unittest

from web_create import host


class B15Test(unittest.TestCase):
    def test_B15(self):
        issue = host().create("B15")
        body = host().mail_for(issue)[0].body
        default_url = host().facts.default_url
        self.assertIn(default_url + f"Issues/IssueDetail.aspx?id={issue.issue_id}", body)
        self.assertIn(default_url + "Account/UserProfile.aspx", body)
