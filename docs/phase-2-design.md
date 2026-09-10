# Phase 2 design: reading people, companies, search, notifications, page stats

The Architect's settled design. The Manager builds THIS. Where it is silent, the
Manager decides and writes down what it decided and why. Where it is wrong,
because the live page says otherwise, the Manager says so and the Architect
rules again - it does not quietly build something else.

Verbs: `read-profile`, `read-company`, `search-people`, `search-posts`,
`notifications`, `stats`. All read-only. All JSON out. None of them writes
anything to LinkedIn.

## 0. The rule the whole phase hangs on

**A read that comes back empty is a FAILURE, never a result.**

The natural shape of a read verb is a check whose pass condition is an absence:
"no error, so print what we found." Handed a login wall, a changed layout or a
throttled page, that shape prints an empty record and exits 0, and every caller
downstream believes it. So:

* Every verb names its REQUIRED fields (below). A required field that is empty,
  or a number that will not parse as a number, is `FAIL <reason>` and exit 1.
* Every verb asserts it is on the right entity: the profile slug, the company
  slug, or the page id it was asked for must be what came back.
* Zero rows from `search-people`, `search-posts` or `notifications` is a FAIL,
  not an empty list. A genuinely empty result set is indistinguishable from a
  broken selector, and the broken selector is far more likely.
* `assert_signed_in()` runs on every navigation, and it is a PRESENCE check -
  the global navigation's own identity control must be there. Do not test for
  the absence of the words "Sign in": a profile page can contain them, and an
  authwall can be served without them.

## 1. Survey before code

Nothing in this phase is written against a guessed selector. Build
`tools/survey.py` first - read-only, driven through `kit/browser.Browser` so it
takes the lock like everything else - which for a given URL dumps:

* the final URL after any redirect (an authwall shows up here first);
* every role and accessible-name pair from the accessibility tree, filtered to
  what a person could act on or read;
* for each candidate container: tag, class list, `data-*` attributes, and the
  first 120 characters of text;
* which rendering was served, by the same test Phase 1 uses (`[data-urn]`
  present = the classic app), because a profile or a search page may well come
  in two flavours too - Phase 1 learned that the hard way on the permalink.

Run it on: Soren's profile, a second person's profile, the CenterConsulting
company page, a people search, a content search, the notifications page, and the
Page analytics page. Save each dump under `docs/surveys/<surface>-2026-09-09.txt`
and commit them. **The surveys are part of the record and they land with the
code** - the next reader has to be able to see what the DOM looked like on the
day the selectors were written.

Run each survey TWICE, minutes apart. If the two dumps disagree, LinkedIn is
serving that surface in more than one rendering and both belong in
`kit/selectors.py`.

## 2. Code shape

Three new modules, one per surface, in the shape `kit/comments.py` already sets:
a module docstring holding what was MEASURED and when, selectors imported from
`kit/selectors.py`, verbs that take the argparse namespace.

* `kit/people.py` - `read-profile`, `read-company`. The entity read surface.
* `kit/search.py` - `search-people`, `search-posts`. The search surface.
* `kit/account.py` - `notifications`, `stats`. The signed-in account's own
  surfaces: what happened to me, and how my Page is doing.

New selectors go in `kit/selectors.py` with the date they were measured, grouped
by surface, exactly as Phase 1's are.

`cc_linkedin.py` gains the six subcommands. It stays the entry point; every
existing command line keeps working.

## 3. Pacing: reads get their own clock

`Pace` today has one track - `last_outbound` plus per-kind daily caps - and its
gap is 45 to 90 seconds. Reads must not use it: a profile read would make the
next comment wait a minute and a half, and a search of twenty-five people would
take an hour.

Add a second track:

* `Pace.before_view()` and `Pace.after_view()`, keyed on `last_view`, gap 3 to 8
  seconds, daily cap **80** views.
* Views never touch `last_outbound`, and outbound actions never touch
  `last_view`.
* One view is counted per profile or company page opened. A search results page
  counts one view no matter how many cards it reads - the cards are read from
  the results page and no profile is opened.
