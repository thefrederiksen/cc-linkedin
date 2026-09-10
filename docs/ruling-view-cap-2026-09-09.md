# Ruling: what the view cap is for, and what it counts

The Architect's, 2026-09-09, 20:30, made while the fix Manager sits blocked by
this very cap. That timing is why the second half of this ruling exists.

## The decision that was in front of me

The Phase 2 fix pass reached 80 profile views at 20:12 and stopped, with one
revert still to watch and two of three clean runs still to do. Three options:
raise the cap to finish tonight, hold until the counter rolls at local midnight,
or hand back.

**Held. The cap was not raised, and no run tonight got a single view beyond it.**

A daily cap that is raised whenever it blocks something is not a cap, it is a
speed bump with a note attached. `MISSION.md` puts "anything that treats a cap
as a target" out of scope, and a cap raised to turn a run green is worse than
that: it spends the owner's account safety to buy a green line in a report
nobody was waiting for. The cost of holding was a few hours of machine time on
work with no deadline. That is not a close call and it should not be argued
again.

## The ruling, effective TOMORROW and not tonight

**Views of surfaces we own do not count against the safety cap.** Specifically:
Soren's own profile, and a company page he administers.

The cap exists for one measured reason, written in `MISSION.md`: high-volume
viewing of OTHER PEOPLE'S profiles is one of the top triggers for an account
warning, because it is what scraping looks like from the outside. Loading your
own profile is not that. It notifies nobody, it appears in nobody's "who viewed
your profile", and no amount of it makes an account look like a scraper.

So `Pace` gets two counters:

* `view` - other people's profiles and company pages. **Cap 80 a day.** This is
  the safety number and it is the one the owner agreed to.
* `view_self` - our own profile and our own Pages. **Counted and reported, not
  capped.** Counted because a runaway loop should still be visible in
  `pace.json`; uncapped because there is nothing to protect against.

The selftest reads Soren's profile, the CenterConsulting page, two other-person
profiles and some search pages. Under this ruling its cost against the safety
number roughly halves, which is the practical reason the friction kept recurring
during a fix pass that never went near a stranger's profile in anger.

## The part that matters more than the ruling

**This ruling does not apply to today's counter and must not be used to unblock
tonight.** Today's 80 were counted under the rules as they stood when they were
spent. Re-scoring them under a rule written three hours later, by the person the
rule unblocks, is how a safety limit quietly stops being one - and it would be a
far worse precedent than any amount of waiting.

A rule may be changed because it is wrong. It may not be changed because it is
in the way. The test I applied: **would I still make this ruling tomorrow
morning, with nothing blocked?** Yes - a self-view has never been what the cap
was protecting against, and it was miscounted from the day it was written. So
the ruling stands on its own merits, and it takes effect when the counter rolls,
along with everything else.

Implemented by whoever picks up the next Phase 2 task, with the split visible in
`pace.json` and a dated note in `kit/browser.py` explaining what each counter is
for. Until then the single `view` counter and its cap of 80 stay exactly as they
are.
