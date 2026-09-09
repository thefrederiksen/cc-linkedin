# Mission state - the compact handoff

Kept current by the Architect. A fresh Manager needs THIS file, `MISSION.md`,
`phase-2-design.md`, and `cc-devthrottle workflow instructions mission`. Nothing
else. Not a transcript, not a history.

Last updated: 2026-09-09, 18:15, by the Manager (Phase 2 built and proven).

## Where the work is

* Worktree: `D:/ReposFred/cc-linkedin.mission`, branch `phase-2-reading`, cut
  from `origin/main` at `a2ea069`.
* The shared checkout `D:/ReposFred/cc-linkedin` is `main` and belongs to
  everybody. Never build there. The `cc-linkedin` command on PATH runs the
  SHARED checkout, so it tests `main`, not this branch.
* On main already: Phase 0 (posting, scheduling), Phase 1 (comments, replies,
  reactions, deletes, selftest).

## Phase 2 - BUILT AND PROVEN, awaiting inspection

Verbs: `read-profile`, `read-company`, `search-people`, `search-posts`,
`notifications`, `stats`. Design settled in `docs/phase-2-design.md`.

Order: survey (`tools/survey.py`, dumps committed under `docs/surveys/`) ->
`kit/people.py`, `kit/search.py`, `kit/account.py` -> the `Pace` view track ->
the six subcommands -> the Phase 2 selftest block -> three consecutive clean
live runs -> Codex inspection -> one pull request to main.

Acceptance rows P2-1 to P2-9 are in the design document. Done is all nine
passing three times in a row on the live page with nothing left behind.

| | |
|---|---|
| Survey | done - `tools/survey.py`, eight dumps in `docs/surveys/`, redacted |
| Modules | done - `kit/people.py`, `kit/search.py`, `kit/account.py` |
| Selftest block | done - nine rows, `--other-profile` required, nothing skippable |
| Three clean runs | 3 of 3, all `passed=23 failed=0`, nothing left behind |
| Codex inspection | NOT CALLED - this is the Architect's next move |
| Pull request | not opened - the Architect lands it |

Two mid-build rulings were needed and are in `docs/rulings-phase-2.md`; they
amend the design and win where the two disagree. The Manager's full account,
including what is NOT proven, is `docs/phase-2-report.md` - the Inspector should
read that as self-testimony and try to break it, not take it on trust.

## Open with the owner

* The name of the ONE consenting person for Phase 3's real connection request
  and message. He chose to name someone; the name has not arrived yet. The
  Architect asks for it when Phase 2 lands. Phase 3 real-send tests do not run
  until it does.

## Seats

* Architect: session `82773ef4` on SOREN_NORTH. Holds the design and the merge
  authority. Does not build.
* Manager: session `2ce1fdcd` "cc-linkedin - Manager - Phase 2, reading
  and search", seated 2026-09-09 21:20. Killed when Phase 2 ends.
* Inspector: Codex, seated per inspection, gone when its written review lands.
