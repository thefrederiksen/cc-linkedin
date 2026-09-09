# Phase 2 report

The Manager's, written through the build and finished 2026-09-09 evening.
Branch `phase-2-reading` in the worktree `D:/ReposFred/cc-linkedin.mission`.

**Every command in this report was run as
`py -3.11 D:/ReposFred/cc-linkedin.mission/cc_linkedin.py`.** Never the
`cc-linkedin` on PATH: that runs the shared checkout, which is `main`, and a
proof produced by it would say nothing about this branch.

Status: **built, pushed, three consecutive clean runs.** Ready for the
Architect to call the Codex inspection.

---

## What it does for the owner

Six new read verbs, all JSON, all read-only, none of which writes anything to
LinkedIn:

| Verb | What it gives back |
|---|---|
| `read-profile` | name, headline, location, about, current company, degree, connection state, connections, followers |
| `read-company` | name, tagline, industry, followers as an integer, size, website, location, about |
| `search-people` | a ranked list: name, profile URL, headline, location, degree |
| `search-posts` | a ranked list: author, text, age, a share link, and - on request - the real permalink |
| `notifications` | text, who did it, where it points, how long ago, read or unread |
| `stats` | the Page's followers, its window, one row per post, and the sum of those rows |

`README.md` and `.claude/skills/linkedin/SKILL.md` both carry the new block, so
the next agent finds them without reading this.

## The three clean runs

One command, both blocks - Phase 1 writes and cleans up after itself, Phase 2
reads. There is deliberately no flag that runs half of it.

```
py -3.11 cc_linkedin.py selftest \
  --post https://www.linkedin.com/feed/update/urn:li:activity:7501672190191296512/ \
  --page 107519091 --page-name "CenterConsulting, Inc." \
  --other-profile <profile B, passed at run time, never committed>
```

| Run | Started | Result |
|---|---|---|
| 1 | 2026-09-09 17:43 | `RESULT selftest passed=23 failed=0` |
| 2 | 2026-09-09 17:52 | `RESULT selftest passed=23 failed=0` |
| 3 | 2026-09-09 18:00 | `RESULT selftest passed=23 failed=0` |

Every one of the nine acceptance rows passed in all three, and every Phase 1
verb passed in all three as well. Afterwards, checked directly on the live page:
no leftover selftest post on the Page, no native dialog, the browser lock
released.

The single line reading `FAIL` in each run's output is row P2-3, where a
deliberately wrong `--expect` is SUPPOSED to make the verb refuse.

Rows, as they printed on run 3:

```
P2-1  own profile: name='Soren Frederiksen' slug='sorenfrederiksen' headline present degree='self'
P2-2  profile B: slug matched=True degree='1st' state='Message' name present=True
P2-3  wrong --expect refused: exited non-zero=True, records printed=0
P2-4  company: name='CenterConsulting, Inc.' followers=3
P2-5  first row url='https://www.linkedin.com/in/sorenfrederiksen/'
P2-6a rows=5, every row has an author and a lnkd.in share_url
P2-6b resolved 3 of 3 rows to a post urn
P2-6c a resolved permalink fed to read-post returned author='mindzie, inc. - ...'
P2-7  rows=10, every row has text
P2-8  followers=3 name matched=True window=30d (2026-08-11..2026-09-09) posts with integer impressions
P2-9  views rose by 7 (expected 7), lock released=True, native dialogs=0
```

**Profile B** was a 1st-degree connection chosen at run time and is not named
here, in the code, in the surveys or anywhere else in this public repository. It
produced `degree='1st'` and `connection_state='Message'` - neither of which
Soren's own profile can produce, which is the whole reason that row exists.

## Every guard was watched failing

A guard that has never been seen to fire is decoration. Each of these was broken
on purpose, run, and restored; the tree was confirmed clean afterwards.

| Guard | How it was broken | What it said |
|---|---|---|
| The Content engagement header check - the member-analytics trap | added a column that is not on the page to `REQUIRED_COLUMNS` | `FAIL the Content engagement table is not the table this was written against: it is missing the columns Sponsored spend. Its header reads Post title, Post type, ...` |
| `assert_signed_in` | pointed `ME_BUTTON` at a control that does not exist | `FAIL not signed in on the company page centerconsulting-inc: the global navigation has no identity control. ... this is NOT an empty result.` |
| The stats window check | mapped the 30-day preset to the 7-day one | `FAIL the time range reads 'Time range: Sep 3, 2026 - Sep 9, 2026' after choosing 'Last 7 days', which is 7 days, not 30.` |
| The two-degree-badges check | fed it a card carrying a visible "1st" and a visible "2nd" | `FAIL the top card shows two different visible degree badges (1st, 2nd) ... refusing to guess which one is the truth` |
| Zero rows is a failure | searched people for a string nobody is called | `FAIL no people found for 'zzqqxx not a real person zzqqxx'. Zero rows is a broken selector far more often than an empty result set ...` (exit 1) |
| The missing fixture | ran the selftest without `--other-profile` | `FAIL --other-profile is required. Row P2-2 is the only row that proves read-profile works on somebody other than its owner ...` (exit 1) |

## The best thing the survey found

**The Page's own analytics screen carries the MEMBER's numbers, in the obvious
place, in the right shape.**

