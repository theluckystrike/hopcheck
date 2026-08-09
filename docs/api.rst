API reference
=============

Everything listed here is importable straight from ``hopcheck``.

Walking a chain
---------------

.. autofunction:: hopcheck.trace

.. autofunction:: hopcheck.trace_all

.. autofunction:: hopcheck.fetch_once

Data
----

.. autoclass:: hopcheck.Trace
   :members:
   :undoc-members:

.. autoclass:: hopcheck.Hop
   :members:
   :undoc-members:

.. autoclass:: hopcheck.Finding
   :members:
   :undoc-members:

Pure helpers
------------

These make no network calls and can be tested in isolation.

.. autofunction:: hopcheck.findings_for

.. autofunction:: hopcheck.method_after

.. autofunction:: hopcheck.parse_meta_refresh

.. autofunction:: hopcheck.parse_refresh_value

Defaults
--------

.. code-block:: python

   DEFAULT_USER_AGENT = "hopcheck/0.1 (+https://github.com/theluckystrike/hopcheck)"
   DEFAULT_TIMEOUT = 20.0
   DEFAULT_MAX_HOPS = 10
