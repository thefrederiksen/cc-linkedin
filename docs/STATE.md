# Mission state - the compact handoff

Kept current by the Architect. A fresh seat needs THIS file, `MISSION.md`, the
design document for its phase, and
`cc-devthrottle workflow instructions mission`. Nothing else. Not a transcript.

Last updated: 2026-09-10, 03:20, by the Architect, at the end of an overnight run.

## Where the work is

* `main` is at `7374a5f`. Phases 0, 1 and 2 are all ON MAIN and working.
* Worktree `D:/ReposFred/cc-linkedin.mission`, branch `phase-2-follow-up`, cut
  from main. The shared checkout `D:/ReposFred/cc-linkedin` is main and belongs
  to everybody - never build there.
* **The `cc-linkedin` on PATH runs the SHARED checkout.** Now that Phase 2 has
  landed it will look right while still not being your branch. Always run
  `py -3.11 <worktree>/cc_linkedin.py`.

## Done and on main

* **Phase 0** - `post` (text, video, up to 20 images, now or scheduled),
  `scheduled`, `unschedule`. In daily use by the video pipeline.
* **Phase 1** - `read-post`, `read-comments`, `comment`, `reply`, `react`,
  `unreact`, `delete-comment`, `delete-post`.
* **Phase 2** - `read-profile`, `read-company`, `search-people`, `search-posts`,
  `notifications`, `stats`. Merged 2026-09-10 as a SQUASH, deliberately: the
  branch's intermediate commits carried third-party identifiers before they were
  redacted, and squashing keeps those off main's history.
  * Three consecutive clean live runs, `passed=29 failed=0 rows=29/29`.
  * 160 offline tests. Every guard watched failing before it was trusted.
  * Four adversarial inspection passes by Codex, a different agent family.

## IN PROGRESS

**Nothing.** No branch, no worktree, no seated Manager. Four pull requests landed
overnight (#3 to #6) and every one is squashed onto `main`.

* **#3** Phase 2, the six read verbs.
* **#4** the Phase 2 follow-up: the uncounted view path, `view_self`, a pending
  invitation that says so.
* **#5** the Phase 3 survey - and a leak form that was LIVE ON MAIN: real profile
  slugs inside `vanityName=` invite hrefs. Fixed, and the guard now imports the
  redactor's own form lists so the two cannot drift apart again.
* **#6** the Phase 3 design amended with what the survey measured. It was wrong
  six times and the document says so rather than being quietly corrected.

## NEXT: Phase 3

Designed in full at `docs/phase-3-design.md`, not built. `connect`, `withdraw`,
`message`, `read-inbox`, `read-thread`, `invitations`, `follow`/`unfollow`,
`invite-to-follow`. Staged by default; `--submit` sends.

**Its three rules, before anything else is read:** a staged action must PROVE
the pre-action state survived; the message composer must NEVER press Enter,
because Enter sends and the shared `type_text` presses one per newline; and an
irreversible act names its target twice.

**Ready to build.** The surfaces are surveyed (`docs/phase-3-survey.md`, 13
dumps) and the design is amended to match (`docs/phase-3-amendments.md`, read it
BEFORE the design). Build against the amendments.

**Blocked, and only this part:** five acceptance rows need a consenting person
for one real connection request and one real message. The owner redirected this
to real prospects rather than a colleague, which is fine for the SEND rows and
NOT fine for two of them - one withdraws a minute later, costing that person
three weeks before they can be invited again, and one deliberately sends a
broken half-message to prove the Enter guard fires. Those two need somebody who
does not mind. Everything staged builds and proves without it.

## Open with the owner

1. **Whether to actively scrub the already-public commits.** Phase 2's branch
   carried third-party identifiers before redaction and was pushed to a public
   repository. The squash keeps them off main and the branch is deleted, so they
   are unreachable - but unreachable is not gone, and the complete remedy needs
   GitHub support. Recommendation and honest limits in R14.
2. **Who the two rude Phase 3 rows may be run against** (see above).

## Things that will bite the next seat

* **Fixtures live on the machine, not in git** (R20):
  `%LOCALAPPDATA%/cc-linkedin/selftest-fixtures.json` holds profile B, a menu
  profile, a pending-invitation profile and `--post`. A FRESH MACHINE HAS NONE
  and the run will fail naming both routes. That is intended, not a regression.
* **The daily view cap is 80 and is never raised.** It was hit once and the
  answer was to wait, not to raise it (`docs/ruling-view-cap-2026-09-09.md`).
* **Views of our own surfaces are `view_self` and uncapped**; everything else
  counts against the 80.
* **`session spawn --agent Codex` is broken from the Architect's session**
  (devthrottle#2802). Codex inspections are run as `codex exec` instead, in the
  background, under a narrow exception the owner granted when asked - for
  producing a WRITTEN REVIEW and nothing else.
* **Four defects in two days were instruments that could not fail**: a redactor
  that knew eight identifier forms, a leak test that reintroduced the leak it
  guarded, a lock that read "I could not look" as "nothing is there", and an
  inventory row that named itself as never having run. When a check passes,
  ask what it would take to make it fail.
