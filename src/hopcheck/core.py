"""Core primitives for hopcheck. Standard library only, no dependencies.

hopcheck walks a redirect chain **one hop at a time** and records what each hop
actually did. It never hands the chain to the HTTP library to resolve, because
an auto-following client collapses the whole chain into a single final response
and throws away the evidence: the status of each hop, whether ``Location`` was
relative, whether the scheme was downgraded, whether the host changed, and
whether the last leg was an HTML ``<meta http-equiv="refresh">`` rather than a
real HTTP redirect.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Dict, List, Optional, Sequence, Tuple

__all__ = [
    "DEFAULT_MAX_HOPS",
    "DEFAULT_TIMEOUT",
    "DEFAULT_USER_AGENT",
    "Finding",
    "Hop",
    "Trace",
    "fetch_once",
    "findings_for",
    "method_after",
    "parse_meta_refresh",
    "parse_refresh_value",
    "trace",
]

DEFAULT_USER_AGENT = "hopcheck/0.1 (+https://github.com/theluckystrike/hopcheck)"
DEFAULT_TIMEOUT = 20.0
DEFAULT_MAX_HOPS = 10

#: Only this many bytes of a response body are scanned for a meta refresh.
#: A refresh that appears after 64 KiB of markup is not one a browser would be
#: guaranteed to honour early, and reading whole bodies to find one is waste.
META_REFRESH_SCAN_BYTES = 65536

REDIRECT_STATUSES = (301, 302, 303, 307, 308)

_REFRESH_URL_RE = re.compile(
    r"""^\s*[0-9.]*\s*(?:;\s*)?url\s*=\s*['"]?(?P<url>[^'"]+?)['"]?\s*$""",
    re.IGNORECASE,
)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Disable urllib's automatic redirect following."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


class _MetaRefreshFinder(HTMLParser):
    """Collect the ``content`` value of every ``<meta http-equiv=refresh>``."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.values: List[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: D102
        if tag.lower() != "meta":
            return
        pairs = {k.lower(): (v or "") for k, v in attrs}
        if pairs.get("http-equiv", "").strip().lower() == "refresh":
            self.values.append(pairs.get("content", ""))


@dataclass(frozen=True)
class Finding:
    """One machine-readable observation about a chain.

    Attributes:
        code: Stable identifier, e.g. ``PROTOCOL_DOWNGRADE``. Safe to match on.
        severity: ``error``, ``warn`` or ``info``. Only ``error`` fails the CLI.
        hop_index: Index of the hop the finding is about, or ``None`` if it is
            about the chain as a whole.
        detail: Human-readable sentence. Wording may change between releases.
    """

    code: str
    severity: str
    hop_index: Optional[int]
    detail: str


@dataclass
class Hop:
    """One request/response pair in a chain, captured without following it.

    ``kind`` is ``http`` for a 3xx with a ``Location``, ``meta-refresh`` when
    the redirect came from the HTML body or a ``Refresh:`` header, ``final``
    for a response that does not redirect, and ``error`` when the request
    itself failed.
    """

    index: int
    url: str
    method: str
    status: Optional[int]
    kind: str
    location_raw: Optional[str] = None
    location_resolved: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    body_bytes: int = 0
    error: Optional[str] = None

    @property
    def content_type(self) -> Optional[str]:
        return self.headers.get("content-type")

    @property
    def is_redirect(self) -> bool:
        return self.kind in ("http", "meta-refresh")


