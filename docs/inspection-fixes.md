# The fix pass answering the independent inspection

The Manager's account, 2026-09-09 night, branch `phase-2-reading`, worktree
`D:/ReposFred/cc-linkedin.mission`.

It answers `docs/rulings-inspection-2026-09-09.md`, R1 to R18, which are the
Architect's rulings on the four Codex inspection passes
(`docs/inspection-slice-1-urn.md` through `-slice-4-claims.md`). The rulings are
what was built, not the findings directly.

**Read this as self-testimony.** It is written by the session that did the work,
about its own work, and it is exactly as persuasive as that makes it. Section 4
is the list of what is NOT proven, and it is the section worth reading first.

**Nothing here was proved on the live site.** The LinkedIn daily view cap was
exhausted (80 of 80) for the whole of this pass and the Architect had already
refused to raise it (`docs/ruling-view-cap-2026-09-09.md`). No profile, company
page or search was opened. Everything below was proved OFFLINE, against strings
and fakes, and section 4 says exactly which claims that leaves standing and
which it does not.

---

## 1. What was done, ruling by ruling

Every ruling is answered. R14 is deliberately NOT executed - it is the owner's.

| | | |
|---|---|---|
| R1 | the urn is READ from the landed page | `kit/identity.py`, `kit/search.py` |
| R2 | a permalink handed to a mutating verb names the post it acts on | `kit/identity.py`, `kit/comments.py`, P2-6c |
| R3 | the lock is released on every path; an unreadable lock is broken | `kit/browser.py` |
| R4 | an unreadable table is a failure; stats proves which Page | `kit/account.py` |
| R5 | `can_connect` fails rather than guesses | `kit/people.py` |
| R6 | a number grammar; the ambiguous fails | `kit/people.py` |
| R7 | `EXPECTED_VIEWS` deleted; a view registry; the stray-tab assertion | `kit/browser.py`, `kit/selftest.py` |
| R8 | an empty expectation is a FAIL | `kit/selftest.py` |
| R9 | nothing is skipped; the run reconciles its row inventory | `kit/selftest.py` |
| R10 | P2-7 asserts what the verb does not, and is labelled a smoke test | `kit/selftest.py` |
| R11 | vacuous truth is banned | `kit/selftest.py` |
| R12 | profile B must be 1st- or 2nd-degree | `kit/selftest.py` |
| R13 | the public-repository leak comes out of the tree | `docs/`, `kit/search.py`, `tools/` |
| R14 | how Phase 2 lands, given the leak is already pushed | **NOT DONE - the owner's** |
| R15 | `pace.json` keeps its guarantee or stops making it | `kit/browser.py` |
| R16 | a read-only verb does not change the owner's machine | `kit/search.py`, `cc_linkedin.py` |
| R17 | redact by SHAPE, not by enumerating forms | `tools/survey.py` |
| R18 | a redaction check that can FAIL | `tests/test_no_leak.py` |

### The two that matter most

**A wrong-but-well-formed permalink can no longer reach `comment`, `react` or
`delete-post` (R1, R2).** The resolver proved only that some substring of the
browser's final URL matched a permissive regular expression, and `Post.load()`
then fell back from the card for the requested urn to the first arbitrary post
card on the page. Identity is now READ FROM THE PAGE - the post card's own
`data-urn`, the canonical link, `og:url` - and the URL path is only allowed to
AGREE with it. Disagreement is a failed row naming both. More than one distinct
candidate anywhere is ambiguity, not a first match. The `card_any` fallback
requires exactly one post card AND the page stating it is the urn asked for.

**A wedged lock can no longer stall every session on this machine (R3).** The
lock is taken as late as it can be, the whole of `__enter__` releases it on any
`BaseException`, the release sits in a `finally` nothing can skip, and the
sentinel is written whole and linked into place so a partial lock cannot exist -
which is what makes "a lock that will not parse is a BROKEN lock" a safe rule.

### The leak (R13, R17, R18) - and what it cost to get right

This repository is PUBLIC. The fourth inspection pass found third-party
identifiers in it, and found `docs/phase-2-fixes.md` carrying a sentence saying
there were none - false in the same file that made it. Three exact `lnkd.in`
short links were handwritten into the `kit/search.py` docstring; following one
recovers a real person's post and its author.

