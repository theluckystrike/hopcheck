"""Tests for hopcheck. Every network test runs against a real local server.

Nothing here is mocked at the socket level: a threaded ``http.server`` is
started on 127.0.0.1 and answers real requests, so the redirect semantics being
asserted are the ones urllib and the OS actually produce.
"""

from __future__ import annotations

import http.server
import threading
import unittest
from typing import Dict, Tuple

from hopcheck import (
    Finding,
    Hop,
    Trace,
    fetch_once,
    findings_for,
    method_after,
    parse_meta_refresh,
    parse_refresh_value,
    trace,
    trace_all,
)
from hopcheck.cli import format_text, main

HTML = "text/html; charset=utf-8"


class Handler(http.server.BaseHTTPRequestHandler):
    """Routes that between them exercise every branch hopcheck cares about."""

    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # noqa: D102 - silence the test output
        return

    def _send(self, status: int, headers: Dict[str, str], body: bytes = b"") -> None:
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body and self.command != "HEAD":
            self.wfile.write(body)

    def route(self) -> Tuple[int, Dict[str, str], bytes]:
        p = self.path
        if p == "/ok":
            return 200, {"Content-Type": "text/plain"}, b"ok"
        if p == "/ok-html":
            return 200, {"Content-Type": HTML}, b"<html><body>done</body></html>"
        if p == "/one":
            return 301, {"Location": "/ok"}, b""
        if p == "/two":
            return 302, {"Location": "/one"}, b""
        if p == "/abs":
            return 308, {"Location": f"http://127.0.0.1:{self.server.server_port}/ok"}, b""
        if p == "/nowhere":
            return 302, {}, b""
        if p == "/loop-a":
            return 301, {"Location": "/loop-b"}, b""
        if p == "/loop-b":
            return 301, {"Location": "/loop-a"}, b""
        if p.startswith("/deep/"):
            n = int(p.rsplit("/", 1)[1])
            return 301, {"Location": f"/deep/{n + 1}"}, b""
        if p == "/meta":
            body = b"<html><head><meta http-equiv='refresh' content='0; url=/ok'></head></html>"
            return 200, {"Content-Type": HTML}, body
        if p == "/refresh-header":
            return 200, {"Content-Type": HTML, "Refresh": "0; url=/ok"}, b"<html></html>"
        if p == "/no-head":
            if self.command == "HEAD":
                return 405, {"Allow": "GET"}, b""
            return 200, {"Content-Type": "text/plain"}, b"get only"
        if p == "/gone":
            return 404, {"Content-Type": "text/plain"}, b"nope"
        if p == "/cross":
            return 301, {"Location": f"http://localhost:{self.server.server_port}/ok"}, b""
        return 404, {"Content-Type": "text/plain"}, b"unrouted"

    def do_GET(self):  # noqa: D102
        self._send(*self.route())

    def do_HEAD(self):  # noqa: D102
        self._send(*self.route())


class ServerCase(unittest.TestCase):
    """Base case that owns the local HTTP server."""

    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def url(self, path: str, host: str = "127.0.0.1") -> str:
        return f"http://{host}:{self.port}{path}"


class TestFetchOnce(ServerCase):
    def test_plain_200_is_final(self):
        hop = fetch_once(self.url("/ok"))
        self.assertEqual(hop.status, 200)
        self.assertEqual(hop.kind, "final")
        self.assertIsNone(hop.location_raw)

    def test_redirect_is_returned_not_followed(self):
        hop = fetch_once(self.url("/one"))
        self.assertEqual(hop.status, 301)
        self.assertEqual(hop.kind, "http")
        self.assertEqual(hop.location_raw, "/ok")
        self.assertEqual(hop.location_resolved, self.url("/ok"))

    def test_absolute_location_is_preserved(self):
        hop = fetch_once(self.url("/abs"))
        self.assertEqual(hop.location_raw, hop.location_resolved)

    def test_three_xx_without_location_is_not_a_redirect(self):
        hop = fetch_once(self.url("/nowhere"))
        self.assertEqual(hop.status, 302)
        self.assertEqual(hop.kind, "final")

    def test_connection_error_becomes_an_error_hop(self):
        hop = fetch_once("http://127.0.0.1:1/never")
        self.assertIsNone(hop.status)
        self.assertEqual(hop.kind, "error")
        self.assertTrue(hop.error)

    def test_headers_are_lowercased(self):
        hop = fetch_once(self.url("/ok"))
        self.assertIn("content-type", hop.headers)
        self.assertEqual(hop.content_type, "text/plain")


