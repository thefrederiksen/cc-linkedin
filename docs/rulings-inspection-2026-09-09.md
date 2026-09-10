# Rulings on the independent inspection

The Architect's, 2026-09-09 night, answering the findings in
`docs/inspection-slice-1-urn.md` and `docs/inspection-slice-3-verbs.md`. Rulings
on the two remaining passes are appended when they land.

These amend `docs/phase-2-design.md` and, where they touch it,
`docs/rulings-phase-2.md`. Where they disagree, THIS file wins.

Several findings are in code that is already on `main` (Phase 1). That is in
scope: Phase 2 is what makes them dangerous, and a fix and the thing that stops
it regressing are one unit.

---

## R1. The urn must be READ from the landed page, never inferred from its URL

**Finding:** `search-posts --resolve` proves only that some substring of
`page.url` matches an unanchored regex. A full urn in a query parameter beats
the real one in the path, because the full-urn pattern is searched first; and
the path pattern takes the FIRST `-kind-digits` motif anywhere in the string
rather than the terminal one. Ambiguity has no outcome: the first match becomes
a non-null permalink with a null `resolve_error`, counted as resolved, and no
caller can tell it from a good one.

**Ruling. Stop parsing the URL for identity. Read the post's own identity off
the page it landed on.** The landed post page states what post it is - in the
classic rendering as a `data-urn` on the post card, and in both renderings as
the canonical URL the page publishes for itself. That is a measurement. A
regular expression agreeing with a string it was pointed at is not.

Specifically:

1. After navigating, read the identity from the DOM. Prefer, in order: the post
   card's own `data-urn`; the page's canonical link or `og:url`; the post
   control menu's own "Copy link to post" value. **Survey which of these the
   landed page actually carries before writing the code** - Phase 2 learned that
   the content-search page carries none of them, and that is exactly why we are
   here.
2. **Cross-check, and require agreement.** If the URL path also yields a
   candidate, it must agree with what the page said. Disagreement is a FAIL for
   that row - never a preference for one of them.
3. **Exactly one candidate, or it is not resolved.** More than one distinct
   candidate anywhere is ambiguity, and ambiguity is `permalink: null` with a
   `resolve_error` naming both. First-match is banned.
4. Anchor the patterns and validate the host and path type. A final URL on
   another host, or on a `/company/` or `/school/` path, resolves to nothing.
5. `--resolve` uses `Browser.read`, not `Browser.goto`, so the signed-in
   assertion runs on it like everything else (see R3).

## R2. A permalink handed to a mutating verb must name the post it acts on

**Finding, which the inspector followed downstream without being asked:**
`kit/comments.py` `urn_of` is also an unanchored substring search, and
`Post.load()` falls back from the card for the requested urn to
`card_any` - **the first arbitrary post card on the page** - when the exact one
is not found. So a wrong-but-well-formed permalink reaches `comment`, `react`
and `delete-post`. The acceptance row cannot catch it: it asserts only that
`read-post` returns a non-empty author, and never compares that author to the
search row the permalink came from.

**Ruling. The fallback is the defect, not the parser.**

1. `urn_of` is anchored and requires exactly one match in the string it is
   given. Two different urns in one input is a FAIL.
2. **`Post.load()` may use `card_any` ONLY when it can prove the page holds
   exactly one post card AND the page's own stated identity matches the urn
   asked for.** Otherwise it fails, naming the urn it wanted. Today's fallback
   is silent and unconditional, and on a permalink page it is usually right,
   which is precisely why nobody noticed.
3. The `--expect` phrase guard stays, and stays optional, but it is not the
   answer to this: a phrase is not an identity, and `delete-comment` and
   `unreact` do not even accept it.
4. P2-6c is rewritten to compare the resolved post's AUTHOR AND TEXT with the
   search row it came from. Asserting a non-empty author proves the page loaded,
   which was never in doubt.

This is the highest-consequence item in the whole phase. Acting on a stranger's
post is not a degraded result, it is a different act.

## R3. The lock is released on every path, and a lock we cannot read is broken, not held

**Finding (CRITICAL):** the lock is taken before several fallible entry
operations and only the CDP-connect failure releases it, so a failure in
`sync_playwright().start()`, `contexts[0]`, the CDP session, or the
`createTarget` timeout leaves `__enter__` never returning and the lock file
behind - with no `__exit__` to run, because the `with` statement never began. On
the way out, `_pw.stop()` raising skips the release on the very next line. And a
half-written lock file parses as `{}`, has no pid, is never classified as dead,
and so is never reclaimed by anything.

A wedged lock stalls every other session on this machine, including the job that
posts the owner's video series each morning. This is the finding most likely to
hurt him in a way he cannot diagnose.

**Ruling:**

1. **Acquire the lock LAST**, after every fallible setup step that can be done
   without it; and wrap the whole of `__enter__` so that ANY exception -
   `BaseException`, so a KeyboardInterrupt counts - releases the lock before it
   propagates.
2. **Release in a `finally` that nothing can skip.** No fallible call may sit
   between the last statement and the release.
3. **Write the lock file ATOMICALLY** - write a temporary file, then rename it -
   so a half-written lock cannot exist. Once it cannot exist, a lock file that
   will not parse is a broken lock and is reclaimed with a log line saying so.
   Do NOT reclaim on a timer instead: a grace period would let a second run
   steal the lock from a healthy holder that was merely slow, which is worse
   than the bug being fixed.
4. `close_file_dialogs` and its `die` must not sit between the release and the
   end of `__exit__`.

## R4. An unreadable table is a failure, and stats must prove which Page it read

Both are the phase's own rule and neither needs argument: a table body that is
empty or unreadable is a FAIL, not a set of zeroes, and `stats` asserts that the
Page it landed on is the Page it was asked for before it reads a number.

Cleared, and worth recording as cleared: **the member-analytics widget cannot
reach a stats number.** The inspector confirmed the header assertion and the
cells come from the same local `table` object, so the 5-versus-48 mix-up the
ruling in `rulings-phase-2.md` was written against is genuinely gone.

## R5. `can_connect` fails rather than guesses, in both directions

A value that means "you can invite this person" must never be produced by a code
path that did not positively see an invite control, and "you cannot" must never
be produced by a path that merely failed to look properly. Where it cannot
decide, the field is null with a reason, and the reason names what it could not
read.

## R6. Numbers: reject the ambiguous, do not normalise it away

**Finding:** `to_int` strips every comma and every plus before deciding what the
number means, so the European `1,2K` becomes `12K` and returns **12000 instead
of 1200** - wrong by a factor of ten, silently. Global plus-stripping turns
`12+3` into `123`.

**Ruling. Stripping separators before parsing is the bug; the fix is a grammar,
not another replace.**

1. A comma is a thousands separator only when followed by exactly three digits,
   and only in a well-formed group. A comma followed by one or two digits is a
   decimal comma; accept it as a decimal point, or FAIL - the Manager decides
   which after measuring what LinkedIn actually renders in a European locale,
   and writes down what it saw. **What it must not do is silently pick one.**
2. A plus is stripped only when TRAILING. A plus anywhere else means the string
   is not a number and it fails.
3. Every ambiguous form fails loudly. "3 followers" is not the shape this has to
   get right; a Page with 1,2K followers in a European locale is.

## What does NOT change

`docs/phase-2-design.md` section 0 stands and is reinforced by every finding
above: a read that comes back empty is a failure, never a result, and every
assertion is a check for something PRESENT. Nothing here relaxes it.
