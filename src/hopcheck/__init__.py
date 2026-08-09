"""hopcheck - see every hop of a redirect chain, not just where it lands.

``curl -L`` and every auto-following HTTP client answer one question: what did
I end up with? They cannot answer the question that matters when you are
auditing a link: *what happened on the way*. A 200 at the end is compatible
with a chain that downgraded to plain http, wandered onto a different host,
bounced through a temporary redirect a search engine will not consolidate, or
finished with an HTML refresh rather than a real HTTP status.

hopcheck issues one request per hop, follows nothing automatically, and returns
the whole walk as data::

    from hopcheck import trace

    t = trace("https://example.com/old-page")
    print(t.final_url, t.final_status, t.redirect_count)
    for f in t.findings:
        print(f.severity, f.code, f.detail)

Standard library only. MIT licensed.
"""

from .core import (
    DEFAULT_MAX_HOPS,
    DEFAULT_TIMEOUT,
    DEFAULT_USER_AGENT,
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

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_MAX_HOPS",
    "DEFAULT_TIMEOUT",
    "DEFAULT_USER_AGENT",
    "Finding",
    "Hop",
    "Trace",
    "__version__",
    "fetch_once",
    "findings_for",
    "method_after",
    "parse_meta_refresh",
    "parse_refresh_value",
    "trace",
    "trace_all",
]
