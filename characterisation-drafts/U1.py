import unittest

from web_create import host


class U1Test(unittest.TestCase):
    def test_U1(self):
        issue = host().create("U1")
        self.assertNotEqual("0", issue.status_id)
        self.assertNotEqual("0", issue.resolution_id)
        self.assertEqual(issue.status_id, issue.detail_status_id)
        self.assertEqual(issue.resolution_id, issue.detail_resolution_id)
