# Inspection slice 2: can the self-test fail?

## Verdict

**Not clean.** The current Phase 2 block is capable of going red, and the three
profile rows are materially better than the old permitted-set check. In
particular, P2-2 compares eight supplied expectations and P2-10 forces both of
the defect-bearing facts: `connect_via == "more-menu"` and no employer with a
reason. Those are real assertions.

The advertised fail-closed guarantee is nevertheless false in four proved
ways:

1. **HIGH — PROVED:** `headline=` is accepted as a supplied key and turns the
   headline comparison into a tautology. A human-oracle row can therefore
   silently assert nothing about the headline.
2. **HIGH — PROVED:** P2-9's expected view count is a hand-set constant used as
   its own oracle. Retuning that constant makes a view-count-only failure pass;
   nothing executable independently derives the expected number. P2-9 also
   omits the required stray-tab assertion entirely.
3. **HIGH — PROVED:** a missing `--page` or `--page-name` silently skips the
   whole Page publish/delete block. No expected check inventory is reconciled at
   the end.
4. **MEDIUM — PROVED:** Phase 2's `attempt`/`check` accounting no longer counts
   an expected verb failure as a failed row, but the whole self-test can still
   count one Phase 1 operation as both passed and failed. P2-6, one acceptance
   row in the design, is also counted as three checks.
5. **MEDIUM — PROVED:** P2-7 merely repeats conditions that `notifications`
   already enforces before returning. Against the current verb, it can only go
   red when the verb fails/exits or its output cannot be parsed; it cannot tell
   a correct notification from a wrong one. P2-8 is not wholly crash-only, but
   its per-post assertion passes vacuously when zero posts were read.
6. **LOW — PROVED:** the required 1st-/2nd-degree shape for profile B is not
   enforced. The row also accepts `3rd` and `3rd+`.

This was a source inspection only. No self-test was executed and no LinkedIn
page was opened. P2-6b/P2-6c's resolver behavior is outside this slice as
requested.

## 1. P2-9 chooses its own expected number

The number is a literal:

> `kit/selftest.py:242-248` — “What one full Phase 2 block must cost on the view
> clock” ... `EXPECTED_VIEWS = 8`

The assertion then compares the measured delta only to that same literal:

> `kit/selftest.py:570-576` — `took = views_after - views_before` ...
> `check("P2-9", took == EXPECTED_VIEWS and not os.path.exists(lock) and not dialogs, ...)`

The fixes document repeats the hand-maintained number rather than supplying an
independent derivation:

> `docs/phase-2-fixes.md:163-164` — “`EXPECTED_VIEWS` rises from 7 to 8 ... and
> P2-9 still proves the view counter moved by exactly that.”

**Concrete case:** if a regression makes the block consume seven views and the
only red result is P2-9's `took == 8`, changing line 248 to `7` makes P2-9 pass.
There is no second executable inventory of view-taking operations to disagree.
A repository-wide source search found `EXPECTED_VIEWS` used in executable code
only at its declaration and this comparison. Documentation or review might
notice a careless change; the suite will not.

Therefore P2-9 asserts **a number the test chose for itself**, supported by a
prose derivation. It is not independently derived from the verbs actually run.

There is a second, independent miss. The governing row requires:

> `docs/phase-2-design.md:205` — “lock file released, **no stray tab**, no native
> dialog, `pace.json` view count rose ...”

The implementation checks only the count, lock-path absence, and empty dialog
list at lines 570-576. It never enumerates tabs. A stray tab cannot make P2-9
fail.

## 2. Row-by-row provenance and ability to fail

“PAGE” below means an expectation separately transcribed by a person, not a
value read by the verb under test. The code cannot prove that a caller really
obtained a command-line expectation from the screen.