The first pass at this fix taught the redactor the named forms it had missed.
The Architect verified rather than took it, and found the same post id still in
a committed dump, written `shareId=<19 digits>` inside a DOM element id. **That
is the entire defect repeating itself one level down: a redactor that knows N
forms always loses to form N+1.** R17 replaced the enumeration with a SHAPE
rule - every run of fifteen or more consecutive digits, wherever it appears -
and R18 required a check that tests the ARTEFACT rather than the redactor.

Running that check for the first time found **nine**, not one: the `shareId` the
Architect named, and eight nobody had looked for - the whole urn percent-encoded
inside notification hrefs, `li%3Aactivity%3A<19 digits>`. That is the argument
for R18 in one line.

## 2. Every test was watched failing first

There were no tests in this repository before tonight. There are now **122**,
in `tests/`, and they run in about two seconds with no browser and no network:

```
py -3.11 -m unittest discover -s tests -t . -v
```

A test that has never been watched failing is decoration, so each was run
against the behaviour it replaces before the fix was written. What was seen is
in `docs/evidence/`, one file per area, with the symptom rather than only the
assertion:

| evidence | what was seen |
|---|---|
| `watched-failing-identity.txt` | 17 of 24. Twice: `urn:li:activity:...222 != urn:li:share:...111` - a well-formed permalink for a DIFFERENT POST |
| `watched-failing-lock.txt` | 9 of 15. Five entry paths, an interrupt, the `stop()` path, and three unreadable-lock cases that did not merely fail - they sat waiting for a lock nothing would ever release |
| `watched-failing-selftest-r8-r11.txt` | `headline=` accepted, `"" in any_headline` is `True`, `every([])` is `True` |
| `watched-failing-selftest-r7-r12.txt` | `EXPECTED_VIEWS = 8`; `'3rd'` accepted for profile B; **P2-6c's whole assertion satisfied by a STRANGER'S post** |
| `watched-failing-numbers.txt` | `1,2K -> 12000`, `12+3 -> 123`, `1.234 -> 1`, `12,,345 -> 12345` |
| `watched-failing-stats.txt` | an empty tbody and an all-short table both exit successfully with `impressions=0`; a `-` cell adds a literal zero to an aggregate |
| `watched-failing-can-connect.txt` | a DISABLED invite control reported as `can_connect: true` with an invite URL |
| `watched-failing-pace.txt` | 40 concurrent views counted as **2**; with one slot left under a cap of 80, **8 of 8** runs allowed past it |
| `watched-failing-leak.txt` | nine 15-digit content ids in the committed dumps |

The identity extraction was committed in TWO steps on purpose (`32efff7` then
`636b6e7`): the first lifts the defect out of `kit/search.py` and
`kit/comments.py` without altering a character of its behaviour, so the
inspector's breaking inputs could be put on it and watched failing; the second
replaces the body. The failing state is in git, not only in a text file.

## 3. Two defects nobody had found, both caught by a test that could fail

**The R3 fix was itself broken on Windows, and the R15 concurrency test found
it.** Six concurrent writers wedged permanently on the new lock. Python's
`open()` on Windows does not ask for `FILE_SHARE_DELETE`, so while any waiter
has the lock file open to read who holds it, `os.remove` raises a sharing
violation - and the release path swallowed it as `except OSError: pass`. The
lock then stayed behind carrying a LIVE pid, which no reclaim rule will ever
touch. That is the R3 defect exactly, one layer down, put back by an error
handler that treated "I could not do it" as "it is done". `_discard` now retries
for a bounded three seconds and logs loudly if it still cannot.

**The R13 fix was incomplete, and the R18 artefact check found eight more of
it.** Described above.

Neither was in any inspection. Both were found because a fix was given a test
that could fail. That is the argument for R18 generalised: an implementation
with no failing check behind it is a claim, not a guarantee.

## 4. WHAT IS NOT PROVEN

Read this before trusting anything above.

**Nothing has run against LinkedIn.** Not one verb, not one selftest row. Every
claim in sections 1 to 3 is about code behaviour against strings and fakes. The
live proving is a separate job for a fresh Manager after the cap rolls; see
`docs/STATE.md`.

**R1's survey was not done, and the code refuses rather than guesses.** R1.1
asks which identity sources a landed post page actually carries - `data-urn`,
canonical, `og:url` - and says to survey it BEFORE writing the code, because
Phase 2 already learned the content-search page carries none of them. That
survey needs the live site. So `resolve_post_identity` requires the page to
state its own identity and returns an unresolved row with a `resolve_error`
printing a CENSUS of what the page did carry when it does not. **The first live
`--resolve` run performs the survey by running**, and it may well come back
0-of-3 resolved with P2-6b red. That is the instrument reporting what it can
read, not a regression - and the census in the error is the survey result.

