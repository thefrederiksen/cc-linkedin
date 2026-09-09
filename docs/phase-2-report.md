# Phase 2 report

Written by the Manager, kept current through the build. The Architect reads this;
the fleet message only points at it.

Branch `phase-2-reading` in the worktree `D:/ReposFred/cc-linkedin.mission`.
Every command below was run as `py -3.11 D:/ReposFred/cc-linkedin.mission/cc_linkedin.py`
or `D:/ReposFred/cc-linkedin.mission/cc-linkedin.cmd`, never the `cc-linkedin` on
PATH, which runs the shared checkout and would prove nothing about this branch.

---

## TWO RULINGS NEEDED (2026-09-09, 17:20)

Both are places where the live page contradicts the settled design. Neither is a
matter of taste and neither can be decided inside the Manager's mandate, because
each one changes an acceptance row. Everything else in Phase 2 is unaffected and
is being built while these wait.

### Ruling 1 - `search-posts` cannot return a permalink (row P2-6)

The design requires every `search-posts` row to carry a `url` containing
`urn:li:activity`, "so the result feeds straight into Phase 1's verbs". Measured
on the live content-search page, `https://www.linkedin.com/search/results/content/?keywords=mindzie`:

* The page is served ONLY in the new server-driven React rendering. Loaded four
  times, minutes apart: `[data-urn]` 0 every time, `[data-id]` 0 every time,
  `[data-sdui-screen]` 1 every time. There is no classic rendering to fall back
  to, unlike the post permalink Phase 1 met.
* A result card carries NO permalink. Six cards on the first page, and
  `a[href*="/feed/update/"]` counts 1 - and that one belongs to a quoted post
  inside a card, not to the card itself. `a[href*="urn:li:activity"]` counts 0.
* The card's own control menu has "Copy link to post", and it is a menuitem with
  no href - it writes to the clipboard. Read back through granted clipboard
  permission, for three consecutive cards, it returns a SHORTENED link:
  `https://lnkd.in/p/gb95KeRa`, `https://lnkd.in/p/gJm39pjw`,
  `https://lnkd.in/p/gSCBypgw`. No activity id. Resolving one costs a navigation,
  so a 25-row search would cost 25 further page loads and 25 more views against
  the cap.
* The document that renders the page does embed six activity urns, one per card.
  They cannot be attached to a card with confidence: the per-card DOM tokens
  (`div#expanded<token>FeedType_FLAGSHIP_SEARCH`) either appear in the raw
  document with no urn within 4,000 characters either side, or - for the last
  three cards - do not appear in it at all, because those cards are fetched
  after load. Pairing them by ORDER would be an assumption dressed as a proof,
  which is the one thing this phase is built to refuse.

So the required field cannot be produced honestly by any cheap route. Options,
Manager's recommendation first:

1. **Keep `search-posts`, drop the urn requirement.** Return `kind=post_result`,
   `rank`, `author`, `text`, `when`, and `url` = the card's short link from
   "Copy link to post", with a new field `url_kind` = `"short"`. Add
   `--resolve` (off by default), which follows each short link and fills
   `permalink` with the real `urn:li:activity` URL, costing one view per row and
   refusing above a low limit. P2-6 becomes: at least 3 rows, every row has a
   non-empty `author` and a `url` on `lnkd.in`; and with `--resolve --limit 3`,
   every `permalink` contains `urn:li:activity`. That keeps the verb useful,
   keeps the feed-into-Phase-1 promise as an explicit opt-in, and never claims
   an id it did not measure.
2. Keep the requirement and always resolve. Honest, but a search becomes 25
   extra page loads and 25 views; at a cap of 80 views a day, two searches
   nearly exhaust the day.
3. Drop `search-posts` from Phase 2 and revisit it when the surface settles.

### Ruling 2 - the Page has no page-level aggregate to read (row P2-8)

The design's `stats` record wants `followers`, `impressions`, `engagements`,
`reactions`, `comments`, `reposts` over a 30-day window, from "the Page's own
analytics, as a Page admin". Measured on
`https://www.linkedin.com/company/107519091/admin/analytics/updates/`:

* Reachable as this identity - no redirect, no authwall. So the design's "not
  reachable is a FAIL naming the identity" case does not arise.
