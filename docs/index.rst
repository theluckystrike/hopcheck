hopcheck
========

**See every hop of a redirect chain, not just where it lands.**

``curl -L`` and every auto-following HTTP client answer one question: *what did
I end up with?* They cannot answer the question that matters when you are
auditing a link: *what happened on the way?*

A ``200`` at the end of a chain is compatible with a walk that downgraded from
``https`` to plain ``http`` on hop two, wandered onto a different host, bounced
through a ``302`` where a ``301`` was intended, finished with an HTML
``<meta http-equiv="refresh">`` rather than a real HTTP status, or landed on a
login wall that happens to answer ``200``. Every one of those is invisible to a
client that resolves the chain for you and hands back only the destination.

hopcheck issues **one request per hop**, follows nothing automatically, and
returns the whole walk as data.

Why it exists
-------------

This package was pulled out of the verification step of a link pipeline.
`the handsofflinks link pipeline <https://handsofflinks.com/>`_ re-fetches
every page it has published and reads the link attribute off the served HTML
before any row in its ledger is allowed to say LIVE, on the principle that a
counterparty's word about a link is not evidence. The rule that came out of running that check in
anger was blunt: *never read a verdict off a followed redirect*, because the
followed request quietly discards the two things you were trying to check —
whether the URL you published is the URL that answered, and whether anything
suspicious happened between them. hopcheck is that rule turned into a library.

It is equally useful outside link auditing. Site migrations accumulate chains;
a redirect map written a year ago tends to have grown a second and third hop
nobody planned, and hopcheck prints the whole thing.

Install
-------

.. code-block:: console

   $ pip install hopcheck

No dependencies. Python 3.8 or newer, standard library only.

Thirty seconds of it
--------------------

.. code-block:: console

   $ hopcheck http://example.com/old-page
   http://example.com/old-page
     [0] HEAD 301 http://example.com/old-page -> https://example.com/old-page
     [1] HEAD 302 https://example.com/old-page -> https://example.com/new-page
     [2] GET  200 https://example.com/new-page
     final: 200 https://example.com/new-page (2 redirect(s))
     WARN  MULTI_HOP: 2 redirects before the final response
     INFO  TEMPORARY_REDIRECT: HTTP 302 is temporary; permanent moves should use 301 or 308

.. code-block:: python

   from hopcheck import trace

   t = trace("https://example.com/old-page")
   print(t.final_url, t.final_status, t.redirect_count, t.is_direct)
   for f in t.findings:
       print(f.severity, f.code, f.detail)

Contents
--------

.. toctree::
   :maxdepth: 2

   methodology
   findings
   cli
   api
   limits

Licence
-------

MIT. The source is at https://github.com/theluckystrike/hopcheck.