@dataclass
class Trace:
    """The full walk of a chain, from ``start_url`` to wherever it ended."""

    start_url: str
    hops: List[Hop] = field(default_factory=list)
    max_hops: int = DEFAULT_MAX_HOPS
    truncated: bool = False
    findings: List[Finding] = field(default_factory=list)

    @property
    def hop_count(self) -> int:
        return len(self.hops)

    @property
    def redirect_count(self) -> int:
        return sum(1 for h in self.hops if h.is_redirect)

    @property
    def final_hop(self) -> Optional[Hop]:
        return self.hops[-1] if self.hops else None

    @property
    def final_url(self) -> Optional[str]:
        return self.hops[-1].url if self.hops else None

    @property
    def final_status(self) -> Optional[int]:
        return self.hops[-1].status if self.hops else None

    @property
    def ok(self) -> bool:
        """True when nothing of ``error`` severity was found."""
        return not any(f.severity == "error" for f in self.findings)

    @property
    def is_direct(self) -> bool:
        """True when the start URL answered 2xx with no redirect at all."""
        s = self.final_status
        return self.hop_count == 1 and s is not None and 200 <= s < 300

    def to_dict(self) -> Dict[str, object]:
        """A JSON-serialisable view, used by ``hopcheck --json``."""
        return {
            "start_url": self.start_url,
            "final_url": self.final_url,
            "final_status": self.final_status,
            "hop_count": self.hop_count,
            "redirect_count": self.redirect_count,
            "truncated": self.truncated,
            "direct": self.is_direct,
            "ok": self.ok,
            "hops": [
                {
                    "index": h.index,
                    "url": h.url,
                    "method": h.method,
                    "status": h.status,
                    "kind": h.kind,
                    "location_raw": h.location_raw,
                    "location_resolved": h.location_resolved,
                    "content_type": h.content_type,
                    "bytes": h.body_bytes,
                    "error": h.error,
                }
                for h in self.hops
            ],
            "findings": [
                {
                    "code": f.code,
                    "severity": f.severity,
                    "hop_index": f.hop_index,
                    "detail": f.detail,
                }
                for f in self.findings
            ],
        }


def parse_refresh_value(value: str) -> Optional[str]:
    """Extract the URL from a ``Refresh`` value such as ``0; url=/next``.

    Returns ``None`` for a refresh that only reloads the current page, which is
    a real pattern and is not a redirect.

    >>> parse_refresh_value("0; url=/next")
    '/next'
    >>> parse_refresh_value("5") is None
    True
    """
    assert isinstance(value, str), "refresh value must be a string"
    m = _REFRESH_URL_RE.match(value)
    if not m:
        return None
    url = m.group("url").strip()
    return url or None


def parse_meta_refresh(html: str) -> Optional[str]:
    """Return the URL of the first meta refresh in ``html``, or ``None``.

    Only the first ``META_REFRESH_SCAN_BYTES`` characters are parsed. Malformed
    markup is tolerated: the standard library parser is lenient, and a meta tag
    it cannot see is reported as no refresh rather than as an error.
    """
    assert isinstance(html, str), "html must be a string"
    finder = _MetaRefreshFinder()
    try:
        finder.feed(html[:META_REFRESH_SCAN_BYTES])
    except Exception:  # pragma: no cover - html.parser is lenient by design
        return None
    for value in finder.values:
        url = parse_refresh_value(value)
        if url:
            return url
    return None


def method_after(status: int, method: str) -> str:
    """The method a conforming client uses for the next hop.

    303 always switches to ``GET`` except for ``HEAD``; 301 and 302 are
    historically rewritten to ``GET`` for anything that is not already ``GET``
    or ``HEAD``; 307 and 308 preserve the method. hopcheck itself only ever
    issues ``GET`` and ``HEAD``, so this function exists so that callers
    reasoning about POST chains get the same answer hopcheck would give.

    >>> method_after(308, "POST")
    'POST'
    >>> method_after(302, "POST")
    'GET'
    """
    assert isinstance(status, int), "status must be an int"
    assert method, "method must be a non-empty string"
    method = method.upper()
    if status in (307, 308):
        return method
    if status == 303:
        return method if method == "HEAD" else "GET"
    if status in (301, 302):
        return method if method in ("GET", "HEAD") else "GET"
    return method


def _read_body(resp, limit: int) -> bytes:
    try:
        return resp.read(limit)
    except Exception:  # pragma: no cover - socket-level failure mid-read
        return b""