`/company/107519091/admin/analytics/updates/` has exactly one four-number
headline card. It is titled "Your profile view highlights". Its selector,
`.member-analytics-addon-summary__list-item`, has four hits and the four labels
Impressions, Reactions, Comments, Reposts - which is precisely what a `stats`
verb is looking for. On 2026-09-09 it read **5 impressions**, while the Page's
own Content engagement table read **48** for the single post in the same window.

Reading it would have produced a plausible, precise, wrong answer on every run
forever, and nothing downstream could have caught it: the numbers are the right
shape, they move over time, and they are somebody's real data. So `stats` reads
every number from inside the Content engagement table, asserts that table's
header labels BEFORE touching a cell, and `kit/selectors.py` carries the
selector as a dated negative note naming both numbers, so nobody reaches for the
obvious thing again.

## Where the live page contradicted the design

Both went to the Architect mid-build rather than being built around, and both
were ruled on in `docs/rulings-phase-2.md`.

1. **`search-posts` cannot read a permalink off a content-search card.** Not
   present in the DOM on four consecutive loads; the card's own "Copy link to
   post" yields a `lnkd.in` shortener; and the six activity urns embedded in the
   document cannot be paired to the six cards by anything except order, which
   would be an assumption dressed as a proof. The record now carries `share_url`
   and `permalink` as separate fields with no `url` at all, and `--resolve`
   follows the short link in the browser. **Measured while implementing it:** a
   short link does not land on `/feed/update/` either - it lands on the readable
   post page, `/posts/<slug>_<words>-<kind>-<id>-<hash>`, so the urn is rebuilt
   from that path.
2. **The Page publishes no page-level aggregate.** `stats` reports what the
   Page states - followers, the window, one row per post - plus `sum_of_posts`,
   named so that nobody reads it as LinkedIn's own total, since a Page's real
   impressions include arrivals the table never lists.

Three further design assumptions were disproved and decided by the Manager, and
the Architect blessed all three as measured:

* the P2-5 fixture: `search-people "Soren Frederiksen"` returns ten other people
  of that name and not the owner at all, so the fixture is now
  `"Soren Frederiksen mindzie"`, whose first and only row is his profile. Both
  dumps are committed, the failing one included;
* `read-company` goes to `/company/<slug>/about/?viewAsMember=true`, because a
  Page admin asking for his own page is redirected to the admin dashboard, and
  asserts the final URL still carries it;
* `read-profile` takes the VISIBLE degree badge and fails when two visible ones
  disagree.

## What is NOT proven

Named honestly, because an unproven claim that reads as proven is worse than no
claim.

1. **`stats` is proven on ONE Page with ONE post and three followers.** The
   number parsing (`1,234`, `1.2K`) is exercised by unit-sized values only; a
   Page with thousands of impressions and a paginated Content engagement table
   has never been read. The table is read as it stands on the page - if it
   paginates, later pages are not fetched and `sum_of_posts` would silently
   cover only the first page. That is the most likely place for this verb to be
   wrong at scale.
2. **`search-posts` reads only the cards LinkedIn renders on the first pass** -
   six of them, measured. `--limit` above that does not scroll to fetch more, so
   a `--limit 25` today returns what is there, not 25. The limit is a ceiling,
   never a promise.
3. **`--days 7` and `--days 15` were exercised, `--days 0` was not**, and no
   window other than a preset has been driven. The Custom calendar is untouched.
4. **Only ONE profile B was ever used.** `degree` has been seen as `self` and
   `1st`; `2nd`, `3rd` and `3rd+` have been seen on search rows but never on a
   profile top card, and `connection_state` has been seen as `Message` only -
   `Connect`, `Pending` and `Follow` are in the allowed set on the strength of
   the survey, not of a run.
5. **The company `followers` parser has only ever parsed "3 followers".** The
   `K`/`M`/`B` path in `to_int` is written and unexercised on a real page.
6. **Nothing here has been run against a signed-out or throttled browser.** The
   signed-in check was proven by breaking the selector, which proves the check
   fires - it does not prove LinkedIn's authwall looks the way the check
   assumes.
7. **The surveys are one day old.** Every selector carries 2026-09-09. The
   profile and both search surfaces are the new server-driven rendering, whose
   class names are hashed and change without notice; the element IDs the code
   leans on are more stable than classes but are not a contract.

## What I got wrong along the way

* The first survey pass leaked ten third-party profile URLs into the dumps meant
  for committing. The redactor covered element TEXT and not attributes, so
  `href` and `aria-label` went through whole. Caught before anything was
  committed; the redactor now covers attributes and header lines, and all eight
  dumps were retaken.
* The first full selftest scored 32 passed / 1 failed, and the one failure was
  row P2-3 behaving correctly - the refusal was counted once as a failed step
  and once as a passed check.
* The stats time-range dropdown was located by "the first element carrying the
  open class", which matched an empty container on one run and the right one on
  the next. Found by running it twice rather than by reading it.
* That same code waited for the range text to CHANGE, which would have failed on
  a page already showing the right window - correct state reported as a failure.
  It now waits for the page to state the window that was asked for.

## Files

* `tools/survey.py` and the eight dumps under `docs/surveys/` - the measurement
  the selectors were written from, redacted for a public repository.
* `kit/people.py`, `kit/search.py`, `kit/account.py` - the six verbs.
* `kit/selectors.py` - every new selector with the date it was measured, and the
  member-analytics trap as a dated negative note.
* `kit/browser.py` - the view clock and `assert_signed_in`.
* `kit/selftest.py` - the Phase 2 block and the nine rows.
* `docs/rulings-phase-2.md` - the Architect's two mid-build rulings.
