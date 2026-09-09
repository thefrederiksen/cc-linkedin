# Mission state - the compact handoff

Kept current by the Architect. A fresh Manager needs THIS file, `MISSION.md`,
`phase-2-design.md`, and `cc-devthrottle workflow instructions mission`. Nothing
else. Not a transcript, not a history.

Last updated: 2026-09-09, 21:10, by the Architect.

## Where the work is

* Worktree: `D:/ReposFred/cc-linkedin.mission`, branch `phase-2-reading`, cut
  from `origin/main` at `a2ea069`.
* The shared checkout `D:/ReposFred/cc-linkedin` is `main` and belongs to
  everybody. Never build there. The `cc-linkedin` command on PATH runs the
  SHARED checkout, so it tests `main`, not this branch.
* On main already: Phase 0 (posting, scheduling), Phase 1 (comments, replies,
  reactions, deletes, selftest).

## Phase 2 - IN BUILD

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
| Survey | not started |
| Modules | not started |
| Selftest block | not started |
| Three clean runs | 0 of 3 |
| Codex inspection | not called |
| Pull request | not opened |

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