| Row | What it compares against | Can it distinguish a successful wrong record? | Judgment |
|---|---|---|---|
| P2-1 | Eight fields against the committed `SOREN_EXPECT`; then test-computed invariants and `about` length | Yes, if the committed values are current and non-empty | **Genuinely useful correspondence**, but the oracle is a test constant, not a fresh page reading. The `headline=` loophole also applies if the default is overridden. |
| P2-2 | Eight fields against runtime `--other-expect` | Yes, if a person actually read the values and did not use an empty headline | **Genuinely sound core.** Exact name/location/company/degree/primary/connect/count comparisons can catch a normally returning wrong verb. Headline is substring rather than exact by design. |
| P2-2b | Test-computed shape and cross-field invariants; degree membership in a permitted set | Yes for such contradictions as a count in `current.company`, a primary action absent from `actions`, or an invite URL for the wrong slug | **Useful invariant row, not PAGE correspondence.** `kind`, `rendering`, null title, and degree-domain checks largely repeat values the producer constructs. |
| P2-3 | A test-invented wrong phrase and the expected refusal protocol | Yes: an incorrectly successful record makes the row fail | **Sound negative test:** it requires non-zero, no parsed record, and the positive presence of `FAIL`. Its “no record” arm inherits `_records` silently discarding malformed JSON. |
| P2-4 | Hard-coded fixture name plus the permitted numeric range `int >= 1` | Yes: a normal return with the wrong name or zero followers fails | **Sound fixture assertion**, but not a current human reading of both values. |
| P2-5 | Hard-coded expected first URL (`SOREN`) | Yes: a normal search with another first result fails | **Sound exact fixture assertion**, not merely set membership. |
| P2-6a | Minimum cardinality and permitted shapes: author present, `share_url` contains `lnkd.in` | Yes: the verb permits one row, some missing authors, or some missing links, all of which this row rejects | **Sound non-vacuous shape check**, but it establishes no correspondence between a result and what the person saw. P2-6b/P2-6c are not re-inspected here. |
| P2-7 | Minimum cardinality and non-empty text | Not against the current producer: it filters out empty text and refuses zero rows before returning | **Crash/refusal-only duplication in the current build.** It is not false, but it is padding as independent acceptance evidence. |
| P2-8 | Caller-supplied page name, test-chosen `30` days, type/non-empty checks, and a permitted integer type for each post | Only partly. It compares no follower or impression number to an independent PAGE value; zero posts satisfy the `all(...)` assertion | **Some useful shape checks, no numeric correspondence.** It can fail on a normally returned post whose impression is `None`, but cannot detect wrong integer values. |
| P2-9 | Test-computed process state and hand-set `EXPECTED_VIEWS` | It can detect a surviving lock/dialog or a delta different from the literal; it cannot detect a retuned oracle or a stray tab | **Not an independent view-count proof.** |
| P2-10 | Eight runtime PAGE expectations plus fixed shape facts: connectable, via More, invite URL contains this slug, company absent with a reason; then invariants | Yes | **The strongest row and genuinely sound for the two shipped defects**, subject to the empty-headline and human-provenance holes. |

The exact correspondence implementation is real:

> `kit/selftest.py:150-165` — `name`, `location`, `current.company`, `degree`,
> `primary_button`, `can_connect`, and `connections` use equality; `headline`
> uses `exp["headline"].lower() in head.lower()`.

P2-10 also hard-codes the defect-bearing shape rather than trusting only the
operator's expectation:

> `kit/selftest.py:481-495` — `can_connect is True`, `connect_via == "more-menu"`,
> the invite URL contains the target slug, and `current.company is None and
> bool(current.company_reason)`.

That is not padding. It can fail while `read-profile` returns normally, and it
targets both regressions described at `docs/phase-2-fixes.md:149-154`.

### Rows that can only fail when the verb fails

For the current Phase 2 implementation, **P2-7 is the only in-scope row whose
post-return assertions are already guaranteed by its producer**. The row says:

> `kit/selftest.py:546-550` — `ok and len(recs) >= 1 and all((x.get("text") or
> "").strip() for x in recs)`.

