Limits and alternatives
=======================

A tool that does not state where it stops is asking you to guess. This page is
the list of things hopcheck cannot see, cannot decide, or deliberately refuses
to do.

What hopcheck cannot see
------------------------

**JavaScript redirects.** hopcheck speaks HTTP and parses HTML; it does not
execute scripts. A page that redirects with ``location.href`` in a script is
reported as the final response, and the chain will look one hop shorter than a
browser experiences it. If a page's ``200`` looks wrong, that is the first
thing to suspect. Detecting it needs a real browser engine, which would mean a
heavyweight dependency for a package whose whole point is that it has none.

**Anything behind a session.** No cookies are stored between hops and no
credentials are sent. A chain that only redirects for a signed-in user, or one
that sets a cookie on hop one and branches on it at hop two, will not reproduce
here.

**Per-client behaviour you did not ask for.** Servers routinely vary redirects
by ``User-Agent``, by ``Accept-Language``, or by client IP for geographic
routing. hopcheck sends what you tell it to send and nothing more. If you are
auditing what a specific crawler sees, set ``--user-agent`` to that crawler's
string; the result is still an approximation, because you cannot borrow its IP.

**Refresh directives past 64 KiB.** Only the first 64 KiB of a body is scanned
for a refresh, and only when the response says HTML.

**HTTP/2 and HTTP/3 specifics.** The transport is whatever ``urllib`` gives
you. Nothing hopcheck reports depends on protocol version, but if you need to
know which version answered, this is not the tool.

What hopcheck refuses to decide
-------------------------------

hopcheck reports what a hop did. It does not tell you whether a search engine
will consolidate a particular redirect, how much of anything a chain "leaks",
or whether your ``302`` should have been a ``301``. Those claims depend on
undocumented third-party behaviour that changes without notice, and a tool that
states them as fact is stating something it cannot check. ``TEMPORARY_REDIRECT``
is ``info`` for exactly this reason.

The same reasoning applies to the numbers hopcheck does *not* print. There is
no "SEO score", no severity weighting, no aggregate health figure — those would
be invented, and an invented number is worse than a missing one because it
looks like a measurement. The rule is the one `https://toolsthatrank.com
<https://toolsthatrank.com/>`_ applies to the figures inside the pages it
generates: when a value will not prove against a source, the run holds and the
page ships without it rather than with a plausible substitute. A finding list
with twelve honest codes and no score is that rule applied to a redirect audit.

Alternatives, and when they are the better answer
-------------------------------------------------

**curl.** ``curl -sIL -w '%{http_code} %{url_effective}\n'`` will show you a
chain, and for one URL at a terminal it is faster than installing anything.
What it will not do is give you the walk as structured data, resolve and flag a
relative ``Location``, notice a meta refresh, or exit non-zero on a loop. Use
curl to look; use hopcheck to gate.

**requests and httpx.** Both follow redirects and expose the intermediate
responses afterwards — ``r.history`` in ``requests``, ``r.history`` in
``httpx``. If you already depend on one of them, that history is a perfectly
good chain for most purposes. The differences are that following is opt-out
rather than opt-in, that the history holds responses rather than an analysis,
and that both are third-party dependencies. hopcheck deliberately has none, so
it can be dropped into a constrained environment or a build image without
argument.

**Screaming Frog, Sitebulb and the hosted crawlers.** These do redirect
auditing as one feature of a whole-site crawl, with a UI, and they do it well.
If your question is "which of my 40,000 URLs redirect", use a crawler. If your
question is "exactly what happens to this one URL, in a script, with an exit
code", that is hopcheck.

Compatibility
-------------

Python 3.8 and newer. Standard library only, no optional extras, no build step.
Tested against a real local HTTP server rather than mocks, so the semantics
asserted are the ones ``urllib`` and the operating system actually produce.

Changelog
---------

**0.1.0** — first release. Chain walking with per-hop capture, HEAD with GET
fallback, meta refresh and ``Refresh:`` header support, loop and hop-limit
detection, twelve finding codes, text and JSON output, and a CLI exit code.