* Over the cap is `FAIL`, with the count and "tomorrow", the way the outbound
  cap already reads.

The gap is drawn from the range, not fixed. The existing gap draw uses
`hash(str(time.time()))`, which is not random in any useful sense; use
`random.uniform`, and fix the outbound one at the same time - a fixed-looking
rhythm is exactly what pattern detection is for.

## 4. The verbs

Every record is one line of JSON on stdout, then a single
`RESULT <verb> ...` line. `FAIL <reason>` and exit 1 otherwise.

### `read-profile <url> [--expect PHRASE]`

Mechanism: open the `/in/` URL, expand the About section if it is collapsed,
read the top card and the current position.

Record: `kind=profile`, `url`, `slug`, `name`, `headline`, `location`, `about`,
`current` (`title`, `company`, `company_url`), `degree`, `connection_state`,
`followers`, `connections`, `rendering`.

* REQUIRED non-empty: `name`, `headline`. REQUIRED to match: `slug` equals the
  slug asked for.
* `degree` is one of `self`, `1st`, `2nd`, `3rd`, `3rd+`, or null with a reason
  recorded - never silently absent.
* `connection_state` is what the primary button actually says (`Connect`,
  `Pending`, `Message`, `Follow`). On Soren's OWN profile there is no such
  button, so `degree` is `self` and `connection_state` is null - **and that is
  why this verb cannot be proven on his profile alone.** See the acceptance
  rows.
* `--expect` checks the phrase against name and headline; a miss refuses.
* Costs one view.

### `read-company <url>`

Record: `kind=company`, `url`, `slug`, `name`, `tagline`, `industry`,
`followers`, `size`, `website`, `location`, `about`, `rendering`.

* REQUIRED non-empty: `name`. REQUIRED to match: `slug` or numeric page id.
* `followers` parses to an integer. "1,234" and "1.2K" both become an integer
  and the raw string is kept as `followers_raw`. A value that will not parse is
  a FAIL - not a null, and not the raw string smuggled into a number field.
* Costs one view.

### `search-people <query> [--company] [--title] [--location] [--limit N]`

Mechanism: the people search results page. Read the cards; do not open the
profiles.

Record per result: `kind=person_result`, `rank`, `name`, `url`, `headline`,
`location`, `degree`.

* REQUIRED: at least one row; every row has a non-empty `name` and a `url`
  containing `/in/`.
* `--limit` defaults to 25, hard cap 100 per run. Paging past the first page
  costs one further view per page.
* Costs one view for the results page.

### `search-posts <query> [--limit N]`

Record per result: `kind=post_result`, `rank`, `author`, `url`, `text`, `when`.

