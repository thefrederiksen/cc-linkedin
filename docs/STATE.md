# Mission state - the compact handoff

Kept current by the Architect. A fresh Manager needs THIS file, `MISSION.md`,
`phase-2-design.md`, and `cc-devthrottle workflow instructions mission`. Nothing
else. Not a transcript, not a history. For the Phase 2 FIX pass, add
`docs/findings-from-live-use-2026-09-09.md` and `docs/phase-2-fixes.md`. For the
INSPECTION fix pass and everything after it, add
`docs/rulings-inspection-2026-09-09.md` (R1 to R18, what was built) and
`docs/inspection-fixes.md` (what was done and, in section 4, what is not
proven).

Last updated: 2026-09-10, by the Manager of the LIVE PROVING pass. Phase 2 is
now PROVED ON THE LIVE SITE: three consecutive clean runs, both reverts watched
failing, four defects found that no offline test could have found, and two
rulings taken back to the Architect and amended because they were wrong about
the world. The account is `docs/phase-2-live-proving.md` and its section 7 is
what is NOT proven.

## Where the work is

* Worktree: `D:/ReposFred/cc-linkedin.mission`, branch `phase-2-reading`, cut
  from `origin/main` at `a2ea069`.
* The shared checkout `D:/ReposFred/cc-linkedin` is `main` and belongs to
  everybody. Never build there. The `cc-linkedin` command on PATH runs the
  SHARED checkout, so it tests `main`, not this branch.
* On main already: Phase 0 (posting, scheduling), Phase 1 (comments, replies,
  reactions, deletes, selftest).

## Phase 2 - BUILT, NOT INSPECTED, TWO DEFECTS FOUND AND FIXED; VERIFICATION UNFINISHED

Verbs: `read-profile`, `read-company`, `search-people`, `search-posts`,
`notifications`, `stats`. Design settled in `docs/phase-2-design.md`, amended by
`docs/rulings-phase-2.md` (which wins where the two disagree). The build
Manager's own account is `docs/phase-2-report.md` - self-testimony, to be broken
rather than trusted.

| | |
|---|---|
| Survey | done - `tools/survey.py`, eight dumps in `docs/surveys/`, redacted |
| Modules | done - `kit/people.py`, `kit/search.py`, `kit/account.py` |
| Selftest block | done, then rebuilt by the fix pass - see below |
| Hand-driving the live site | done by the Architect; it found what the suite could not |
| Phase 2 fix pass | code done and pushed |
| Independent inspection, four passes | done - Codex, 2026-09-09 night |
| Inspection fix pass, R1 to R18 | **code done, tested offline, pushed. `docs/inspection-fixes.md`** |
| Live proof of any of it | **DONE 2026-09-10 - `docs/phase-2-live-proving.md`** |
| Pull request | not opened - the Architect lands it |

### The independent inspection has NOT been done - SUPERSEDED, kept for the record

*This section describes the state on the afternoon of 2026-09-09 and is left
here because the reason it says what it says is worth keeping. It was overtaken
that night: see the section immediately after it. Do not act on this one.*

`docs/inspection-phase-2-brief.md` exists and is the mandate. No inspector ever
read it. Two Codex sessions were spawned for it (`af3d4f12`, `3aced9e2`); both
times `session spawn` printed a session id and the usual "Message it" footer,
and both times the session never appeared in `session list`, never ran, and
never wrote a line. Filed as thefrederiksen/devthrottle#2802.

The Architect reported the inspection as running, twice, on the strength of that
returned id. It was not running. That is why this row now says what it says: a
spawn that returns an id is a promise, not a fact, and the only proof an
inspection happened is a review file with findings in it.

**Phase 2 does not land on main until a genuinely different agent family has
tried to break it.** Codex is preferred; Gemini or Grok are acceptable. Landing
without one is the owner's call to make explicitly, not an omission to drift
into.

### The independent inspection HAS NOW BEEN DONE (2026-09-09 night)

