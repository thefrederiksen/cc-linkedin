# Phase 2 follow-up: F1 to F4, done

The Manager's own account of the follow-up pass, 2026-09-10, on branch
`phase-2-follow-up` cut from `main` at `a7e4ae5`. Self-testimony: it was written
by the seat that did the work, about its own work, and section 7 is the part
worth reading first if you intend to trust any of it.

## 1. The headline

```
RESULT selftest passed=30 failed=0 rows=30/30      02:17
RESULT selftest passed=30 failed=0 rows=30/30      02:26
RESULT selftest passed=30 failed=0 rows=30/30      02:35
```

Three consecutive clean runs on the code that ships, taken LAST - after every
change that touches behaviour, so they certify the build in the commit and not
an earlier one. 30 rows now, one more than Phase 2 landed with: P2-11 is new.

201 offline tests, up from 160. They need no browser and no network and take
about eight seconds. Every new guard was watched failing before it was trusted.

**Cost: 19 views of the safety cap's 80** - one survey to measure F3, plus six
per run. The counter went 42 to 61 and **the cap was neither raised nor reached**,
with nineteen left. `docs/ruling-view-cap-2026-09-09.md` did not have to be
argued with, which is the point of it.

## 2. F1 - the view counter had a path it could not see

**This is the one with safety weight, and it was found by the previous Manager
about its own work.**

`tools/survey.py` drives `kit/browser.Browser`. Same lock, same background tab,
a real profile opened in the real signed-in browser against the owner's account.
From LinkedIn's side it is indistinguishable from `read-profile`. It registered
nothing at all, so on 2026-09-09 two profile views went through it unrecorded
while `pace.json` sat at eighty - and the Architect had read a profile the same
way the night before. Neither noticed.

**Both halves of the ruling are built.**

*The tool counts.* `survey()` registers its view before it navigates, on the
counter the surface belongs to, and refuses over the cap without opening
anything. The RESULT line says which counter it was charged to. The branch is
written out at the call site rather than hidden in a helper, and it is now the
third copy of the same four lines - deliberately, because `before_self_view` is
the uncapped path and reaching it has to be a positive act somebody can read,
never something a wrapper does on a caller's behalf.

*The classifier.* `kit/browser.surface_kind(url)` answers `view_self` only on a
positive match against the owner's own lists - his profile slug, his Page id and
slug, his notifications page. Everything else is capped, **including everything
it does not recognise**, an empty string and `None`. It is an enumeration, and
an enumeration always loses to the form it has not met (R17); here that loss is
harmless in the only direction that matters, because a new own-surface it has
never heard of gets charged to the cap rather than exempted from it. It reads
the whole slug, not a substring: `/in/sorenfrederiksen2` is somebody else.

*The docstring stops overselling.* `Pace` now says, first thing, what it counts:
**views taken through this toolkit**. Not views taken on this machine, and not
views taken against the owner's account. Under IT DOES NOT GUARANTEE there is a
new entry saying that a profile opened by an agent hand-driving a browser -
browser-harness, Playwright by hand, a person clicking in Chrome - never enters
this code and appears nowhere, while costing the account exactly the same; that
the number in `pace.json` is therefore a FLOOR under the day's real total; and
that it happened twice on 2026-09-09, to two people who were both being careful.

*The two documents an agent actually reads.* The same warning is in `README.md`
and in `.claude/skills/linkedin/SKILL.md`, in the same words, with the same
instruction: use `read-profile` for a profile and `tools/survey.py` for raw DOM,
because both register - and if you open one by hand anyway, say so out loud,
because the counter is now short by that many. Whoever is about to hand-drive a
browser reads one of those three surfaces and not the other two, which is why
the sentence is in all three and why a test asserts it is.

**Watched failing:** `docs/evidence/watched-failing-view-registry.txt`. Seventeen
tests against `a7e4ae5`; six failures and eleven errors. The two that matter are
that the survey tool opened a stranger's profile with the registry empty, and
that it did so **even at the cap**.

**Proved live, on its first outing:** the F3 measurement below was taken through
`tools/survey.py`, and the capped counter went 42 to 43 for it.

