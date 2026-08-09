Methodology
===========

Everything hopcheck does follows from one decision: **the client never follows
a redirect**. Each hop is an explicit request whose response is kept whole.
This page explains what that buys, hop by hop, and where the judgement calls
are.

One request per hop
-------------------

``urllib`` is opened with a redirect handler whose ``redirect_request`` returns
``None``, which disables automatic following. A ``3xx`` therefore arrives as an
``HTTPError``, and hopcheck treats it as data rather than as a failure: status,
headers, the raw ``Location`` string, and the URL that ``Location`` resolves to
are all recorded on the :class:`~hopcheck.Hop`. Only then does the walk decide
whether to make another request.

The consequence is that a chain of three redirects produces four
:class:`~hopcheck.Hop` records, not one final response. Nothing is collapsed.

Read the headers of every hop, not only the last
------------------------------------------------

An auto-following client shows you the headers of the destination. The
interesting headers are usually earlier: the ``Location`` that was wrong, the
``Cache-Control`` on a ``301`` that will make the mistake sticky in every
intermediary for a year, the ``Set-Cookie`` that explains why the chain behaves
differently in a browser. hopcheck keeps the response headers of every hop,
lower-cased, on ``hop.headers``.

When you only want to eyeball a single response by hand rather than script
anything, a browser-side inspector is quicker than installing a package —
`Zovo's HTTP header analyzer <https://zovo.one/free-tools/http-header-analyzer>`_
prints the response headers for one URL and needs nothing installed. hopcheck's
reason to exist starts at the second URL, and at the second hop.

HEAD first, GET when it has to
------------------------------

The default method is ``HEAD``, because a redirect chain can usually be walked
without transferring a single body. Two things make hopcheck fall back to
``GET``:

1. A server that answers ``405 Method Not Allowed`` or ``501 Not Implemented``
   to ``HEAD``. Plenty do, and treating that as the end of the chain would be a
   false result, so the same URL is retried once with ``GET`` and the hop is
   annotated. ``--no-head-fallback`` turns this off.
2. A final response that says ``text/html``. A refresh directive lives in the
   body, and a ``HEAD`` has no body, so the last hop is re-fetched once with
   ``GET`` in order to look. ``--no-meta-refresh`` turns this off, at the cost
   of missing refresh-based redirects entirely.

Both fallbacks are visible in the output: the hop records the method that was
actually used.

Relative ``Location`` values are resolved, and said so
------------------------------------------------------

RFC 9110 permits a relative reference in ``Location``, and most servers emit
one. hopcheck stores the raw header value in ``location_raw`` and the value
resolved against the requesting URL in ``location_resolved``, and raises
``RELATIVE_LOCATION`` at ``info`` severity so the resolution is never silent.
That distinction matters more often than it sounds: a ``Location`` of
``example.com/x`` with no scheme is a *path*, not a host, and resolves to
``https://original-host/example.com/x``.

Related, and a real source of broken chains: characters in a ``Location`` that
should have been percent-encoded and were not. hopcheck resolves the value as
given rather than trying to repair it, because repairing it would hide the bug.
If a raw ``Location`` looks wrong in the output, encoding it correctly with
something like `Zovo's URL encoder <https://zovo.one/free-tools/url-encoder>`_
and comparing the two strings is the fastest way to confirm that the server,
and not the client, is at fault.

Downgrades to plain http are errors, not warnings
-------------------------------------------------

If an ``https`` hop redirects to ``http``, hopcheck raises
``PROTOCOL_DOWNGRADE`` at ``error`` severity. This is the one place the package
takes a firm position rather than merely reporting: there is no benign reason
for a secure hop to hand the user to an insecure one, and a chain that does it
exposes the rest of the walk. In practice the cause is usually a server config
built before TLS was terminated in front of it, or a certificate that stopped
validating and a redirect added to route around the symptom — checking what the
origin is actually serving on 443, with a certificate inspector such as
`Zovo's SSL checker <https://zovo.one/free-tools/ssl-checker>`_, normally
settles which of the two it is in one look.

Method rewriting is modelled, not guessed
-----------------------------------------

:func:`hopcheck.method_after` implements the rule a conforming client uses:
``307`` and ``308`` preserve the method; ``303`` switches to ``GET`` unless the
request was ``HEAD``; ``301`` and ``302`` are historically rewritten to ``GET``
for anything that is not already ``GET`` or ``HEAD``. hopcheck itself only ever
issues ``GET`` and ``HEAD``, so the function is there for callers reasoning
about ``POST`` chains — it is a pure function with its own tests, and it gives
the same answer hopcheck would give.

Loops end the walk, they do not exhaust it
------------------------------------------

Every URL requested in a chain is remembered. When the next hop would repeat
one, hopcheck stops immediately, records the would-be URL as an unrequested
hop, and raises ``LOOP``. A loop is therefore detected in the number of hops it
actually takes, not after burning through ``--max-hops``. ``MAX_HOPS_EXCEEDED``
is reserved for chains that keep producing genuinely new URLs — the paginated
redirect, the tracker that appends a parameter each time — which is a different
bug and deserves a different code.

Refresh directives are followed and flagged
-------------------------------------------

Two non-status redirect mechanisms are recognised: an HTML
``<meta http-equiv="refresh">`` in the body, and the non-standard ``Refresh:``
response header that some servers still emit. Both are parsed by the same
routine, both are followed by default, and both raise ``META_REFRESH`` at
``warn`` severity, because they are not HTTP redirects and are treated
inconsistently by clients and crawlers. A ``content`` value with no ``url=``
part is a reload, not a redirect, and is ignored.

What hopcheck does not decide
-----------------------------

hopcheck reports what a hop *did*. It does not tell you whether a given search
engine will consolidate a given redirect, whether a chain costs you ranking, or
whether a ``302`` should have been a ``301`` in your particular case — it says
``TEMPORARY_REDIRECT`` at ``info`` and leaves the judgement where it belongs.
Claims of that kind depend on undocumented, changing third-party behaviour, and
a tool that asserts them is asserting something it cannot check.
