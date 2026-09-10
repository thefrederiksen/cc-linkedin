# Mission state - the compact handoff

Kept current by the Architect. A fresh Manager needs THIS file, `MISSION.md`,
`phase-2-design.md`, and `cc-devthrottle workflow instructions mission`. Nothing
else. Not a transcript, not a history. For the Phase 2 FIX pass, add
`docs/findings-from-live-use-2026-09-09.md` and `docs/phase-2-fixes.md`.

Last updated: 2026-09-09, 20:30, by the Manager of the Phase 2 fix pass
(both defects fixed and pushed; verification blocked on the daily view cap).

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
| Independent inspection | **NEVER HAPPENED - see below. Do not record it as done.** |
| Hand-driving the live site | done by the Architect; it found what the suite could not |
| Phase 2 fix pass | **code done and pushed; proof unfinished - THIS is the open work** |
| Pull request | not opened - the Architect lands it |

### The independent inspection has NOT been done

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

### WHAT REMAINS - a fresh Manager can finish this from cold

Nothing of the fix is left to build. Four things, in this order:

1. **Watch revert 2 fail.** In `kit/people.py`, put the OLD positional employer
   read back - the headline and employer as the first and second surviving
   visible paragraph of the whole top card - run the suite against the
   `--menu-profile` fixture, and confirm `current.company` comes back as the
   bare connections count (the symptom is a value like `'205'`) and that
   P2-10 and P2-2b go RED on `current.company is not a count` and on the
   `company=none` correspondence. Then `git checkout -- kit/people.py` and
   confirm the tree is clean. Revert 1 has already been watched failing with
   its exact symptom; `docs/phase-2-fixes.md` section 5 records what was seen
   and is the model for writing this one up.
2. **Re-observe revert 1's search controls.** That run crossed the view cap
   mid-way, so P2-5, P2-6 and P2-9 failed on the cap rather than staying green.
   The P2-10 half of the proof stands; this half does not.
3. **Three consecutive clean runs**, `passed=25 failed=0`, nothing left behind.
   One such run of the final build exists (ended 20:05, 2026-09-09); it does not
   count towards the three unless the Architect says so.
4. **Implement the `view` / `view_self` split** that
   `docs/ruling-view-cap-2026-09-09.md` calls for, since that ruling hands it to
   whoever picks up the next Phase 2 task. Do it BEFORE the three clean runs, so
   the runs that count are runs of the code that ships - and see the note on
   `EXPECTED_VIEWS` at the end of this section before touching that constant.

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