Run as `codex exec` in the FOREGROUND first, then in the background under a
narrow exception the owner granted when asked (a real review overruns the
10-minute foreground tool limit; the exception covers Codex producing a WRITTEN
REVIEW and nothing else). `session spawn --agent Codex` is still broken from the
Architect's session and is filed as thefrederiksen/devthrottle#2802.

Four passes, model gpt-5.6-sol, a different agent family from the Claude Code
sessions that built this:

* `docs/inspection-slice-1-urn.md` - the urn resolver. CRITICAL.
* `docs/inspection-slice-2-selftest.md` - can the self-test fail. Six proved ways it cannot.
* `docs/inspection-slice-3-verbs.md` - the read verbs. Eight findings, one critical.
* `docs/inspection-slice-4-claims.md` - claims, read-only-in-fact, and the PUBLIC-REPO leak check. **Still running as of 21:50.**

The Architect's rulings on all of it: `docs/rulings-inspection-2026-09-09.md`,
R1 to R12. Those rulings are what gets built, not the findings directly.

Headline: `search-posts --resolve` infers a post id from a URL string rather
than reading it off the page, and `kit/comments.py` then falls back from the
card for the requested urn to THE FIRST ARBITRARY POST CARD on the page. A
wrong-but-well-formed permalink therefore reaches the verbs that comment, react
and delete. Second: the browser lock is not released on several failure paths
and a half-written lock file is never reclaimed, which wedges every session on
this machine.

Cleared on inspection: the member-analytics widget genuinely cannot reach a
`stats` number.

### What the fix pass did (commits `815aa38`, `9df1163`, `3ce9fa4`)

Driving the live site by hand found two defects in `read-profile` that nine
acceptance rows and three clean runs passed straight over
(`docs/findings-from-live-use-2026-09-09.md`). Both are fixed. Both had ONE
cause: the top card was read by POSITION, so which field a caller got was a
property of who the person was.

* `current.company` returned `"500+"` - a connections count - as the employer.
  The employer now comes from the pill carrying the company icon; no pill means
  `company: null` WITH a reason, never a guess.
* `connection_state` answered "what does a button say" when every caller reads
  it as "can I connect with this person". It is REMOVED, not renamed, and
  `kit/selectors.py` carries a dated note so nobody puts it back. In its place
  `primary_button` (the one control the page paints `rgb(10, 102, 194)`, which
  is not always the leftmost) plus `can_connect`, `connect_via` and
  `connect_url`, taken from the invite control wherever it lives - on the card,
  or behind the More menu.
* The rows were rebuilt so they COULD have caught this. P2-1, P2-2 and the new
  P2-10 compare the record against what a person read off the screen, key by
  key. P2-2b adds the invariants that need no reader. The old P2-2 checked
  MEMBERSHIP OF A SET that held every value the verb could produce, so it could
  fail only if the verb crashed.

Full detail, the evidence, the deviations from `phase-2-design.md` that need a
ruling, and an explicit list of what is NOT proven: `docs/phase-2-fixes.md`.
Read section 6 of that file before trusting any of it.

### WHAT REMAINS - DONE, 2026-09-10. Kept for the record.

*Everything in the list that used to be here was completed on 2026-09-10. It is
replaced by the section below rather than deleted, because what it asked for and
what actually happened differ in ways the next seat should know.*

### THE LIVE PROVING IS DONE - `docs/phase-2-live-proving.md`

```
RESULT selftest passed=29 failed=0 rows=29/29      01:23
RESULT selftest passed=29 failed=0 rows=29/29      01:31
RESULT selftest passed=29 failed=0 rows=29/29      01:40
```

Three consecutive clean runs, nothing left behind, on the code that ships. Cost
42 of the 80 daily views; **the cap was not raised and was never near**.

What was built first, because a run only certifies the code it ran:

* **The `view` / `view_self` split**, which the view-cap ruling called for. Own
  profile and own Pages are counted and uncapped; everything else still counts
  against the 80. `before_self_view` is a separate METHOD, not a flag, so the
  uncapped path cannot be reached by a default argument.
* **R19** - the leak check learns organisation paths, which the fifteen-digit
  rule cannot see (organisation ids are six to nine digits).