## 3. F2 - notifications and stats counted nothing at all

Both open a page in the signed-in browser and neither registered a view, not
even `view_self`. They are our own screens, so they are correctly outside the
safety cap - but the whole point of the `view_self` track is that `pace.json`
shows everything this toolkit opened, and a surface that appears nowhere cannot
be reconciled against a run's own registry.

Both register now. `notifications` unconditionally, because its URL is a
constant and it is ours. `stats` only where `--page` is positively one of the
owner's Pages, and on the capped counter otherwise - because `--page` is an
argument, and the uncapped counter must not be reachable by naming a Page. That
is `read_company`'s existing answer to the same problem, applied again rather
than reinvented.

Each run now shows five own-surface views instead of three, and spends no more
of the safety number than before.

**Watched failing:** `docs/evidence/watched-failing-own-surface-views.txt`. The
ninth test in that file passed before the fix and is meant to - it asserts the
self counter is uncapped, which is the property that makes putting these two
verbs on it safe.

## 4. F3 - a pending invitation now says so

**Measured, not reasoned about.** One capped view through `tools/survey.py`
against the profile the Architect sent a real invitation to on 2026-09-09. The
control is an anchor in the top card's action row, between Message and More:

```
    A   text "Message"   aria ""                                        filled
    A   text "Pending"   aria "Pending, click to withdraw invitation sent to <name>"
                         href <the profile's own URL>   disabled=false
    B   text "More"      aria ""
```

Two things fell out of the measurement that reasoning would have got wrong.
There is **no withdraw endpoint** anywhere on the card - the href is the
profile's own URL - so this tells Phase 3 that there is something to withdraw
and nothing about how. And the pending control is **not** the filled one;
Message is.

`read-profile` now answers from the card:

```
can_connect        : False
invitation_pending : True
connect_via        : None
connect_url        : None
can_connect_reason :
  an invitation to <name> is already PENDING - the top card carries the
  control labelled 'Pending, click to withdraw invitation sent to <name>',
  which is LinkedIn saying an invitation has been sent and not yet answered.
  Sending another is not possible until this one is withdrawn or expires.
```

It is matched on the **label** and never on the bare word "Pending" - the same
rule `_invite` applies to the bare word "Connect", and chosen the same way:
precision over recall, because a false positive tells Phase 3's `withdraw` there
is an invitation to take back when there is not, while a false negative gives
back the true-but-uninformative answer we started from.

The check also happens **before** the More menu is opened, so a pending profile
no longer costs a click, a settle loop and several seconds to arrive at a worse
sentence than the card was already showing.

`invitation_pending` is a boolean on every profile, and `_profile_holds` now
asserts on every profile row that it is one and that a true value never comes
with an invitation attached.

**New live row P2-11**, on the pending fixture, with `--pending-profile` to
supply it. It asserts thirty checks and it is the only thing in this repository
that would notice LinkedIn changing that label: without it, such a change turns
`invitation_pending` quietly false everywhere and no row goes red.

**Watched failing:** `docs/evidence/watched-failing-pending-invitation.txt`.
Fifteen errors, and one of them is the old behaviour caught in the act - handed
the measured card with no browser at all, the old `_connect` reached past the
Pending control for the browser rather than reading what was in front of it.

## 5. F4 - nothing built, and that is the answer

`1,2K` still fails. R6.1's European measurement is still not made - nothing in
this pass ran in another locale - so the form still refuses rather than
resolving to 1200 or 12, which is R6.3's default and the only safe direction.

One repair, and it is to the check rather than the code.
`test_a_failure_names_what_it_read` asserted only that `to_int` exits. The
message could have said nothing about what it read and the test would still have
passed **under that name**. It reads the message now: the value, the field, and
the rule that was broken. Watched going red with the message weakened and green
again with it restored -
`docs/evidence/watched-failing-european-number.txt`.

## 6. What one run costs, now