But `notifications` first filters to rows with text and then refuses an empty
list:

> `kit/account.py:103-108` — `rows = [r for r in rows if r["text"]][:limit]`;
> `if not rows: die("no notifications ... this is a failure and not an empty list")`.

Thus a normal return from the current verb necessarily satisfies P2-7. A future
mutation that removes those producer guards could make the self-test assertion
valuable, but the row does not presently supply an independent truth about the
notifications on the page.

P2-8 is weak but not crash-only: `stats` may normally encode `"-"`/empty table
cells as `None` (`kit/account.py:334-343`), while P2-8 requires every returned
`impressions` value to be an integer.

Profile B's promised shape is also looser than the documents say. The design
requires “a 1st- or 2nd-degree profile” (`docs/phase-2-design.md:207-210`), but:

> `kit/selftest.py:65` — `DEGREES_NOT_SELF = ("1st", "2nd", "3rd", "3rd+", "you")`
>
> `kit/selftest.py:463-466` — the row accepts a value in `DEGREES_NOT_SELF`.

The preceding general degree check excludes `you`, but `3rd` and `3rd+` remain
accepted.

## 3. Expectation-key validation

The claim is true for omitted and unknown **keys**, but false for empty
**values**.

The parser records a key even when its value is empty:

> `kit/selftest.py:103-113` — blank semicolon parts are skipped, then
> `got[k.strip().lower()] = v.strip()`; `missing` tests key presence and `unknown`
> tests key names.

It exits non-zero on either list:

> `kit/selftest.py:114-119` — `if missing or unknown: ... sys.exit(1)`.

Consequences, case by case:

- **Omitted key:** fails in `_expect`.
- **Unknown key:** fails in `_expect`, even if all required keys are also
  present.
- **Misspelled key:** fails as both one missing expected key and one unknown key.
- **Flag absent entirely:** fails before any row because the four profile
  fixtures are gated together (`kit/selftest.py:314-333`). The CLI supplies no
  default for either flag (`cc_linkedin.py:779-790`).
- **Entire flag value empty (`""`):** also fails the same truthiness gate.
  Whitespace-only text is truthy, reaches `_expect`, and fails with every key
  missing.
- **One empty value:** only `can_connect` and `connections` have value-level
  validation (`kit/selftest.py:120-130`). Empty `name`, `headline`, `location`,
  `company`, `degree`, or `primary` is accepted by the parser as a supplied key.
  Some later invariants happen to reject empty degree/primary; that is not parser
  validation.

The concrete silent no-op is headline:

> `kit/selftest.py:152-153` — `exp["headline"].lower() in head.lower()`.

For `headline=`, Python evaluates `"" in any_headline` as true. P2-2 and P2-10
can therefore report their headline sub-check passed for any non-count-shaped
wrong headline. This directly contradicts:

> `kit/selftest.py:83-85` — “every key is REQUIRED ... because a mistyped key
> would otherwise silently assert nothing at all.”

An empty `name`, `location`, or `company` is not a total no-op—it asks for an
empty record value—but it is still an absence-shaped oracle and can bless a
producer regression that emits empty strings. `company=` is separately rejected
for the menu fixture because that fixture must say `company=none`
(`kit/selftest.py:334-340`).

`--menu-expect` is parsed before the run starts. `--other-expect` is parsed only
after profile B returns a record (`kit/selftest.py:454-462`), so a malformed
other expectation can spend a profile view before terminating the run. If the
verb fails first, the malformed expectation is not diagnosed, but the row is
already red.

## 4. Missing fixtures and skips

No Phase 2 acceptance row is silently skipped for a missing Phase 2 fixture:

- Missing `--other-profile`, `--other-expect`, `--menu-profile`, or
  `--menu-expect` exits non-zero at lines 314-333 before the block runs.