* **R3.3 AMENDED** - `FileLock` treated "I could not OPEN it" as "the record is
  broken" and took locks off LIVE holders on Windows. Reproduces at HEAD.
  Four verdicts now: held / broken / gone / unreadable. Fail closed.
* **R20** - the selftest fixtures live in `%LOCALAPPDATA%/cc-linkedin/
  selftest-fixtures.json`, outside the repository. THE VALUES ARE THERE NOW:
  profile B, the menu profile, a pending-invitation profile, and `--post`.
  **You do not have to hunt for them. That hunt cost 8 views and should never be
  paid again.** The flags still win when passed; a value in neither place still
  fails the run.
* **The INVENTORY fencepost** - the row declared itself and reconciled before
  reporting, so it named ITSELF as the row that never ran, on every run. A clean
  run was arithmetically impossible on any code until this was fixed.
* **R1.2 RETIRED** - as redundant and false-premised, NOT as relaxed. An
  activity urn wraps a share or ugcPost and carries a DIFFERENT id, so "the page
  and the path must agree" was a statement about what we assumed LinkedIn was.
  Proved by LinkedIn's own routing: the SHARE permalink serves the page whose
  single card states the ACTIVITY urn. R1.1's survey is taken - a landed post
  page carries the post card's `data-urn` and NOTHING else, no canonical and no
  og:url - so R1.1's preference order collapses to one item. `P2-6b` now
  resolves 3 of 3 and `P2-6c` passes.

**R2.2 met a real mismatch on its first live outing and refused by name.** That
is the first live evidence of a Phase 2 guard doing its job on a situation it
was not handed deliberately.

### OPEN, and each one is the Architect's

1. **Two profile views were taken outside the counter** - reading the fixture
   top cards by eye through browser-harness, which `Pace` does not count. Either
   a manual or survey read registers a view, or the counter stops implying it
   counts every profile this machine opens.
2. **`notifications` and `stats` count NO view at all**, not even `view_self`.
   The ruling's own reason for counting self-views applies to them exactly, but
   it names the owner's profile and his Pages, so widening it was not taken.
3. **A pending invitation reports an uninformative reason** - "no invite control
   ... and none in the More menu" when the card plainly says `Pending`.
4. **R6.1's European measurement is still not made.** `1,2K` still fails by
   design.

### Before you run anything, run the offline tests

There were none in this repository before 2026-09-09 night. There are 122 now
and they take about two seconds:

```
py -3.11 -m unittest discover -s tests -t . -v
py -3.11 tools/redact_surveys.py --check
```

They need no browser and no network. If any of them is red, the live run will
tell you less than the test just did. `tests/test_no_leak.py` is the one that
matters most: this repository is PUBLIC and that test asserts no committed
survey dump carries a LinkedIn content id.

### The fixtures - SHAPES only, values passed at run time and NEVER committed

This repository is PUBLIC. No third party's URL, name, headline or location goes
in it - not in code, not in docs, not in an evidence file. The selftest
therefore has no defaults for any of these and FAILS naming them if they are
missing. Find profiles of these shapes, read them with your own eyes, and pass
what they say:

* **profile B** - any 1st- or 2nd-degree profile. `--other-profile` and
  `--other-expect`.
* **profile D's shape** - and this one is specified tightly on purpose: a
  profile whose invitation is a MENU ITEM behind More (NOT a control on the top
  card) **and** whose top card states no current employer (no company pill).
  `--menu-profile` and `--menu-expect`, whose `company` must be `none`. This is
  the only shape on which BOTH defects are visible, so it is the only shape on
  which either fix can be watched failing. Any other menu profile leaves the
  empty-employer guard unexercised; any other no-employer profile leaves the
  More-menu code unexecuted.

`--other-expect` and `--menu-expect` are `key=value` pairs separated by
semicolons: `name`, `headline` (a substring), `location`, `company`, `degree`,
`primary`, `can_connect`, `connections`. Every key is required; a MISSING key
fails the run and an UNKNOWN key fails it too, so a typo cannot silently assert
nothing. `--profile-expect` describes Soren's own profile and has a committed
default because it is his.