class TestTrace(ServerCase):
    def test_direct_page_is_one_hop(self):
        t = trace(self.url("/ok"))
        self.assertEqual(t.hop_count, 1)
        self.assertEqual(t.redirect_count, 0)
        self.assertTrue(t.is_direct)
        self.assertTrue(t.ok)

    def test_two_hop_chain_records_both_hops(self):
        t = trace(self.url("/two"))
        self.assertEqual([h.status for h in t.hops], [302, 301, 200])
        self.assertEqual(t.redirect_count, 2)
        self.assertEqual(t.final_url, self.url("/ok"))
        self.assertFalse(t.is_direct)

    def test_multi_hop_is_warned_about(self):
        codes = [f.code for f in trace(self.url("/two")).findings]
        self.assertIn("MULTI_HOP", codes)

    def test_relative_location_is_flagged_as_info(self):
        f = [f for f in trace(self.url("/one")).findings if f.code == "RELATIVE_LOCATION"]
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].severity, "info")

    def test_loop_is_detected_and_is_an_error(self):
        t = trace(self.url("/loop-a"))
        codes = [f.code for f in t.findings]
        self.assertIn("LOOP", codes)
        self.assertFalse(t.ok)
        self.assertLess(t.hop_count, t.max_hops)

    def test_endless_chain_is_truncated_not_infinite(self):
        t = trace(self.url("/deep/0"), max_hops=4)
        self.assertTrue(t.truncated)
        self.assertEqual(t.hop_count, 4)
        self.assertIn("MAX_HOPS_EXCEEDED", [f.code for f in t.findings])

    def test_missing_location_is_an_error(self):
        t = trace(self.url("/nowhere"))
        self.assertIn("MISSING_LOCATION", [f.code for f in t.findings])
        self.assertFalse(t.ok)

    def test_404_at_the_end_is_an_error(self):
        t = trace(self.url("/gone"))
        codes = [f.code for f in t.findings]
        self.assertIn("FINAL_NOT_OK", codes)
        self.assertFalse(t.ok)

    def test_head_refusal_falls_back_to_get(self):
        t = trace(self.url("/no-head"))
        self.assertEqual(t.final_status, 200)
        self.assertEqual(t.hops[0].method, "GET")

    def test_head_refusal_is_respected_when_fallback_is_off(self):
        t = trace(self.url("/no-head"), head_fallback=False)
        self.assertEqual(t.final_status, 405)

    def test_meta_refresh_is_followed_and_flagged(self):
        t = trace(self.url("/meta"))
        self.assertEqual(t.final_url, self.url("/ok"))
        self.assertIn("META_REFRESH", [f.code for f in t.findings])

    def test_meta_refresh_can_be_switched_off(self):
        t = trace(self.url("/meta"), follow_meta_refresh=False)
        self.assertEqual(t.final_url, self.url("/meta"))
        self.assertEqual(t.hop_count, 1)

    def test_refresh_response_header_is_honoured(self):
        t = trace(self.url("/refresh-header"))
        self.assertEqual(t.final_url, self.url("/ok"))

    def test_cross_host_hop_is_reported(self):
        t = trace(self.url("/cross"))
        codes = [f.code for f in t.findings]
        self.assertIn("HOST_CHANGE", codes)
        self.assertIn("CROSS_HOST", codes)
        self.assertEqual(t.final_status, 200)

    def test_temporary_redirect_is_informational(self):
        f = [f for f in trace(self.url("/two")).findings if f.code == "TEMPORARY_REDIRECT"]
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].severity, "info")

    def test_to_dict_round_trips_through_json(self):
        import json

        d = trace(self.url("/two")).to_dict()
        self.assertEqual(json.loads(json.dumps(d))["hop_count"], 3)

    def test_trace_all_returns_one_trace_per_url(self):
        out = trace_all([self.url("/ok"), self.url("/gone")])
        self.assertEqual([t.final_status for t in out], [200, 404])

    def test_max_hops_must_be_at_least_one(self):
        with self.assertRaises(AssertionError):
            trace(self.url("/ok"), max_hops=0)