- Missing records in P2-1/P2-2/P2-10 become explicit failed checks
  (`kit/selftest.py:443-459`, `478-496`).
- The no-resolved-row branch explicitly fails P2-6c rather than skipping it
  (`kit/selftest.py:536-543`; resolver substance remains out of scope here).

There is, however, a proved skip elsewhere in the same self-test:

> `kit/selftest.py:400` — `if a.page and a.page_name:`

Everything through Page post creation and deletion at lines 401-428 is omitted
when either value is missing. The CLI declares both options without
`required=True`:

> `cc_linkedin.py:768-769` — `sp.add_argument("--page", ...)` and
> `sp.add_argument("--page-name", ...)`.

P2-8 is still attempted later, so a missing Page fixture is likely to create a
separate red stats row rather than a clean run. That does not change the narrow
finding: the Page write/delete check itself is skipped, not failed, and the
summary has no expected-inventory assertion that names its absence.

## 5. Pass/fail accounting

### Phase 2: locally sound

The repair for the old expected-failure accounting bug is present:

> `kit/selftest.py:356-361` — `attempt` runs a Phase 2 verb “WITHOUT counting
> it”; “Every Phase 2 row is counted once, by its check.”
>
> `kit/selftest.py:363-371` — `check` increments exactly one of `passed` and
> `failed`.

Therefore P2-3's intended non-zero verb exit is not first charged as a suite
failure and then counted again. A failed `every(...)` sub-check is printed, but
the enclosing Phase 2 check increments `failed` only once. A missing P2-2 record
increments P2-2 and P2-2b separately; those are two documented rows, not one row
double-counted.

### Whole self-test: counts are not mutually exclusive or an inventory

The Phase 1 pattern still counts an operation as passed before performing its
content assertion:

> `kit/selftest.py:347-354` — `step` increments `passed` whenever `_run` returns
> `ok`.
>
> `kit/selftest.py:382-385` — `read-comments` is counted by `step`; if the new
> comment is absent, `failed += 1`.

The same shape occurs for the reply at lines 387-390 and leftover check at lines
395-398. **Concrete case:** `read-comments` returns normally but omits the newly
created comment. The summary gains one pass for `read-comments` and one failure
for the failed verification. The process still exits non-zero because lines
578-580 exit when `failed` is nonzero, so this accounting defect does not turn
that explicit failure green; it does make the reported pass count false.

The count also does not equal acceptance rows:

- Design row P2-6 is three separately counted checks: P2-6a at lines 523-527,
  P2-6b at 533-534, and P2-6c at 539-543. One design row can contribute two
  passes and one failure.
- Each stale Page post found by `sweep_page` adds another counted
  `delete-leftover` step (`kit/selftest.py:402-403`). The clean pass total varies
  with cleanup work.
- The conditional Page block removes checks without recording a failure at the
  skip site.
- The final gate tests only `if failed`; it never reconciles `passed` with an
  expected inventory (`kit/selftest.py:578-580`).

So every Phase 2 `check()` is exclusive, but `RESULT selftest passed=N failed=M`
is not a trustworthy row inventory.

## 6. Assertions whose success is an absence

These are all absence-shaped success conditions in `kit/selftest.py`, including
the ones that are legitimate negatives. “Anchored” means a positive fact in the
same composite prevents a completely empty run from satisfying the whole row.