* The only headline four-number card on that page is titled **"Your profile view
  highlights"** and it is Soren's OWN member analytics widget: 5 impressions,
  0 reactions, 0 comments, 0 reposts, against 82.1% down. The Page's single post
  had 48 impressions in the same window. Reading
  `.member-analytics-addon-summary__list-item` - the obvious selector, four hits,
  right shape, right four labels - would silently return the member's numbers as
  the Page's. **This is the trap on this surface and it is worth writing down
  even if the ruling goes another way.**
* What the Page actually publishes there is a real `<table>` - "Content
  engagement", headed Post title, Post type, Audience, Impressions, Views,
  Clicks, CTR, Reactions, Comments, Reposts, Follows, Engagement rate - one row
  per post, under a stated "Time range: Aug 26, 2026 - Sep 9, 2026". The default
  window is 15 days, not 30; a different window means driving the time-range
  control.
* `followers` is available and unambiguous: the admin header reads
  "CenterConsulting, Inc. ... 3 followers" on every analytics tab, and the
  Followers tab states "3 Total followers".

Options, Manager's recommendation first:

1. **Return what the Page states, and say where each number came from.** Record:
   `kind=page_stats`, `page`, `name`, `window_start`, `window_end`,
   `window_days` (derived from the stated range, not assumed), `followers`,
   `posts` (the table's rows, each with its own impressions, reactions,
   comments, reposts and the raw strings), and `totals` computed by summing
   those rows, each total carrying `source="content-engagement-table-sum"`.
   P2-8 becomes: `followers` is an integer of at least 1, the page name matches,
   the window is a real date range, and every row's `impressions` parses as an
   integer. Nothing is invented and nothing is passed off as LinkedIn's own
   aggregate.
2. Narrow the verb to `followers` plus the per-post rows, and no totals at all.
3. Drive the time-range control to 30 days first, then do option 1. One extra
   click on an admin page; the Manager can build it either way.

---

## What is settled and already measured (no ruling needed)

These were design assumptions the live page disproved, but the fix is a fixture
or a URL, not a change to what a verb promises. Recorded here so the Inspector
can check them rather than take them on trust.

1. **P2-5's search fixture does not work as written.** The design asserts that
   `search-people "Soren Frederiksen"` returns Soren's own profile first.
   Measured: the first ten results are ten other people of that name - the first
   is a realtor in Winnipeg - and Soren's own profile does not appear on page
   one at all. The query **"Soren Frederiksen mindzie"** returns his profile as
   the first and only result, so that is the fixture. Both dumps are committed
   (`search-people-2026-09-09.txt` shows the failure,
   `search-people-self-2026-09-09.txt` shows the fixture that works).
2. **A Page admin cannot open his own Page as a member without saying so.**
   `/company/107519091/` and `/company/centerconsulting-inc/about/` both redirect
   to `/admin/dashboard/`. `read-company` therefore navigates to
   `/company/<slug>/about/?viewAsMember=true`, which measured no redirect and
   serves the ordinary member page. The verb asserts the final URL is still the
   member view, so a future redirect is a FAIL and not a silently different page.
3. **A profile's degree badge is rendered twice, with different values.** On a
   1st-degree profile the top card holds a `p` reading "- 1st" AND, inside a
   `div[data-display-contents]`, a second `p` reading "- 2nd". Only one is
   visible. `read-profile` reads the VISIBLE one and fails if two visible badges
   disagree, rather than taking the first in document order.

## Surfaces, and which rendering each one serves (measured 2026-09-09)

| Surface | Rendering | Anchor the code uses |
|---|---|---|
| `/in/<slug>/` profile | new React (SDUI) only, `[data-urn]` 0 | `div[id$="Topcard"]`, `div[id$="About"]` |
| `/company/<slug>/about/?viewAsMember=true` | classic org page | `.org-top-card-summary__title`, `dl`/`dt`/`dd` |
| `/company/<id>/admin/...` | classic | `.member-analytics-addon-*` (the trap), `table` |
| `/search/results/people/` | new React (SDUI) | `div[role=listitem]`, `p a[href*="/in/"]` |
| `/search/results/content/` | new React (SDUI) only | `div[role=listitem]`, control-menu label |
| `/notifications/` | classic | `article.nt-card`, `a.nt-card__headline` |

The signed-in PRESENCE check has to work on both renderings: on the classic
pages `.global-nav__me` exists, on the SDUI profile and search pages it does not.
What is present on every one of them is a button whose accessible name is "Me"
or ends in " Me". That is what `assert_signed_in()` tests for.