**A kind mismatch between the page and the path would fail a row, by ruling.**
R1.2 says the URL path must AGREE with what the page said and disagreement is a
FAIL. If a live run shows the page saying `urn:li:activity:<n>` while the
`/posts/` path says `urn:li:share:<n>` for the same post, every row fails. The
error distinguishes "the same post id under a different urn kind" from "two
different posts" precisely so that evidence exists for the Architect to amend
R1.2 if it turns out to be wrong about the world. **It was not softened
pre-emptively.**

**`--resolve` now dies on a short link that leaves LinkedIn.** R1.5 requires
`Browser.read`, which asserts we are signed in, and that assertion is a `die`.
One off-site or authwalled short link therefore fails the whole verb rather than
one row. That is deliberate - catching it would swallow a genuine "you are
signed out", which is the fail-open this phase exists to stop - but it is a
behaviour change and it is named here.

**R6.1's measurement was not made.** It leaves it to this pass whether `1,2` is
a decimal comma or a failure, "after measuring what LinkedIn actually renders in
a European locale". That needs the live site in another locale. It FAILS, which
is R6.3's default and the only safe direction: accepting it means guessing
between 1200 and 12 with no evidence, and the wrong guess is silent and off by a
factor of ten. The reasoning is in the code beside the grammar.

**R5's menu scoping has no offline test.** The page-global menu query is fixed -
`MENU_JS` reads inside the one visible `[role=menu]` and refuses when there is
not exactly one - but proving it needs a page with two open menus. The test file
says so rather than leaving it looking covered. The settle loop's TIMING (eight
seconds, two agreeing reads) is a judgement, not a measurement.

**R10 is the honest label, not the correspondence check.** P2-7 now asserts
things `notifications` does not enforce - ranks 1..n, the limit, an actor or
target on every row, `unread` actually a boolean - and it PRINTS ITSELF as a
smoke test. **The phase does not claim `notifications` is proven.** R10 allowed
either; this is the second.

**R7 gave something up, and it should be said.** The old P2-9 could catch "this
block cost a different number of views than it should". The new one cannot: if
the block comes to cost seven views, the registry says seven, the counter says
seven, and P2-9 passes. That question now belongs to the row inventory, which is
a denominator rather than an arithmetic identity somebody can edit into
agreement. The trade is the ruling's, and it is the right way round - a constant
that can be retuned until a run goes green is worse than no constant - but it is
a loss and not a pure gain.

**The row count changes.** A clean run was `passed=25 failed=0`. The rows are
renamed and the inventory is reconciled, so a clean run is now **29 declared
rows** (15 Phase 1 + 13 Phase 2 + INVENTORY), plus one more per leftover Page
post the sweep finds. `RESULT selftest ... rows=N/M` carries the denominator.
**Do not read the old 25 as a target.**

**The three post ids from the inspection remain in
`docs/inspection-slice-1-urn.md`.** R13 does not name that file, and editing an
independent inspector's own review is the Architect's to own; he said he was
doing it himself with a visible note. It was left alone deliberately.

**Redaction fixes the tree, not the history.** The branch is already pushed to a
public repository. R14 is the owner's call and nothing here rewrote history or
force-pushed.

**`tools/redact_surveys.py` was applied to dumps that cannot be regenerated.**
The redaction is by rule and is idempotent and checkable (`--check`), but the
dumps were edited in place rather than retaken, so they are now a redaction of a
measurement rather than a measurement.

## 5. Where to look

* `kit/identity.py` - one grammar for post identity, and why it is a grammar.
* `kit/browser.py` - `FileLock`, `Browser.__enter__`/`__exit__`, `Pace`, the
  view registry, `open_tabs`.
* `kit/selftest.py` - `Rows`, `_same_post`, `_notification_holds`, and the
  comment where `EXPECTED_VIEWS` used to be, which says what was given up.
* `tools/survey.py` - the identifier rules, named forms then the shape rule.
* `tools/redact_surveys.py` - applies them to the committed dumps; `--check`.
* `tests/` - 122 offline tests. `tests/README.md` says how to run them.
* `docs/evidence/` - what each one looked like before the fix.