| Lines | Absence accepted as success | Assessment |
|---|---|---|
| 112-119 | Expectation parsing succeeds when no missing or unknown key was found | Sound for the key inventory because it compares both directions against all eight `EXPECT_KEYS`; unsound for values because an enumerated key may still be empty. |
| 145-148, 156-165 | Human expectations `company=none`, `can_connect=none`, or `connections=none` become exact `None` expectations | Legitimate page absences, but still absence-shaped. Later reason/relationship checks partly anchor them. |
| 184-186 | `about is None` is acceptable for profiles B/menu | Intentional optional field, but it cannot prove the About path ran. P2-1 closes this with `len(about) > 100`. |
| 193-211 | Missing degree/company/connections/followers can pass when a reason is present; title is required to be absent with a source | Partly anchored by a non-empty reason/source. This proves a reason string exists, not that the relevant page region was read. |
| 218-225 | “not a count,” “company is not connections,” and fields are “not equal” | **Fail-open on empty values.** `_count_shaped` begins with `bool(v)` (line 139), and the equality guards explicitly pass when either value is absent. |
| 233-239 | `can_connect=false/null` requires invite metadata to be absent | Legitimate relational negative, anchored by an exact connection value/degree and a required reason elsewhere. |
| 260-265, 347-354 | A verb/step is `ok` when it raised no exception and no non-zero `SystemExit` | **Fail-open for Phase 1 step credit.** No required `RESULT` or record is checked by `_run` itself. Phase 2 generally adds record/content checks. |
| 278-285 | `every([])` returns true because it found no bad sub-check | Absence-shaped helper behavior, but no current call site supplies an empty list: the profile helpers and P2-10 seed concrete checks. |
| 293-297 | A JSON-looking line that does not parse is silently discarded | This manufactures “no records.” Other positive rows then fail, but P2-3's no-record arm can accept malformed record output. |
| 309-311, 402-403 | No leftover URNs found means no cleanup and no assertion about the sweep's reach | **Fail-open sweep.** Empty and “nothing found” are indistinguishable here. |
| 395-398 | Neither marker string occurs in final `read-comments` output | **Fail-open cleanup proof.** Empty/truncated successful output satisfies it. |
| 464-466 | `degree != self` passes on `None` | The following permitted-set assertion rejects `None`, so the row as a whole is closed on this case. |
| 501-503 | Wrong `--expect` caused no success and printed no parsed record | Legitimate refusal test, anchored by the positive presence of `FAIL`; malformed JSON remains invisible because of `_records`. |
| 556-566 | `all(post impressions are integers)` when `posts == []` | **Vacuous pass.** There is no `len(posts) >= 1` guard. Stats can return a record after reading zero table rows. |
| 574-576 | No lock path exists and `open_file_dialogs()` returns empty | Required cleanup negatives, but neither proves a lock/dialog detector observed a run. The view-count conjunct is meant to anchor them and is itself self-oracled. |

Two nearby `all(...)` assertions are genuinely sound against the empty-run
failure: P2-6a first requires at least three records (`kit/selftest.py:523-527`),
and P2-7 first requires at least one (`kit/selftest.py:548-550`). P2-8 lacks that
cardinality guard.

## SUSPECTED / not proved by source inspection

No additional code defect is asserted on suspicion. Two premises remain outside
what this inspection can prove:

1. The comments say the runtime expectation strings are “what a person reads
   off the screen” (`kit/selftest.py:39-40`, `68-85`). The parser can distinguish
   valid syntax from invalid syntax; it cannot distinguish a human transcription
   from values copied out of the record under test. P2-2/P2-10 are independent
   only if the operator followed that process.
2. This reading proves what the repository's code can and cannot assert. It does
   not establish current LinkedIn fixture contents, current browser behavior, or
   the existence of an out-of-repository CI policy that reviews a changed
   `EXPECTED_VIEWS`. Those were deliberately not exercised because the daily
   view cap is exhausted.

## Bottom line

The builders' narrow claim is **partly true**: P2-1, P2-2, and P2-10 now contain
real per-key record-to-expectation comparisons, and P2-10 can genuinely catch
both shipped profile regressions. It is false as an unconditional claim because
an empty headline silently disables one of those comparisons, and only those
profile rows use a human oracle at all. The remaining rows use hard-coded fixture
facts, test-computed values, or permitted shapes. P2-7 is crash/refusal-only
duplication; P2-8 has a vacuous empty-post pass; and P2-9 can be retuned because
its expected number comes from the test itself.