class TestPureFunctions(unittest.TestCase):
    """No network at all - these are the parts a caller can reason about."""

    def test_method_after_preserves_on_307_and_308(self):
        self.assertEqual(method_after(307, "POST"), "POST")
        self.assertEqual(method_after(308, "PUT"), "PUT")

    def test_method_after_rewrites_on_301_302_303(self):
        self.assertEqual(method_after(301, "POST"), "GET")
        self.assertEqual(method_after(302, "POST"), "GET")
        self.assertEqual(method_after(303, "POST"), "GET")

    def test_method_after_keeps_head_on_303(self):
        self.assertEqual(method_after(303, "HEAD"), "HEAD")

    def test_method_after_leaves_non_redirects_alone(self):
        self.assertEqual(method_after(200, "POST"), "POST")

    def test_parse_refresh_value_variants(self):
        self.assertEqual(parse_refresh_value("0; url=/next"), "/next")
        self.assertEqual(parse_refresh_value("5;URL='/x'"), "/x")
        self.assertEqual(parse_refresh_value('0;url="https://e.com/"'), "https://e.com/")
        self.assertIsNone(parse_refresh_value("5"))
        self.assertIsNone(parse_refresh_value(""))

    def test_parse_meta_refresh_finds_the_first_one(self):
        html = ("<html><head><meta http-equiv='REFRESH' CONTENT='0;url=/a'>"
                "<meta http-equiv='refresh' content='0;url=/b'></head></html>")
        self.assertEqual(parse_meta_refresh(html), "/a")

    def test_parse_meta_refresh_ignores_other_meta_tags(self):
        self.assertIsNone(parse_meta_refresh("<meta name='robots' content='noindex'>"))

    def test_parse_meta_refresh_ignores_a_pure_reload(self):
        self.assertIsNone(parse_meta_refresh("<meta http-equiv='refresh' content='30'>"))

    def test_protocol_downgrade_is_an_error(self):
        t = Trace(start_url="https://a.example/")
        t.hops = [Hop(0, "https://a.example/", "HEAD", 301, "http",
                      location_raw="http://a.example/x",
                      location_resolved="http://a.example/x")]
        codes = {f.code: f.severity for f in findings_for(t)}
        self.assertEqual(codes["PROTOCOL_DOWNGRADE"], "error")

    def test_findings_for_needs_a_trace(self):
        with self.assertRaises(AssertionError):
            findings_for("https://example.com/")

    def test_finding_is_immutable(self):
        f = Finding("X", "info", 0, "d")
        with self.assertRaises(Exception):
            f.code = "Y"


class TestCli(ServerCase):
    def test_exit_zero_on_a_clean_url(self):
        self.assertEqual(main([self.url("/ok"), "--quiet"]), 0)

    def test_exit_one_on_a_broken_chain(self):
        self.assertEqual(main([self.url("/loop-a"), "--quiet"]), 1)

    def test_json_output_parses(self):
        import contextlib
        import io
        import json

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            main([self.url("/two"), "--json"])
        self.assertEqual(json.loads(buf.getvalue())["redirect_count"], 2)

    def test_text_output_lists_every_hop(self):
        lines = format_text(trace(self.url("/two")))
        self.assertEqual(len(lines), 5)
        self.assertIn("->", lines[1])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
