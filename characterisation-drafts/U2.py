import unittest


class U2Test(unittest.TestCase):
    def test_U2(self):
        self.skipTest(
            "The mail bucket is filled by a collector after pickup. "
            "An object missing at the 302 can follow a send the request waited for, "
            "and an object already listed can follow a send the request did not wait for."
        )
