import unittest

from web_create import host


class B10Test(unittest.TestCase):
    def test_B10(self):
        issue = host().create("B10")
        message = host().mail_for(issue)[0]
        email_format = host().facts.email_format
        if email_format == "2":
            self.assertEqual("text/html", message.content_type)
            self.assertIn("<table", message.body.lower())
        elif email_format == "1":
            self.assertNotIn("<table", message.body.lower())
            self.assertIn("Title:", message.body)
        else:
            self.fail("unread mail format setting")