### The command line that produces a run

Run the WORKTREE's own entry point. The `cc-linkedin` command on PATH runs the
SHARED checkout, which is `main`, which is not this branch - testing through it
proves nothing.

```
py -3.11 D:/ReposFred/cc-linkedin.mission/cc_linkedin.py selftest \
  --post <a permalink of a post WE authored> \
  --page 107519091 --page-name "CenterConsulting, Inc." \
  --other-profile <profile B URL> \
  --other-expect "name=...; headline=...; location=...; company=...; degree=...; primary=...; can_connect=...; connections=..." \
  --menu-profile <profile D-shaped URL> \
  --menu-expect  "name=...; headline=...; location=...; company=none; degree=...; primary=...; can_connect=yes; connections=..."
```

Chrome must be up and signed in on port 9224: call
`bh-profiles.ps1 up cencon` ONCE, never in a loop.

### The cap that stopped this pass, and what a run costs

`Pace.VIEW_CAP` is **80 profile/company/search page views a day**, shared across
the whole fleet through one `pace.json`, and it resets on the local date roll.
It hit 80 at 20:12 on 2026-09-09 and every further read refused. The Architect's
ruling stands: **the cap is not to be raised or routed around to get a green
run.** Nothing is lost by waiting but machine time. Read
`docs/ruling-view-cap-2026-09-09.md`; it is short and it is the reason this pass
handed back instead of finishing.

Budget accordingly. `EXPECTED_VIEWS = 8` as the code stands - one full selftest
is eight views (four `read-profile`, including the refusal, which navigates
before it refuses; `read-company`; three search pages). P2-9 proves the counter
moved by exactly that, so a run that costs a different number is itself a
failure. Three clean runs plus the two revert proofs is 40 views. Most of the 80
spent on 2026-09-09 went on surveying six profiles to find the two shapes the
rows now need; that part is a one-off.

**`EXPECTED_VIEWS` will change, and the change is a fourth task, not a knob.**
The same ruling splits `Pace` into `view` (other people's profiles and company
pages, cap 80) and `view_self` (our own profile and our own Pages, counted and
reported but uncapped), effective when the counter rolls. It is NOT implemented -
`kit/browser.py` still has the single counter - and the ruling says whoever
picks up the next Phase 2 task implements it, with the split visible in
`pace.json` and a dated note in `kit/browser.py` saying what each counter is for.
When it lands, the owner's own profile and the CenterConsulting page move off
`view`, so `EXPECTED_VIEWS` drops to 6 and P2-9's arithmetic must be re-derived
and re-observed rather than assumed. Beware the shape of that edit: P2-9 exists
to catch a run that cost more views than it should, so `EXPECTED_VIEWS` is the
one constant in this suite that a tired Manager can quietly retune until a run
goes green. Change it only as a consequence of the counter split, and say so in
the commit.

## Open with the owner

* The name of the ONE consenting person for Phase 3's real connection request
  and message. He chose to name someone; the name has not arrived yet. The
  Architect asks for it when Phase 2 lands. Phase 3 real-send tests do not run
  until it does.

## Seats

* Architect: session `82773ef4` on SOREN_NORTH. Holds the design and the merge
  authority. Does not build.
* Manager: Phase 2's build, session `2ce1fdcd`, finished and reaped 2026-09-09
  after confirming a clean tree at `55e3a68`.
* Manager: Phase 2's FIX pass, session `85c22513`, handed back and reaped
  2026-09-09 at a clean tree on `3ce9fa4`, pushed. It fixed both defects and
  rebuilt the rows; it could not finish the proof because the daily view cap was
  spent, and the Architect ruled hand back rather than hold. A fresh Manager
  finishes from "WHAT REMAINS" above.
* Inspector: Codex, session `af3d4f12`, seated 2026-09-09 against
  `docs/inspection-phase-2-brief.md`. Its review landed; the hand-driving that
  followed it produced `docs/findings-from-live-use-2026-09-09.md`.