Six against the safety cap - profile B, the menu profile, the pending profile,
one people search, two content searches - and five on the uncapped own-surface
counter: the owner's profile twice (P2-1, and the P2-3 refusal, which navigates
before it refuses), his Page, his notifications, his Page's analytics. Eleven in
all, and P2-9 reconciled the pacing file against the run's own registry on all
three runs: `views 6 capped + 5 own, lock released=True, dialogs=0, tabs 3->3`.

There is still deliberately no constant to check that against. The number above
is a fact about the rows, written in `kit/selftest.py`'s docstring; the row
compares two independent records of the same run.

## 7. WHAT IS NOT PROVEN

**F3 was measured on ONE profile.** A Pending control rendered without that
label - another locale, another layout, a rendering we have not met - is not
detected, and `invitation_pending` is then false on a profile where an
invitation really is outstanding. This is said in `_pending`'s docstring as
well, because it is the failure mode somebody will meet before they read this
file.

**`invitation_pending: false` is narrower than it sounds.** It means this run
read the card - and the More menu, where it got that far - and saw no pending
control. It is not a promise that no invitation is outstanding. The README and
the skill both say so; no test can prove it, because the claim is about what
LinkedIn might do rather than about this code.

**The More-menu half of F3 is unmeasured.** `_pending` is applied to the menu
items as well as the card, because the menu is the other place an invite control
lives. No pending control was ever measured there. It can only fire on the exact
string that was measured, so it cannot invent a state - but it has never
executed, and a path that has never executed is not covered by three green runs.

**F1 cannot defend against a caller that routes around it.** There is no such
defence and there is not meant to be one: `Browser` opens any URL it is given.
What F1 changes is that the obvious way is now the counted way, and that the
docstring no longer implies the other ways are counted. An agent that opens a
profile with browser-harness still spends a real view invisibly. The only
mitigation is the sentence now sitting in three places telling it not to.

**`surface_kind` is an enumeration of three path shapes.** A fourth own-surface
- a newsletter, a group the owner owns, a showcase page - is charged to the
safety cap. That is the safe direction and it is not the right answer; it will
spend the budget faster than it needs to.

**The three clean runs are three runs.** On this machine, with these fixtures,
against LinkedIn as it rendered tonight. They say nothing about another profile
shape, another locale, or next week.

**R6.1 is still unmeasured**, R5's menu scoping still has no offline test, and
P2-7 is still a smoke test that says so on every run. Unchanged from
`docs/phase-2-live-proving.md` section 7.

**Nothing outbound left this machine beyond the selftest's own footprint.** Each
run comments and replies on one of Soren's own posts, reacts and unreacts,
deletes all of it, then publishes and deletes a throwaway post on the Page - and
P1-nothing-left proves the post is clean afterwards. No connection request, no
message, no comment on anybody else's post. The pending invitation this pass
reads was sent on 2026-09-09, by the Architect, at the owner's instruction; this
pass did not send, withdraw or touch it.

## 8. Where to look

* `kit/browser.py` - `surface_kind`, and `Pace`'s docstring: what it counts,
  and the entry saying what it cannot see.
* `tools/survey.py` - a survey is a view, at the top of the file and at the
  point it navigates.
* `kit/people.py` - `_pending`, and `_connect`'s five values.
* `kit/selectors.py` - `INVITE_PENDING_ARIA`, with the measurement beside it.
* `kit/selftest.py` - P2-11, and what a run costs.
* `docs/evidence/watched-failing-view-registry.txt`
* `docs/evidence/watched-failing-own-surface-views.txt`
* `docs/evidence/watched-failing-pending-invitation.txt` - and the measurement.
* `docs/evidence/watched-failing-european-number.txt`
* `docs/evidence/three-clean-runs-2026-09-10-follow-up.txt`

## 9. Nothing was asked of the Architect

Every one of the four rulings held against the world as measured. F3's
measurement agreed with what the ruling assumed; nothing here contradicts a
ruling, and there is no question waiting.

Two things are the Architect's to do, neither of them a decision:
`docs/STATE.md` still says this work is IN PROGRESS - it is the Architect's file
and this seat did not edit it - and the branch is pushed but not landed, because
only the Architect puts anything on `main`.
