import unittest
import urllib.request
from _support import PROJECT
from cs_youoweme.transport import SameOriginRedirect
from cs_youoweme.errors import AccessStopped


class TransportTests(unittest.TestCase):
    def test_redirect_does_not_forward_secret_to_other_host(self):
        handler = SameOriginRedirect()
        req = urllib.request.Request("https://open.steamdt.com/open/cs2/v1/base", headers={"Authorization": "Bearer test-only"})
        with self.assertRaises(AccessStopped):
            handler.redirect_request(req, None, 302, "", {}, "https://example.com/")
