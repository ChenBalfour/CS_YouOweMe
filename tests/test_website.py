import io
import json
import time
import unittest
import urllib.error
from unittest.mock import patch

import _support
from cs_youoweme.collectors.website import KLINE, WebsiteClient, freshness_timestamp
from cs_youoweme.errors import AccessStopped


class Response(io.BytesIO):
    url = "https://www.steamdt.com/api"


class Opener:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def open(self, req, timeout):
        self.calls.append(req)
        value = next(self.responses)
        if isinstance(value, Exception):
            raise value
        return Response(json.dumps(value).encode())


class WebsiteTests(unittest.TestCase):
    def test_clock_sync_string_and_no_authentication_headers(self):
        opener = Opener([{"success": True, "errorCode": 0, "data": {"systemTime": str(int(time.time()*1000))}},
                         {"success": True, "errorCode": 0, "data": []}])
        archive = []
        client = WebsiteClient(lambda *args: archive.append(args) or len(archive), opener=opener)
        with patch("cs_youoweme.collectors.website.time.sleep"):
            data, request = client.call(KLINE, {"typeVal": "source-id", "type": 1})
        self.assertEqual((data, request), ([], 2))
        self.assertEqual(len(archive), 2)
        for req in opener.calls:
            self.assertFalse({"authorization", "cookie", "access-token"} & {k.lower() for k in req.headers})
        self.assertEqual(freshness_timestamp(1748707200123), "1748707200129")

    def test_http429_is_not_retried(self):
        error = urllib.error.HTTPError("https://www.steamdt.com/api", 429, "limit", {}, None)
        opener = Opener([error])
        client = WebsiteClient(lambda *args: 1, opener=opener)
        with self.assertRaises(AccessStopped):
            client.call(KLINE)
        self.assertEqual(len(opener.calls), 1)

    def test_success_false_stops_and_does_not_echo_response_message(self):
        opener = Opener([{"success": False, "errorCode": 30008, "errorMsg": "private reflected input"}])
        client = WebsiteClient(lambda *args: 1, opener=opener)
        with self.assertRaises(AccessStopped) as caught:
            client.call(KLINE)
        self.assertNotIn("private", str(caught.exception))
