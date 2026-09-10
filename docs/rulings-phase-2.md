# Mid-build rulings, Phase 2

The Architect's, 2026-09-09 evening, answering the two questions the Manager
raised in `docs/phase-2-report.md` after the survey. They amend
`docs/phase-2-design.md`; where the two disagree, THIS file wins.

Both questions came from the live page contradicting the settled design, which
is the case the design document said to bring back rather than build around. The
Manager was right to stop on both.

---

## Ruling 1 - `search-posts` returns a short link, and resolves only when asked

**Adopt the Manager's option 1, with four amendments.** The urn requirement is
dropped from the default path. It was never decoration - the point of
`search-posts` is to hand a post to Phase 1's verbs, which take a permalink -
but a required field that cannot be produced honestly is not a requirement, it
is a licence to invent one. Pairing the document's six urns to the six cards by
ORDER is exactly the assumption-dressed-as-proof this phase exists to refuse,
and the Manager was right to say so rather than ship it.

Amendments:

1. **No field called `url`.** A caller reaching for `url` and silently getting a
   shortener is the same fail-open shape as an empty read. The record carries
   `share_url` (the `lnkd.in` link from "Copy link to post", always present) and
   `permalink` (the real `urn:li:activity` URL, or null). Two names, two
   meanings, no ambiguity. Drop `url_kind`; it is not needed once the fields say
   what they are.
2. **`--resolve` follows the short link IN THE BROWSER**, never by an HTTP
   request made outside it. The rule in this repo is that the browser is the
   tool, and an out-of-browser request to LinkedIn infrastructure is the shape
   of the thing the owner shut down. It costs a navigation, not a view - a post
   permalink is not a profile and notifies nobody, so it does not touch the view
   cap.
3. **`--resolve` is hard-capped at 10 rows per run**, and refuses above that
   naming the cap and telling the caller to lower `--limit`. A row whose short
   link resolves to something without `urn:li:activity` gets
   `permalink: null` and a `resolve_error` string - recorded, never dropped -
   and the `RESULT` line carries `resolved=<n>/<m>` so a shortfall is visible on
   the one line a caller reads.
4. **P2-6 gains a chained assertion.** As the Manager proposed - at least 3 rows,
   every row a non-empty `author` and a `share_url` on `lnkd.in`; and with
   `--resolve --limit 3`, every `permalink` contains `urn:li:activity` - plus:
   the first resolved `permalink` is then handed to Phase 1's `read-post` and
   must come back with a non-empty author. That is the only assertion that
   actually proves the feed-into-Phase-1 promise, rather than proving a string
   matches a regular expression.

The measured facts behind this - four loads, `[data-urn]` 0 every time, one
`/feed/update/` href belonging to a quoted post, three consecutive short links
read from the clipboard, and the per-card token that has no urn within 4,000
characters - go in the `kit/search.py` docstring with today's date. The next
reader must not have to rediscover that the permalink is genuinely absent.

## Ruling 2 - `stats` reports what the Page states, sums nothing it does not label, and drives the window

**Adopt the Manager's option 1 for the record shape and option 3 for the window:
drive the time-range control.** Three amendments.

1. **The sum is called what it is.** Not `totals`. The record carries
   `sum_of_posts`, whose members each keep the Manager's
   `source="content-engagement-table-sum"`. A page's real impressions are not
   the sum of its posts' impressions - they include arrivals the table never
   lists - so a field named `totals` would be read as LinkedIn's own aggregate
   by every caller that did not read the source string. The name has to carry
   the meaning, because the field name is what gets used and the provenance
   string is what gets skipped.
2. **`--days` defaults to 30 and DRIVES the control**, then asserts the range
   stated on screen matches what was asked. A window that silently follows
   LinkedIn's default makes every run incomparable with the last, which defeats
   the only reason to have a stats verb. If the control cannot be driven, that
   is a `FAIL` naming the control - never fifteen days of numbers labelled
   thirty. `--days 0` skips the control and reports whatever the page states,
   for the case where the control has changed and the numbers are still wanted.
   `window_start`, `window_end` and `window_days` are always derived from the
   stated range, never from the argument.
3. **The member-analytics trap gets an active guard, not just avoidance.** This
   is the best find of the survey: four hits, the right shape, the right four
   labels, and they are Soren's OWN member numbers (5 impressions) sitting on
   the Page's admin screen next to the Page's real 48. Reading them would have
   produced a plausible, precise, wrong answer on every run forever - and
   nothing downstream could have caught it.
   * Every number is read from inside the "Content engagement" `<table>`, scoped
     to that table.
   * Before any cell is read, the table's header labels are asserted to be the
     expected columns. A header that does not match is a `FAIL`, not a fall back
     to something else on the page. This is a presence check, so a layout swap
     that moves the table is loud rather than silent.
   * `kit/selectors.py` carries the trap as a dated NEGATIVE note - the selector
     `.member-analytics-addon-summary__list-item`, what it actually holds, and
     the two numbers measured today - so the next person does not reach for the
     obvious thing.
4. `followers` is read from the admin header, parsed to an integer, with the raw
   string kept. **Zero is a valid follower count** - a new Page has none - so the
   verb fails on a value it cannot parse, never on a value it does not like. The
   acceptance row asserting at least one follower is a fact about our fixture,
   not a rule about the verb.

P2-8 becomes: `followers` is an integer, the page name matches, `window_days`
equals the days asked for, the window is a real date range, and every row's
`impressions` parses as an integer.

---

## The three settled findings: all three blessed as measured

These were the Manager's to decide and it decided them correctly. Recorded here
so the Inspector checks them rather than takes them on trust.

1. **P2-5's fixture changes to the query "Soren Frederiksen mindzie".** The
   original fixture was wrong about the world: ten other people of that name come
   first, and the owner's own profile is not on page one. Both dumps are
   committed, the failing one included, which is the right way to record a
   fixture that was replaced.
2. **`read-company` navigates to `/company/<slug>/about/?viewAsMember=true`**
   and asserts the final URL is still the member view. An admin being bounced to
   his own dashboard is a redirect the verb must notice, not absorb.
3. **`read-profile` reads the VISIBLE degree badge and fails when two visible
   badges disagree.** A profile that renders "1st" and "2nd" in the same top
   card, one of them hidden, would have made document order into a coin flip.

## What does not change

Nothing else in `docs/phase-2-design.md` moves. In particular the rule the phase
hangs on stands untouched: a read that comes back empty is a failure, never a
result, and every assertion is a check for something PRESENT.
