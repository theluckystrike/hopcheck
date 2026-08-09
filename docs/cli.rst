Command line
============

.. code-block:: text

   usage: hopcheck [-h] [--method {HEAD,GET}] [--max-hops MAX_HOPS]
                   [--timeout TIMEOUT] [--user-agent USER_AGENT]
                   [--no-meta-refresh] [--no-head-fallback] [--json] [--quiet]
                   url [url ...]

Options
-------

``--method {HEAD,GET}``
    Method for the first request. ``HEAD`` by default, because a chain can
    usually be walked without transferring a body. See :doc:`methodology` for
    the two cases where hopcheck falls back to ``GET`` anyway.

``--max-hops N``
    Hard ceiling on the number of requests, default 10. A chain that has not
    settled by then is marked truncated and yields ``MAX_HOPS_EXCEEDED``.

``--timeout SECONDS``
    Per-request timeout, default 20.

``--user-agent UA``
    The ``User-Agent`` to send. Worth setting: some servers redirect
    differently for an unknown client, and if you are auditing what a specific
    crawler sees, you should send what it sends.

``--no-meta-refresh``
    Treat an HTML refresh directive as the end of the chain rather than
    following it. Also removes the extra ``GET`` on the final HTML hop.

``--no-head-fallback``
    Do not retry with ``GET`` when a server answers ``405`` or ``501`` to
    ``HEAD``. The ``405`` is then reported as the final status.

``--json``
    Emit the walk as JSON. One object for a single URL, an array for several.

``--quiet``
    Print the findings only, without the hop table.

Exit codes
----------

===== ==================================================================
0     every chain walked was free of ``error``-severity findings
1     at least one chain produced an ``error`` finding
2     argument error, from ``argparse``
===== ==================================================================

Output
------

Text mode prints the start URL, one indented line per hop, a summary line, and
then the findings:

.. code-block:: console

   $ hopcheck https://example.com/loop
   https://example.com/loop
     [0] HEAD 301 https://example.com/loop -> https://example.com/loop2
     [1] HEAD 301 https://example.com/loop2 -> https://example.com/loop
     [2] HEAD ERR https://example.com/loop not requested: already seen in this chain
     final: None https://example.com/loop (2 redirect(s))
     ERROR LOOP: https://example.com/loop was already requested at hop 0
     WARN  MULTI_HOP: 2 redirects before the final response

The third line is not a request. When the next hop would repeat a URL, hopcheck
records where the chain *would* have gone and stops.

JSON mode
---------

.. code-block:: json

   {
     "start_url": "http://example.com/old",
     "final_url": "https://example.com/new",
     "final_status": 200,
     "hop_count": 2,
     "redirect_count": 1,
     "truncated": false,
     "direct": false,
     "ok": true,
     "hops": [
       {
         "index": 0,
         "url": "http://example.com/old",
         "method": "HEAD",
         "status": 301,
         "kind": "http",
         "location_raw": "/new",
         "location_resolved": "http://example.com/new",
         "content_type": "text/html",
         "bytes": 0,
         "error": null
       }
     ],
     "findings": [
       {"code": "RELATIVE_LOCATION", "severity": "info", "hop_index": 0,
        "detail": "Location was relative ..."}
     ]
   }

``ok`` mirrors the exit code: it is false when any finding has ``error``
severity.
