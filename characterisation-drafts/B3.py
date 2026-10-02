import unittest

from web_create import host


class B3Test(unittest.TestCase):
    def test_B3(self):
        issue = host().create("B3")
        self.assertEqual(f"{issue.project_code}-{issue.issue_id}", issue.detail_full_id)
