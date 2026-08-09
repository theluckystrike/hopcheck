# hopcheck

**See every hop of a redirect chain, not just where it lands.**

`curl -L` and every auto-following HTTP client answer one question: *what did I
end up with?* They cannot answer the question that matters when you are
auditing a link: *what happened on the way?*

A `200` at the end is compatible with a chain that

- downgraded from `https` to plain `http` on hop two,
- wandered onto a different host,
- bounced through a `302` that a search engine will not consolidate the way a
  `301` is consolidated,
- ended with an HTML `<meta http-equiv="refresh">` rather than a real HTTP
  status, or
- landed on a login wall that happens to return `200`.

hopcheck issues **one request per hop**, follows nothing automatically, and
returns the whole walk as data.

## Install

hopcheck is not on PyPI. Install it from source:

```
pip install git+https://github.com/theluckystrike/hopcheck
```

There are no dependencies. Python 3.8 or newer, standard library only.

## Command line

```
$ hopcheck http://example.com/old-page
http://example.com/old-page
  [0] HEAD 301 http://example.com/old-page -> https://example.com/old-page
  [1] HEAD 302 https://example.com/old-page -> https://example.com/new-page
  [2] GET  200 https://example.com/new-page
  final: 200 https://example.com/new-page (2 redirect(s))
  WARN  MULTI_HOP: 2 redirects before the final response
  INFO  TEMPORARY_REDIRECT: HTTP 302 is temporary; permanent moves should use 301 or 308
```

`--json` emits the same walk as machine-readable JSON. The exit code is `0`
when no finding has `error` severity and `1` otherwise, so it drops into CI
without any parsing.

## Library

```python
from hopcheck import trace

t = trace("https://example.com/old-page")
print(t.final_url, t.final_status, t.redirect_count, t.is_direct)
for f in t.findings:
    print(f.severity, f.code, f.detail)
```

## What it reports

| code | severity | meaning |
| --- | --- | --- |
| `REQUEST_FAILED` | error | the request itself failed (DNS, TLS, connection, timeout) |
| `LOOP` | error | a URL already visited in this chain came round again |
| `MAX_HOPS_EXCEEDED` | error | the chain had not settled within `--max-hops` |
| `MISSING_LOCATION` | error | a 3xx arrived with no `Location` header |
| `PROTOCOL_DOWNGRADE` | error | an `https` hop redirected to `http` |
| `FINAL_NOT_OK` | error / warn | the chain did not end on a 2xx |
| `MULTI_HOP` | warn | more than one redirect before the final response |
| `CROSS_HOST` | warn | the chain ended on a different host than it started on |
| `META_REFRESH` | warn | a hop came from a refresh directive, not an HTTP status |
| `RELATIVE_LOCATION` | info | `Location` was relative and had to be resolved |
| `HOST_CHANGE` | info | one hop crossed a host boundary |
| `TEMPORARY_REDIRECT` | info | a 302 or 307 in the chain |

## Scope limits, stated plainly

- **No JavaScript.** A redirect performed by `location.href` in a script is
  invisible to hopcheck, and it will report the page as the final response.
- **No cookies and no session state.** A chain that only redirects for a
  logged-in user will not reproduce here.
- **One request at a time.** There is no concurrency, on purpose: this is an
  auditing tool, not a crawler.
- **Meta refresh is read from the first 64 KiB** of the body only.
- **HEAD then GET.** With the default `--method HEAD`, a final response that
  says `text/html` is re-fetched once with `GET` so the body can be scanned for
  a refresh. That is two requests for the last hop. `--no-meta-refresh` skips it.
- hopcheck reports what a hop *did*. Whether a particular search engine
  consolidates a particular redirect is a matter for that search engine, and
  this package makes no claim about it.

## Documentation

<https://hopcheck.readthedocs.io/>

## Licence

MIT. See `LICENSE`.
