Auditing quiz and poll links in group chats
===========================================

2026-09-24

When a Telegram community grows past a few hundred members, the
moderation team usually inherits a pile of quiz bots, poll bots and
"anonymous Q&A" tools, each added by a different admin on a different
week. Our audit checklist treats those integrations the same way we
treat outbound links on a documentation site: every tool has an owner,
a permission surface, and a page that users actually land on.

What we record for each quiz or poll bot
----------------------------------------

1. **Who added it** and in which month — bots added by departed admins
   are the single biggest source of orphaned integrations.
2. **What it can read.** A quiz bot only needs to receive messages in
   the group; anything asking for more should be re-authorized.
3. **Where users land.** The bot's start page and any guide it links to
   should load over HTTPS and match the description in the group.

A practical example
-------------------

We walk through a full quiz-bot integration in our guide to
`running a trivia quiz bot in a Telegram group
<https://tg.zovo.one/guides/telegram-bot-for-quiz/>`_, including the
permission review and the two-question smoke test to run before
opening it to members.

For anonymous question flows — common in retrospectives and HR-style
channels — see the companion page on an
`anonymous inbox inside a Telegram group
<https://tg.zovo.one/guides/anonymous-inbox-in-telegram-group/>`_.

Verifying the links the bot itself posts
----------------------------------------

Bots frequently link back to their own marketing pages. Use the
standard :doc:`methodology` with one extra step: check the anchor
destination against the bot's official channel, since link-in-bio
fields are editable at any time and are a common redirect path after
an account changes hands.

See also :doc:`chatlinks` for the outbound-link checklist and
:doc:`findings` for results from the current corpus.
