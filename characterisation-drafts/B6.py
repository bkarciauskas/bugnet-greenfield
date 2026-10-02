import email.utils
import unittest

from web_create import host


class B6Test(unittest.TestCase):
    def test_B6(self):
        issue = host().create("B6")
        facts = host().facts
        message = host().mail_for(issue)[0]
        name, address = email.utils.parseaddr(message.sender)
        self.assertEqual(facts.application_title, name)
        local, separator, domain = facts.host_email.partition("@")
        self.assertEqual("@", separator)
        if facts.allow_reply_to:
            self.assertEqual(f"{local}+iid-{issue.issue_id}@{domain}", address)
        else:
            self.assertEqual(facts.host_email, address)
            self.assertNotIn(f"+iid-{issue.issue_id}", address)
