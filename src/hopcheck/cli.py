"""Command line entry point for hopcheck."""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Sequence

from .core import DEFAULT_MAX_HOPS, DEFAULT_TIMEOUT, DEFAULT_USER_AGENT, Trace, trace

_ARROW = "->"


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser. Exposed so the docs can render it."""
    p = argparse.ArgumentParser(
        prog="hopcheck",
        description="Walk a redirect chain one hop at a time and report what each hop did.",
    )
    p.add_argument("url", nargs="+", help="one or more URLs to trace")
    p.add_argument("--method", default="HEAD", choices=["HEAD", "GET"],
                   help="method for the first request (default: HEAD)")
    p.add_argument("--max-hops", type=int, default=DEFAULT_MAX_HOPS,
                   help=f"stop after this many requests (default: {DEFAULT_MAX_HOPS})")
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                   help=f"per-request timeout in seconds (default: {DEFAULT_TIMEOUT})")
    p.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="User-Agent to send")
    p.add_argument("--no-meta-refresh", action="store_true",
                   help="treat an HTML refresh as the end of the chain")
    p.add_argument("--no-head-fallback", action="store_true",
                   help="do not retry with GET when a server refuses HEAD")
    p.add_argument("--json", action="store_true", help="emit JSON instead of text")
    p.add_argument("--quiet", action="store_true", help="print findings only, not the hop table")
    return p


def format_text(t: Trace) -> List[str]:
    """Render one trace as plain text lines."""
    lines = [f"{t.start_url}"]
    for hop in t.hops:
        status = hop.status if hop.status is not None else "ERR"
        tail = ""
        if hop.location_resolved:
            tail = f" {_ARROW} {hop.location_resolved}"
        elif hop.error:
            tail = f" {hop.error}"
        lines.append(f"  [{hop.index}] {hop.method} {status} {hop.url}{tail}")
    lines.append(f"  final: {t.final_status} {t.final_url} "
                 f"({t.redirect_count} redirect(s))")
    return lines


def format_findings(t: Trace) -> List[str]:
    if not t.findings:
        return ["  findings: none"]
    return [f"  {f.severity.upper():5s} {f.code}: {f.detail}" for f in t.findings]


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI. Returns 0 when every chain is free of error findings."""
    args = build_parser().parse_args(argv)
    assert args.url, "argparse guarantees at least one URL"
    traces = [
        trace(u, method=args.method, max_hops=args.max_hops, timeout=args.timeout,
              user_agent=args.user_agent,
              follow_meta_refresh=not args.no_meta_refresh,
              head_fallback=not args.no_head_fallback)
        for u in args.url
    ]
    if args.json:
        payload = [t.to_dict() for t in traces]
        print(json.dumps(payload if len(payload) > 1 else payload[0], indent=2))
    else:
        for t in traces:
            if not args.quiet:
                print("\n".join(format_text(t)))
            else:
                print(t.start_url)
            print("\n".join(format_findings(t)))
    return 0 if all(t.ok for t in traces) else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
