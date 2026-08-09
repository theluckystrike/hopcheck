Findings reference
==================

Every observation hopcheck makes is a :class:`~hopcheck.Finding` with a stable
``code``, a ``severity``, an optional ``hop_index`` and a human-readable
``detail``. **Match on the code, not on the sentence** — codes are part of the
public interface and will not change meaning within a major version; the
wording of ``detail`` may be improved at any time.

Severities
----------

``error``
    Something is wrong with the chain. Any error finding makes
    :attr:`Trace.ok <hopcheck.Trace.ok>` false and the CLI exit ``1``.

``warn``
    Worth a human look, but not necessarily a defect. Does not affect the exit
    code.

``info``
    A fact about the chain that is useful in a report and is not a problem.

The codes
---------

``REQUEST_FAILED`` (error)
    The request never completed: DNS failure, refused connection, TLS error,
    timeout. The hop has ``status = None`` and ``kind = "error"``, and the
    exception type and message are in ``detail``. A chain that fails on hop
    zero is not the same as a chain that 404s, and hopcheck keeps them apart.

``LOOP`` (error)
    A URL already requested in this chain came round again. The walk stops at
    that point. See :doc:`methodology` for why this is distinct from
    ``MAX_HOPS_EXCEEDED``.

``MAX_HOPS_EXCEEDED`` (error)
    The chain produced ``--max-hops`` requests without settling, and every URL
    was new. Either the limit is too low for a legitimately long chain, or the
    server is generating fresh URLs indefinitely.

``MISSING_LOCATION`` (error)
    A ``301``, ``302``, ``303``, ``307`` or ``308`` arrived with no
    ``Location`` header. There is nowhere to go, so the chain ends there, and
    the response is reported as final with its ``3xx`` status intact.

``PROTOCOL_DOWNGRADE`` (error)
    An ``https`` hop redirected to ``http``.

``FINAL_NOT_OK`` (error or warn)
    The chain did not end on a ``2xx``. It is an ``error`` when the final
    status is ``4xx`` or ``5xx``, or when the final hop was itself a redirect
    that could not be walked; ``warn`` otherwise, which in practice means a
    ``3xx`` that stopped for a structural reason already reported by another
    code.

``MULTI_HOP`` (warn)
    More than one redirect before the final response. One hop is normal —
    ``http`` to ``https``, or a canonical host. Two or more usually means two
    rules were added at different times and nobody collapsed them.

``CROSS_HOST`` (warn)
    The hostname the chain ended on differs from the one it started on. Often
    intended, as with a domain migration. Occasionally the first sign that a
    URL now points at a parking page or a URL shortener's interstitial.

``META_REFRESH`` (warn)
    A hop came from an HTML refresh directive or a ``Refresh:`` header rather
    than an HTTP status.

``RELATIVE_LOCATION`` (info)
    ``Location`` was a relative reference. The raw value and the resolved value
    are both in the finding and on the hop.

``HOST_CHANGE`` (info)
    One specific hop crossed a host boundary. Distinct from ``CROSS_HOST``,
    which compares only the two endpoints: a chain can leave its host and come
    back, and only the per-hop code will show it.

``TEMPORARY_REDIRECT`` (info)
    A ``302`` or ``307`` appeared in the chain.

Using the codes in CI
---------------------

The exit code alone is enough for most gates:

.. code-block:: console

   $ hopcheck --quiet https://example.com/a https://example.com/b || exit 1

For a policy of your own, read the JSON and decide:

.. code-block:: python

   from hopcheck import trace

   BLOCKING = {"LOOP", "PROTOCOL_DOWNGRADE", "REQUEST_FAILED"}

   t = trace(url)
   bad = [f for f in t.findings if f.code in BLOCKING]
   if bad:
       raise SystemExit("\n".join(f"{f.code}: {f.detail}" for f in bad))

This is the shape that suits a build pipeline which ships many sites rather
than one. When a generator stands up dozens of small sites, no single redirect
map is complicated, but the *number* of them means nobody re-reads any of them,
and a stale rule survives for months. The discipline that works there is the
one the `AI Website Pipeline method page
<https://aiwebsitepipeline.com/method.html>`_ describes for its own build
stages: a stage that cannot produce its number halts the run instead of passing
it forward, because "could not check" is not "fine". A redirect audit is cheap
enough to be one of those stages, and an exit code is all it needs to be one.
