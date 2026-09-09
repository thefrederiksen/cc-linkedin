# Mission: cc-linkedin, every LinkedIn action through the signed-in browser

Status: ACTIVE. Phase 2 in build (2026-09-09). Phases 0 and 1 are on main.
Conduct: `cc-devthrottle workflow instructions mission`. This file describes the
WORK. It grants nothing.

## Why

Soren drives LinkedIn from the command line - posting the CenterConsulting video
series, commenting, and soon reading people and reaching them. Today the toolkit
can post and comment. Everything else is still a person clicking, or an agent
improvising browser automation for one job and throwing it away.

The bar, in his words: **"It has to work every single time."** A verb is done
when its selftest passes three times in a row on the live page and leaves
nothing behind. Not when the code looks right, and not when a run happened to
work once.

Two things are settled and are not up for revisiting:

* **No LinkedIn API. Ever.** The browser is the tool. Cookie-copying clients
  (`linkedin-api`, Voyager) are the classic way to get an account restricted.
* **Research before building.** Every mechanic in this repo was taken from a
  tool that already does it and then measured on the live page. Each new verb
  gets the same: read what exists, survey the real DOM, then code.

When this is finished, one command line does anything Soren does on LinkedIn by
hand, refuses to act on the wrong target, paces itself like a person, and proves
what it did before it says it did it.

## Design rulings

Rulings marked (inferred) were not stated by the owner; they are the Architect's
call and can be overturned by him.

### Answered by the owner, 2026-09-09

1. **Reactions and comments on other people's posts fire automatically**, held
   to the 45-90 second gap and the daily caps. They are not staged. The
   permalink-plus-expect guard is what stops the wrong-post failure.
2. **Profile reads leave the ordinary "viewed your profile" trace, and are
   capped.** High-volume profile viewing is one of the top triggers for an
   account warning, so reads get their own daily cap and their own gap. A run
   that hits the cap stops and says so.
3. **Phase 3's one real connection request and one real message go to a person
   the owner names.** He will name them; the Architect asks for the name when
   Phase 2 lands. Until there is a name, Phase 3's real-send tests do not run.

### The Architect's, for Phase 2

4. **A read that comes back empty is a FAILURE, never a result.** (inferred)
   Every read verb asserts it is signed in and asserts its required field is
   non-empty before it prints RESULT. A signed-out page, a login wall or a
   changed layout must produce `FAIL` with the reason, not an empty JSON record
   and a zero exit. This is the rule the rest of Phase 2 hangs on: the natural
   shape of a read verb is a check whose pass condition is an absence, and that
   certifies runs that never happened.
5. **Reads are paced on their own clock.** (inferred) `Pace` gains a second
   track for views: its own last-view timestamp, a short 3-8 second gap, and a
   daily cap of 80. Reads never touch `last_outbound` - a profile read must not
   make the next comment wait 90 seconds, and a page of search results must not
   take an hour. One view is counted per profile or company page actually
   opened; a search results page counts one.
6. **Surveys are committed.** (inferred) The survey script that measured a
   surface, and the dump it produced, are part of the record and land with the
   code. The next reader needs to know what the DOM looked like on the day the
   selectors were written.
7. **Selectors carry the date they were measured**, in `kit/selectors.py`, as
   Phase 1's do. A LinkedIn change is then a one-file fix.
8. **The selftest requires its fixtures. A missing fixture fails the run.**
   (inferred) No verb is silently skipped: a skip that counts as a pass is how a
   suite goes green over code that never ran. The CLI carries the known fixtures
   as defaults so the command line stays short.

## The work

**Phase 2 - reading people, companies, search, notifications, page stats.**
`read-profile`, `read-company`, `search-people`, `search-posts`,
`notifications`, `stats`. Read-only, JSON out. Details and the per-verb proof
table are in `docs/PLAN.md`; the build order and the acceptance rows are in
`docs/phase-2-design.md`.

**Phase 3 - reaching people.** `connect`, `withdraw`, `message`, `read-inbox`,
`read-thread`, `invitations`, `follow`/`unfollow`, `invite-to-follow`. Staged by
default; `--submit` sends.

**Phase 4 - more of posting.** `post --profile`, `edit-post`, `repost`.

Each phase: survey the real DOM, build against the survey, extend the selftest,
three clean consecutive runs on the live page, an independent Codex inspection,
then one pull request to main.

## Out of scope

* The LinkedIn API, and anything that talks to LinkedIn outside the browser.
* Bulk outreach, scraped lists, and anything that treats a cap as a target.
* Jobs, learning, recruiter, sales navigator, events, groups, newsletters.
* Rewriting Phase 0's posting code. It works and it has traffic on it.
* A daemon, a queue, or a scheduler. `cc-linkedin` is a command that runs and
  exits; scheduling lives in whoever calls it.

## Testbed

* Comments and reactions: Soren's own post
  `https://www.linkedin.com/feed/update/urn:li:activity:7501672190191296512/`.
* Page posts: CenterConsulting, Inc., page `107519091`.
* Profile and search reads: `https://www.linkedin.com/in/sorenfrederiksen`,
  the CenterConsulting page, the queries "Soren Frederiksen" and "mindzie".
* Read-only post fixture: mv-001, `urn:li:activity:7503499656291622912`.