* REQUIRED: at least one row; every `url` resolves to a permalink containing
  `urn:li:activity` (so the result feeds straight into Phase 1's verbs).
* Same limit and view accounting as `search-people`.

### `notifications [--limit N]`

Record per row: `kind=notification`, `rank`, `text`, `actor`, `url`, `when`,
`unread`.

* REQUIRED: at least one row, each with non-empty `text`.
* Read-only, and it costs no view - it is our own notifications page.
* **Public repo:** this output names third parties. It goes to stdout for the
  caller; it is never pasted into a committed file. See section 6.

### `stats --page ID`

Mechanism: the Page's own analytics, 30-day window, as a Page admin.

Record: `kind=page_stats`, `page`, `name`, `window_days`, `followers`,
`impressions`, `engagements`, `reactions`, `comments`, `reposts`, plus a
`_raw` string for every number.

* REQUIRED: `followers` and `impressions` are integers. A number that will not
  parse is a FAIL.
* REQUIRED to match: the page name on screen equals `--page-name` if given.
* If the analytics view is not reachable as this identity, that is a FAIL
  naming the identity - not zeroes.
* Costs no view.

## 5. The selftest and the acceptance rows

Extend `cc-linkedin selftest` with the Phase 2 block. Fixtures are arguments
with defaults where the value is Soren's own; the run FAILS on a missing fixture
rather than skipping the verb.

New arguments: `--profile` (default Soren's), `--other-profile` (no default -
see below), `--company` (default the CenterConsulting page),
`--query-people` (default "Soren Frederiksen"), `--query-posts` (default
"mindzie").

| # | Verb | Asserted |
|---|---|---|
| P2-1 | `read-profile` on Soren's profile | `name` contains "Soren Frederiksen"; `slug` is `sorenfrederiksen`; `headline` non-empty; `degree` is `self` |
| P2-2 | `read-profile` on a second person's profile | `name` non-empty; `degree` in the allowed set and NOT `self`; `connection_state` in {Connect, Pending, Message, Follow}; `slug` matches what was asked |
| P2-3 | `read-profile` with a deliberately wrong `--expect` | refuses: FAIL, exit 1, nothing printed as a record |
| P2-4 | `read-company` on CenterConsulting | `name` is "CenterConsulting, Inc."; `followers` is an integer of at least 1 |
| P2-5 | `search-people "Soren Frederiksen"` | first row's `url` is Soren's profile URL |
| P2-6 | `search-posts "mindzie"` | at least 3 rows; every `url` contains `urn:li:activity` |
| P2-7 | `notifications` | at least 1 row, every row with non-empty `text` |
| P2-8 | `stats` on the CenterConsulting page | `followers` and `impressions` are integers; page name matches |
| P2-9 | the whole run | lock file released, no stray tab, no native dialog, `pace.json` view count rose by exactly the number of views the run took |

**P2-2 needs a second person and the repo is PUBLIC.** So `--other-profile` has
no default and is never committed - not in the code, not in the docs, not in an
evidence file. The Manager runs it with a 1st- or 2nd-degree profile chosen at
run time and records it in the evidence as "profile B (passed at run time)".
Without `--other-profile` the Phase 2 selftest FAILS and says why - it does not
skip P2-2. P2-2 is the only row that proves the verb works on anyone other than
its owner, and Soren's own profile has no Connect button, no degree badge and no
"Message" button, so without it half the record is never exercised.

**Done means:** every row above passes on three consecutive live runs, and the
Page and the profile are exactly as they were before.

## 6. Traps, measured or structural

1. **`cc-linkedin` on PATH is the SHARED checkout**
   (`C:\Users\soren\AppData\Local\cc-director\bin\cc-linkedin.cmd` runs
   `D:\ReposFred\cc-linkedin\cc_linkedin.py`), which is `main`, which is NOT the
   mission code. Testing through the PATH command proves nothing about the
   branch. Run the worktree's own `cc-linkedin.cmd` by absolute path, or
   `py -3.11 <worktree>\cc_linkedin.py`. Every proof in the report must say
   which binary produced it.
2. **One Playwright client per Chrome.** The lock in `kit/browser.py` serialises
   runs. The video-pipeline session schedules posts through the same Chrome and
   the same lock; a wait of a few minutes is the lock working, not a hang. Never
   bypass it, and never run two verbs concurrently.
3. **The cencon Chrome wedges.** A run caught by a restart ends with "no Chrome
   on port 9224" and nothing half-done. Call `bh-profiles.ps1 up cencon` ONCE,
   not in a loop.
4. **Two renderings of the same URL, served at random.** Proven on the post
   permalink; assume it until measured otherwise on every new surface.
5. **The native "Open" dialog.** Any click that falls through can open one, and
   CDP cannot close it. Phase 2 clicks almost nothing, but the watchdog stays on
   and a spawned dialog still fails the run.
6. **Public repo.** No third party's name, profile URL, headline or message text
   goes into a committed file. Committed evidence carries counts, shapes and
   pass or fail, and refers to people as "profile B". Soren's own profile, his
   own post and the CenterConsulting page are his and are already in the docs.

## 7. Out of scope for Phase 2

Anything that writes. Anything on a `/jobs/`, `/learning/`, recruiter or sales
navigator surface. Paging a search past 100 results. Caching reads to disk.
