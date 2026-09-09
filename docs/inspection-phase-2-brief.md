# Phase 2 inspection brief

Written by the Architect for an INDEPENDENT inspector of a different agent
family from the one that built this. The builder has finished and left.

## Your mandate

Inspect `git diff origin/main..phase-2-reading` in the worktree
`D:/ReposFred/cc-linkedin.mission`. Six new read verbs for LinkedIn, driven
through a signed-in browser: `read-profile`, `read-company`, `search-people`,
`search-posts`, `notifications`, `stats`.

**You do not fix anything.** Not a typo, not a one-line bug. An inspector who
picks up a hammer stops being an inspector: you were not there when this was
built and that independence is the entire value of the seat. Findings go back to
a builder. Do not commit, do not stage, do not edit a tracked file.

**Do not trust `docs/phase-2-report.md`.** It is self-testimony: written by the
session that did the work, about its own work, and exactly as persuasive as it
is unreliable. Read it to learn what is CLAIMED, then go and check the claims
against the code. Where it says a guard was watched failing, find the guard and
decide for yourself whether it can fire. A report that anticipates your
objections is not the same as code that survives them.

Treat the same scepticism as due to `docs/phase-2-design.md` and
`docs/rulings-phase-2.md` - they are the Architect's, and the Architect is not
neutral about this mission either.

## The bar this code is held to

The owner's, in his words: **it has to work every single time.** A verb that is
right most of the time is not partly done, it is wrong. He drives his company's
LinkedIn presence with this tool.

Two design rules matter more than anything else here, so weigh every finding
against them:

1. **A read that comes back empty is a FAILURE, never a result.** The natural
   shape of a read verb is "no error, so print what I found", which on a login
   wall or a changed layout prints an empty record and exits 0 - and every
   caller downstream believes it. Every assertion in this code is supposed to be
   a check for something PRESENT.
2. **Nothing may be claimed that was not measured.** The most dangerous defect
   available in this diff is not a crash. It is a plausible, precise, WRONG
   answer that nothing downstream can catch.

## The sharp questions

Go where the consequences are, not where the code is easiest to read.

1. **The urn rebuild in `search-posts --resolve` is the highest-consequence path
   in this diff.** A short `lnkd.in` link is followed in the browser and it
   lands on a readable post URL of the shape
   `/posts/<slug>_<words>-<kind>-<id>-<hash>`, from which an
   `urn:li:activity:<id>` is REBUILT by string surgery. That permalink is then
   handed to Phase 1's verbs, which comment on, react to and delete posts. Can
   this produce a well-formed urn that points at the WRONG POST - a numeric run
   in the slug, a hash that is all digits, a repost, a document or newsletter
   URL, a redirect to a login page or an interstitial? A wrong-but-plausible urn
   here means commenting on a stranger's post. What does the code do to prove
   the urn it rebuilt is the post it actually landed on, and is that proof, or
   is it a regular expression agreeing with itself?
2. **Where can a constant be substituted and the suite stay green?** Read
   `kit/selftest.py` against the nine acceptance rows in `phase-2-design.md`
   sections 5. Does each row assert what it says it asserts, on the value the
   verb actually returned - or on something the test computed itself, or on a
   literal that would still match if the verb returned nothing? P2-9 claims
   "views rose by 7 (expected 7)": find out where the 7 comes from. If it is
   hardcoded, the row proves nothing about the view clock.
3. **Is `assert_signed_in()` really on every navigation?** Including inside
   search paging, inside `--resolve`'s follow of each short link, and inside the
   stats time-range drive. One unguarded navigation is where the empty read gets
   back in.
4. **The member-analytics trap.** `stats` must read every number from inside the
   "Content engagement" table. Is the locator genuinely SCOPED to that table, or
   does it find the header and then query the whole page? Can the header check
   pass while a number still comes from `.member-analytics-addon-summary__list-item`
   (the widget holding the OWNER'S personal numbers, in the right shape, on the
   Page's own admin screen)? Construct the case if you can.
5. **Number parsing.** `to_int` handles "1,234" and "1.2K". It has only ever
   parsed "3" on a real page. Check "1.2K", "1.2M", "1,234", "12.5K", a
   non-breaking space, a European decimal comma, and whatever a Page with
   1,000,000 followers actually renders. A silently wrong follower count is
   exactly defect class 2 above.
6. **The view clock in `kit/browser.py`.** Is `before_view` called BEFORE the
   navigation or after? If after, the daily cap can be exceeded by one on every
   run. Do views ever touch `last_outbound`, or outbound actions `last_view`?
   Does the day rollover work across midnight, and does the file survive two
   processes writing it (the video-pipeline session shares this machine)? Note
   the pre-existing gap draw used `hash(str(time.time()))`; check what replaced
   it is actually random and that the outbound path was fixed too.
7. **Zero rows.** `search-people`, `search-posts` and `notifications` must fail
   on zero rows. Verify by reading, not by trusting the table: is the check on
   the parsed rows, or on something upstream that could be non-empty while the
   parsed list is empty?
8. **The lock.** Is it released on EVERY exit path - an exception inside the
   `with`, a `die()` mid-verb, a crashed renderer, a KeyboardInterrupt? A lock
   left held wedges every other session on this machine, including the one
   posting the owner's video series each morning.
9. **Read-only in fact, not just in intent.** Does anything in these six verbs
   click something that could write, follow, connect, or mark a notification
   read? Opening a card's control menu to reach "Copy link to post" is an
   interaction: what else is under that click, and can it fall through? (Phase 1
   learned that a Discard button sits exactly over a Photo button, and a late
   click opens a native OS file dialog that CDP cannot close.)
10. **This repository is PUBLIC.** The committed surveys under `docs/surveys/`
    were redacted by a script that initially covered element text but not
    attributes, so `href` and `aria-label` leaked ten third-party profile URLs.
    The report says all eight dumps were retaken. Verify it: grep the committed
    dumps and every committed file for third-party names, `/in/` slugs, company
    URLs and message text. This is a checkable claim and it is the one with
    consequences outside this machine.
11. **What does the diff claim that the code does not support?** Every "MEASURED"
    line in a docstring is an assertion about the live page made by someone with
    an interest in being done. Which of them could not have been measured the
    way the comment implies?

## What is already admitted, so do not spend your time re-finding it

`docs/phase-2-report.md` has a "What is NOT proven" section listing seven gaps:
stats proven on one Page with one post and no pagination; `search-posts` reading
only first-pass cards so `--limit` is a ceiling not a promise; `--days 0` and
the Custom calendar unexercised; one profile B only, so most `degree` and
`connection_state` values unseen on a top card; the `K`/`M`/`B` parser
unexercised on a real page; nothing run against a signed-out or throttled
browser; and one-day-old selectors on hashed-class renderings.

Confirming these exist is not a finding. **Finding that one of them is worse
than admitted, or that an eighth is missing, is.**

## How to report

Write your review to `docs/inspection-phase-2.md` in the worktree - do not
commit it, just write the file. Then reply to the Architect with ONE LINE:
fleet messages truncate at the first newline, so a multi-line reply arrives as
its first heading and nothing else.

For each finding give: the file and line, what is wrong, the concrete case that
breaks it (inputs and state, then the wrong output), how bad it is, and how
confident you are. Rank by consequence. Separate what you PROVED from what you
suspect - a suspicion labelled as a suspicion is useful, a suspicion dressed as
a proof costs the next reader their scepticism.

If you find nothing in a section, say so plainly. "I could not break this and
here is what I tried" is a real result and is more useful than a padded list.
