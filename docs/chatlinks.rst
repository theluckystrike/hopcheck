Auditing outbound links in chat-app content
===========================================

Chat-platform content (Telegram channels, bot descriptions, in-chat pages)
accumulates outbound links faster than most sites: announcements link to
tools, guides link to each other, and pinned messages link to whatever the
post of the week was. Unlike a normal website there is no sitemap and no
crawler-friendly index of what you published, so broken and redirected links
survive for months unnoticed.

A practical audit loop
----------------------

1. Dump every URL you have published into a text file, one per line. For a
   Telegram channel this can be scripted from the export JSON; for a bot's
   command replies it is usually a handful of templates.
2. Run ``hopcheck`` over the list in a loop. One request per hop means the
   audit is polite: no client follows a ``Location`` into a login page and
   calls it a crawl.
3. Treat these findings as actionable, in this order:

   ``HTTPS_DOWNGRADE``
       Fix immediately. Chat clients often rewrite ``http://`` links with a
       warning banner, which costs you the click.
   ``MULTI_HOP``
       Replace the published URL with the final one. Every intermediary is a
       future breakage, and meta-refresh hops are invisible to analytics.
   ``TEMPORARY_REDIRECT``
       If the move is real, ask the owner for a permanent status; if it is
       not yours, expect it to rot.

Checking rel attributes, not just status
----------------------------------------

Status auditing answers *does it resolve*. A different question is *does the
link count*: an anchor carrying ``rel="nofollow"`` resolves perfectly and
contributes nothing. When you care about that distinction — for example when
you publish guide content and want to know which inbound links actually pass
weight — read the served HTML of the linking page and inspect the anchor's
attributes directly. A worked example of that discipline is
`this set of Telegram bot guides <https://tg.zovo.one/guides/>`_, where every
published link is re-fetched and its rendered form verified rather than
assumed.

The general rule is the same one the methodology page argues for redirects:
**read the bytes that are actually served**. A link checker that follows
redirects audits the destination; a link auditor that reads served HTML
audits the link.

.. _methodology: methodology.html