def _decode(raw: bytes, headers: Dict[str, str]) -> str:
    charset = "utf-8"
    ctype = headers.get("content-type", "")
    if "charset=" in ctype:
        charset = ctype.split("charset=", 1)[1].split(";")[0].strip().strip('"') or "utf-8"
    try:
        return raw.decode(charset, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def fetch_once(
    url: str,
    method: str = "HEAD",
    timeout: float = DEFAULT_TIMEOUT,
    user_agent: str = DEFAULT_USER_AGENT,
    index: int = 0,
    read_body: bool = False,
) -> Hop:
    """Issue exactly one request and return the :class:`Hop` it produced.

    Redirects are never followed. A 3xx is returned as data, with the raw
    ``Location`` value preserved next to the value resolved against ``url``.
    """
    assert url, "url must be a non-empty string"
    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(url, method=method.upper())
    req.add_header("User-Agent", user_agent)
    req.add_header("Accept", "text/html,application/xhtml+xml,*/*;q=0.8")
    try:
        resp = opener.open(req, timeout=timeout)
        status, headers = resp.status, dict(resp.headers.items())
        raw = _read_body(resp, META_REFRESH_SCAN_BYTES) if read_body else b""
        resp.close()
    except urllib.error.HTTPError as exc:
        status, headers = exc.code, dict(exc.headers.items())
        raw = _read_body(exc, META_REFRESH_SCAN_BYTES) if read_body else b""
        exc.close()
    except Exception as exc:
        return Hop(index=index, url=url, method=method.upper(), status=None,
                   kind="error", error=f"{type(exc).__name__}: {exc}")
    lower = {k.lower(): v for k, v in headers.items()}
    hop = Hop(index=index, url=url, method=method.upper(), status=status,
              kind="final", headers=lower, body_bytes=len(raw))
    _classify(hop, lower, raw)
    return hop


def _classify(hop: Hop, headers: Dict[str, str], raw: bytes) -> None:
    """Decide whether ``hop`` redirects, and to where. Mutates ``hop``."""
    if hop.status in REDIRECT_STATUSES and headers.get("location"):
        hop.kind = "http"
        hop.location_raw = headers["location"]
    elif headers.get("refresh"):
        target = parse_refresh_value(headers["refresh"])
        if target:
            hop.kind = "meta-refresh"
            hop.location_raw = target
    elif raw and "html" in headers.get("content-type", "text/html"):
        target = parse_meta_refresh(_decode(raw, headers))
        if target:
            hop.kind = "meta-refresh"
            hop.location_raw = target
    if hop.location_raw is not None:
        hop.location_resolved = urllib.parse.urljoin(hop.url, hop.location_raw.strip())


def _host(url: str) -> str:
    return (urllib.parse.urlsplit(url).hostname or "").lower()


def _scheme(url: str) -> str:
    return urllib.parse.urlsplit(url).scheme.lower()


def _is_absolute(location: str) -> bool:
    return bool(urllib.parse.urlsplit(location.strip()).scheme)


def _chain_findings(t: Trace) -> List[Finding]:
    out: List[Finding] = []
    if t.truncated:
        out.append(Finding("MAX_HOPS_EXCEEDED", "error", None,
                           f"chain did not settle within {t.max_hops} hops"))
    seen: Dict[str, int] = {}
    for hop in t.hops:
        if hop.url in seen:
            out.append(Finding("LOOP", "error", hop.index,
                               f"{hop.url} was already requested at hop {seen[hop.url]}"))
            break
        seen[hop.url] = hop.index
    if t.redirect_count > 1:
        out.append(Finding("MULTI_HOP", "warn", None,
                           f"{t.redirect_count} redirects before the final response"))
    if t.hops and t.final_url and _host(t.start_url) != _host(t.final_url):
        out.append(Finding("CROSS_HOST", "warn", None,
                           f"chain left {_host(t.start_url)} and ended on {_host(t.final_url)}"))
    return out


def _hop_findings(hop: Hop) -> List[Finding]:
    out: List[Finding] = []
    if hop.kind == "error":
        out.append(Finding("REQUEST_FAILED", "error", hop.index, hop.error or "request failed"))
        return out
    if hop.status in REDIRECT_STATUSES and not hop.location_raw:
        out.append(Finding("MISSING_LOCATION", "error", hop.index,
                           f"HTTP {hop.status} with no Location header"))
    if hop.kind == "meta-refresh":
        out.append(Finding("META_REFRESH", "warn", hop.index,
                           "redirect came from a refresh directive, not an HTTP status; "
                           "search engines treat these inconsistently"))
    if hop.location_raw and not _is_absolute(hop.location_raw):
        out.append(Finding("RELATIVE_LOCATION", "info", hop.index,
                           f"Location was relative ({hop.location_raw!r}) and was resolved "
                           f"to {hop.location_resolved}"))
    if hop.location_resolved:
        if _scheme(hop.url) == "https" and _scheme(hop.location_resolved) == "http":
            out.append(Finding("PROTOCOL_DOWNGRADE", "error", hop.index,
                               "redirected from https to http"))
        if _host(hop.url) != _host(hop.location_resolved):
            out.append(Finding("HOST_CHANGE", "info", hop.index,
                               f"{_host(hop.url)} -> {_host(hop.location_resolved)}"))
    if hop.status in (302, 307) and hop.kind == "http":
        out.append(Finding("TEMPORARY_REDIRECT", "info", hop.index,
                           f"HTTP {hop.status} is temporary; permanent moves should use 301 or 308"))
    return out


def findings_for(t: Trace) -> List[Finding]:
    """Derive the finding list for an already-walked :class:`Trace`.

    Pure: it reads the hops and returns observations, so it can be exercised on
    a hand-built ``Trace`` without any network at all.
    """
    assert isinstance(t, Trace), "findings_for takes a Trace"
    out: List[Finding] = list(_chain_findings(t))
    for hop in t.hops:
        out.extend(_hop_findings(hop))
    final = t.final_hop
    if final is not None and final.kind != "error":
        if final.status is not None and not 200 <= final.status < 300:
            severity = "error" if final.status >= 400 or final.is_redirect else "warn"
            out.append(Finding("FINAL_NOT_OK", severity, final.index,
                               f"chain ended on HTTP {final.status}"))
    return out


def _next_method(hop: Hop, method: str) -> str:
    if hop.kind == "meta-refresh":
        return "GET" if method != "HEAD" else "HEAD"
    return method_after(hop.status or 0, method)


def trace(
    url: str,
    method: str = "HEAD",
    max_hops: int = DEFAULT_MAX_HOPS,
    timeout: float = DEFAULT_TIMEOUT,
    user_agent: str = DEFAULT_USER_AGENT,
    follow_meta_refresh: bool = True,
    head_fallback: bool = True,
) -> Trace:
    """Walk the chain from ``url`` and return a fully populated :class:`Trace`.

    Args:
        method: ``HEAD`` by default because it is cheap. Servers that answer
            405 or 501 to ``HEAD`` are retried once with ``GET`` when
            ``head_fallback`` is set.
        max_hops: Hard ceiling on requests. A chain that has not settled by
            then is marked ``truncated`` and yields ``MAX_HOPS_EXCEEDED``.
        follow_meta_refresh: When false, an HTML refresh ends the walk and the
            page is reported as the final response.
    """
    assert url, "url must be a non-empty string"
    assert max_hops >= 1, "max_hops must be at least 1"
    t = Trace(start_url=url, max_hops=max_hops)
    current, current_method, seen = url, method.upper(), set()
    for index in range(max_hops):
        want_body = follow_meta_refresh and current_method != "HEAD"
        hop = fetch_once(current, current_method, timeout, user_agent, index, want_body)
        if (hop.status in (405, 501) and current_method == "HEAD" and head_fallback):
            current_method = "GET"
            hop = fetch_once(current, "GET", timeout, user_agent, index, follow_meta_refresh)
            hop.headers["x-hopcheck-note"] = "HEAD refused, retried with GET"
        if hop.kind == "final" and current_method == "HEAD" and follow_meta_refresh \
                and "html" in (hop.content_type or ""):
            hop = fetch_once(current, "GET", timeout, user_agent, index, True)
        t.hops.append(hop)
        if not hop.is_redirect or hop.location_resolved is None:
            break
        if hop.kind == "meta-refresh" and not follow_meta_refresh:
            break
        if hop.location_resolved in seen:
            t.hops.append(Hop(index=index + 1, url=hop.location_resolved,
                              method=current_method, status=None, kind="final",
                              error="not requested: already seen in this chain"))
            break
        seen.add(current)
        current_method = _next_method(hop, current_method)
        current = hop.location_resolved
    else:
        t.truncated = True
    t.findings = findings_for(t)
    return t


def trace_all(urls: Sequence[str], **kwargs) -> List[Trace]:
    """Trace several URLs in sequence. No concurrency, deliberately."""
    assert not isinstance(urls, str), "pass a sequence of URLs, not one string"
    return [trace(u, **kwargs) for u in urls]
