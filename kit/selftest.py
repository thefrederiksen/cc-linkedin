# -*- coding: utf-8 -*-
"""The selftest: every verb, on things we own, leaving nothing behind.

    cc-linkedin selftest --post <a permalink of ours> --page ID --page-name NAME
                         --other-profile <a 1st- or 2nd-degree /in/ URL>
                         --other-expect  "name=...; headline=...; location=...; company=...;
                                          degree=...; primary=...; can_connect=...;
                                          connections=..."
                         --menu-profile  <a profile whose invitation is behind More and
                                          whose top card states no employer>
                         --menu-expect   "...; company=none; ..."
                         --pending-profile <a profile with an invitation of ours
                                          already outstanding>

TWO BLOCKS, and the run does BOTH. Phase 1 writes: on a post of ours it
comments, replies, reacts, unreacts and deletes everything it made, and on the
Page it publishes a throwaway post and deletes it. Phase 2 only reads: a
profile, a second person's profile, a refusal, a company page, two searches,
the notifications page and the Page's analytics.

WHAT ONE RUN COSTS, as of 2026-09-10. SIX against the safety cap - profile B,
the menu profile, the pending profile, one people search and two content
searches - and FIVE on the uncapped own-surface counter: the owner's profile
twice (P2-1, and the P2-3 refusal, which navigates before it refuses), his Page,
his notifications and his Page's analytics. The last two only started counting
with F2.

That eleven is a fact about the rows, not something this suite asserts. There is
deliberately no constant to compare it against: P2-9 reconciles the pacing file's
movement against the run's own registry of what it opened, because a hand-set
number is the one thing in here a tired Manager can retune until a run goes
green.

NOTHING IS SKIPPED. A fixture that is missing fails the run and says which one.
A verb quietly skipped is how a suite goes green over code that never ran, and
this file exists precisely to stop that - so there is deliberately no flag here
that runs "just the fast half".

THE FIXTURES WITH NO DEFAULT ARE THE ONES ABOUT OTHER PEOPLE, and that is on
purpose. This repository is PUBLIC, so a second person's profile URL and details
are never committed - not in the code, not in the docs, not in an evidence file.
They are passed at run time and the evidence calls those people "profile B" and
"the menu profile".

There are two such profiles, each with its own expectation, rather than the one
this suite had, because of what went wrong on 2026-09-09. Two
defects in read-profile survived three clean runs of this suite: it reported a
connections count as somebody's employer, and it reported a connection state
that could not be acted on. Neither run was faked. The rows simply did not look:
of the eleven fields read-profile returns, P2-2 asserted four, and the one it
asserted about the connection asked only whether the value was a member of a set
that contained every value the verb could produce. So now:

  * --other-expect makes a person state what the page says, and the row compares
    the record to that statement, field by field. Correspondence, not membership.
  * --menu-profile forces the run through the More menu, where an invitation
    lives on some profiles and not others, and onto a top card that states no
    employer, which is the field that used to fill itself with a count. Both
    defects are visible on that one shape and on no other, so without it neither
    fix can be watched failing - a path that never executes is not covered by a
    green suite, however green.
  * --pending-profile (F3, 2026-09-10) is a profile with an invitation of ours
    already outstanding. It is the only fixture that reaches that state and the
    only one nobody can fabricate: an invitation has to have been sent to a real
    person. Row P2-11 is also what makes a change in LinkedIn's own Pending
    label LOUD - without it, that change turns invitation_pending quietly false
    everywhere and no row goes red.

On Soren's own profile there is no invite control, no degree badge and no
Message button, so without profile B half the record is never exercised at all.
"""
import argparse
import io
import json
import os
import re
import sys
import tempfile
import time
from contextlib import redirect_stdout

from . import comments as C
from . import selectors as S
from .browser import Pace

SOREN = "https://www.linkedin.com/in/sorenfrederiksen/"

# WHAT THE READER MUST SAY THE PAGE SAYS -------------------------- 2026-09-09
#
# Rows P2-1 and P2-2 compare read-profile's record against a description of the
# profile that a person read off the screen. That is the whole point of them,
# and it is what the rows they replace did not do.
#
# The rows they replace asserted `connection_state in {Connect, Pending,
# Message, Follow}` and `degree in {...} and not self`, and nothing else on that
# profile. Both are checks for MEMBERSHIP OF A SET. "Message" is in the set, so
# the row passed on a profile where the answer was wrong; every value the verb
# could possibly produce was in the set, so the row could only ever fail if the
# verb crashed. A check that cannot distinguish a right answer from a wrong one
# is not a check, and two defects rode through three clean runs behind these
# two.
#
# So the expectation is stated as data, one key per field, and every key is
# REQUIRED - a missing key fails the run and an unknown key fails it too,
# because a mistyped key would otherwise silently assert nothing at all.
EXPECT_KEYS = ("name", "headline", "location", "company", "degree", "primary",
               "can_connect", "connections")
EXPECT_SYNTAX = ("key=value pairs separated by semicolons, every key required: "
                 + "; ".join("%s=..." % k for k in EXPECT_KEYS)
                 + ". 'headline' is a substring that must appear in the headline; the rest are "
                   "exact. 'company' and 'connections' take the word none when the top card "
                   "states neither; 'can_connect' is yes, no, or none (none only on our own "
                   "profile).")
SOREN_EXPECT = ("name=Soren Frederiksen; headline=mindzie; "
                "location=Toronto, Ontario, Canada; company=mindzie; degree=self; "
                "primary=Open to; can_connect=none; connections=500")


def _expect(spec, flag):
    """Parse one --*-expect string. A missing key, an unknown key or an
    unreadable value FAILS the run - never a key quietly skipped."""
    got = {}
    for part in (spec or "").split(";"):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            print("FAIL %s: %r is not key=value. %s" % (flag, part[:40], EXPECT_SYNTAX), flush=True)
            sys.exit(1)
        k, v = part.split("=", 1)
        got[k.strip().lower()] = v.strip()
    missing = [k for k in EXPECT_KEYS if k not in got]
    unknown = [k for k in got if k not in EXPECT_KEYS]
    if missing or unknown:
        print("FAIL %s: missing %s%s. %s"
              % (flag, ", ".join(missing) or "nothing",
                 (" and does not know " + ", ".join(unknown)) if unknown else "",
                 EXPECT_SYNTAX), flush=True)
        sys.exit(1)
    # RULING R8. An empty value is a supplied key that asserts nothing. The
    # inspection proved it on `headline=`: the comparison is a substring test,
    # and "" is in every string, so the row reported its headline sub-check
    # passed for any wrong headline at all. The whole point of these rows is that
    # a person looked at the screen and wrote down what it said; an empty value
    # means they did not, and the row must say so rather than quietly agreeing
    # with itself. Unknown keys already failed; empty ones fail the same way.
    empty = [k for k in EXPECT_KEYS if not got[k]]
    if empty:
        print("FAIL %s: %s given with no value. An empty expectation asserts nothing - "
              "%s would have compared the record against the empty string and passed on "
              "anything. Write down what the page actually says, or say none where the "
              "syntax allows it. %s"
              % (flag, ", ".join("%s=" % k for k in empty),
                 "the headline check" if "headline" in empty else "that comparison",
                 EXPECT_SYNTAX), flush=True)
        sys.exit(1)
    if got["can_connect"].lower() not in ("yes", "no", "none"):
        print("FAIL %s: can_connect reads %r; it is yes, no, or none."
              % (flag, got["can_connect"]), flush=True)
        sys.exit(1)
    if got["connections"].lower() != "none":
        try:
            int(got["connections"].replace(",", "").rstrip("+"))
        except ValueError:
            print("FAIL %s: connections reads %r; it is a whole number, or the word none."
                  % (flag, got["connections"]), flush=True)
            sys.exit(1)
    return got


def _count_shaped(v):
    """True when this string is a count and nothing else. A value that answers
    true here has no business in a name, a headline, a location or an employer -
    that is precisely how the connections count "500+" came to be reported as
    somebody's company."""
    return bool(v) and bool(S.BARE_COUNT.match(v) or S.COUNT_LINE.match(v))


def _profile_says(r, exp):
    """Field by field, does the record say what the reader says the page says?"""
    cur = r.get("current") or {}
    want_company = None if exp["company"].lower() == "none" else exp["company"]
    want_cc = {"yes": True, "no": False, "none": None}[exp["can_connect"].lower()]
    want_conn = (None if exp["connections"].lower() == "none"
                 else int(exp["connections"].replace(",", "").rstrip("+")))
    head = r.get("headline") or ""
    return [
        ("name", r.get("name") == exp["name"], "%r wanted %r" % (r.get("name"), exp["name"])),
        ("headline", exp["headline"].lower() in head.lower(),
         "%r must contain %r" % (head[:60], exp["headline"])),
        ("location", r.get("location") == exp["location"],
         "%r wanted %r" % (r.get("location"), exp["location"])),
        ("current.company", cur.get("company") == want_company,
         "%r wanted %r" % (cur.get("company"), want_company)),
        ("degree", r.get("degree") == exp["degree"],
         "%r wanted %r" % (r.get("degree"), exp["degree"])),
        ("primary_button", r.get("primary_button") == exp["primary"],
         "%r wanted %r" % (r.get("primary_button"), exp["primary"])),
        ("can_connect", r.get("can_connect") is want_cc,
         "%r wanted %r" % (r.get("can_connect"), want_cc)),
        ("connections", r.get("connections") == want_conn,
         "%r wanted %r" % (r.get("connections"), want_conn)),
    ]


def _profile_holds(r, slug):
    """The invariants that need nobody to have read the page: every remaining
    field is present and the right shape, no count has landed in a field meant
    for words, and the three fields that describe the connection agree with each
    other."""
    cur = r.get("current") or {}
    url = r.get("url") or ""
    acts = r.get("actions")
    cc, via, curl = r.get("can_connect"), r.get("connect_via"), r.get("connect_url")
    out = [
        ("kind", r.get("kind") == "profile", repr(r.get("kind"))),
        ("slug", (r.get("slug") or "").lower() == slug.lower(),
         "%r wanted %r" % (r.get("slug"), slug)),
        ("url", slug.lower() in url.lower() and "?" not in url, repr(url)),
        ("rendering", r.get("rendering") == "react", repr(r.get("rendering"))),
        ("about", r.get("about") is None or (isinstance(r.get("about"), str)
                                             and r["about"].strip() != ""),
         "%r" % ((r.get("about") or "")[:40],)),
        ("actions", isinstance(acts, list) and len(acts) >= 1
         and all(isinstance(x, str) and x for x in acts), repr(acts)),
        ("primary_button is one of actions", r.get("primary_button") in (acts or []),
         "%r not in %r" % (r.get("primary_button"), acts)),
        ("degree", r.get("degree") in S.DEGREES,
         "%r not one of %r" % (r.get("degree"), S.DEGREES)),
        ("degree_reason", (r.get("degree") is None) == bool(r.get("degree_reason")),
         "degree=%r reason=%r" % (r.get("degree"), r.get("degree_reason"))),
        ("current.title", cur.get("title") is None and bool(cur.get("title_source")),
         "title=%r source=%r" % (cur.get("title"), (cur.get("title_source") or "")[:30])),
        ("an empty company says why", cur.get("company") is not None
         or bool(cur.get("company_reason")),
         "company=%r reason=%r" % (cur.get("company"), (cur.get("company_reason") or "")[:40])),
        ("can_connect_reason", bool(r.get("can_connect_reason")),
         repr((r.get("can_connect_reason") or "")[:40])),
        # F3, 2026-09-10. The field is a boolean on EVERY profile, not only the
        # pending one, so a run against any of them catches it going missing.
        ("invitation_pending is a boolean",
         isinstance(r.get("invitation_pending"), bool), repr(r.get("invitation_pending"))),
        ("a pending invitation offers no invitation",
         (not r.get("invitation_pending")) or (cc is False and via is None and curl is None),
         "pending=%r can_connect=%r via=%r url=%r"
         % (r.get("invitation_pending"), cc, via, curl)),
        ("connections", (r.get("connections") is None and bool(r.get("connections_reason")))
         or (isinstance(r.get("connections"), int)
             and "connection" in (r.get("connections_raw") or "")),
         "%r / %r / %r" % (r.get("connections"), r.get("connections_raw"),
                           (r.get("connections_reason") or "")[:30])),
        ("followers", (r.get("followers") is None and bool(r.get("followers_reason")))
         or (isinstance(r.get("followers"), int)
             and "follower" in (r.get("followers_raw") or "")),
         "%r / %r / %r" % (r.get("followers"), r.get("followers_raw"),
                           (r.get("followers_reason") or "")[:30])),
    ]
    # THE DEFECT OF 2026-09-09, AS AN ASSERTION. "500+" was reported as an
    # employer. No field that holds words may hold a count, and the three fields
    # that hold different words may not hold the same words.
    for f, v in (("name", r.get("name")), ("headline", r.get("headline")),
                 ("location", r.get("location")), ("current.company", cur.get("company"))):
        out.append(("%s is not a count" % f, not _count_shaped(v), repr(v)))
    out.append(("current.company is not the connections count",
                not cur.get("company") or cur["company"] != r.get("connections_raw"),
                "%r vs %r" % (cur.get("company"), r.get("connections_raw"))))
    for a, b in (("headline", "location"), ("current.company", "location")):
        va = r.get(a) if a != "current.company" else cur.get("company")
        vb = r.get(b)
        out.append(("%s is not %s" % (a, b), not (va and vb and va == vb), "%r" % (va,)))
    # The three connection fields are one answer, not three independent ones.
    if cc is True:
        out.append(("can_connect=true carries where and how",
                    via in ("topcard", "more-menu") and S.INVITE_HREF in (curl or ""),
                    "via=%r url=%r" % (via, curl)))
        out.append(("the invite is for THIS person",
                    slug.lower() in (curl or "").lower(), repr(curl)))
    elif cc is False:
        out.append(("can_connect=false carries no invite", via is None and curl is None,
                    "via=%r url=%r" % (via, curl)))
    else:
        # RULING R5 widened what a null can mean: our own profile, OR an invite
        # control the page has DISABLED, which is neither a yes nor a no and is
        # reported as undecided with a reason rather than as a false a caller
        # would act on. Either way there is no invitation to hand out, so via
        # and connect_url stay null - and P2-2 and P2-10 compare the actual
        # value against what a person read off the screen, so a null that turns
        # up where the reader saw a Connect control still fails there.
        out.append(("can_connect=null is our own profile or a stated undecidable",
                    (r.get("degree") == "self" or bool(r.get("can_connect_reason")))
                    and via is None and curl is None,
                    "degree=%r via=%r reason=%r"
                    % (r.get("degree"), via, (r.get("can_connect_reason") or "")[:60])))
    return out

# THERE IS NO EXPECTED_VIEWS ANY MORE, AND THAT IS THE POINT - ruling R7,
# 2026-09-09.
#
# There used to be a hand-set constant here saying what one full Phase 2 block
# must cost on the view clock, and P2-9 compared the day's view counter against
# it. That made the test its own oracle: if a regression made the block consume
# seven views and the only red result was `took == 8`, changing the 8 to a 7
# made the run green, and nothing executable anywhere derived the number
# independently. The Manager of the fix pass flagged it unprompted as "the one
# constant in this suite a tired Manager can quietly retune until a run goes
# green", and it was right.
#
# What replaces it is a REGISTRY: every operation that costs a view registers
# itself, by name, as it is invoked (kit/browser.Pace.before_view), and P2-9
# compares the pacing file's delta against that registry and prints the names.
# There is then no number to retune. A disagreement means either the pacing is
# wrong or the registry is, and both deserve a red run.
#
# SAY WHAT THIS NO LONGER PROVES. The old row could catch "this block cost a
# different number of views than it should". The new one cannot: if the block
# comes to cost seven, the registry says seven, the counter says seven, and P2-9
# passes. That question now belongs to the row inventory (ruling R9) - which
# rows ran - and not to an arithmetic identity that could be edited into
# agreement. Adjusting a constant until the suite agrees with the code is not a
# fix and must never read as one.

# THE ROWS THIS RUN INTENDS TO EXECUTE, declared before it starts - ruling R9.
# A count of passes means nothing without the denominator it came from, and a
# row that never ran is a failed run, not an absent line.
PHASE1_ROWS = ("P1-read-post", "P1-comment", "P1-read-comments-1", "P1-comment-is-there",
               "P1-reply", "P1-read-comments-2", "P1-reply-is-there", "P1-react",
               "P1-unreact", "P1-delete-reply", "P1-delete-comment", "P1-read-comments-3",
               "P1-nothing-left", "P1-page-post", "P1-page-delete-post")
PHASE2_ROWS = ("P2-1", "P2-2", "P2-2b", "P2-10", "P2-11", "P2-3", "P2-4", "P2-5",
               "P2-6a", "P2-6b", "P2-6c", "P2-7", "P2-8", "P2-9")
# Profile B must be the shape the design asks for - ruling R12. The row used to
# accept 3rd and 3rd+ as well, which is not what docs/phase-2-design.md says.
PROFILE_B_DEGREES = ("1st", "2nd")


class Rows(object):
    """What the run said it would do, against what it actually reported.

    Ruling R9. A missing --page used to skip the entire Page publish-and-delete
    block in silence, and the summary had no inventory that could name its
    absence. This is the denominator: every row is declared before the run
    starts, every row reports exactly once, and a row that is declared and never
    reported fails the run by name.
    """

    def __init__(self):
        self.declared = []
        self.reported = []

    def declare(self, names):
        self.declared.extend(names)

    def also(self, name):
        """A row discovered as the run goes - the leftover sweep finds however
        many stale posts it finds. Declared the moment it is known, so it is
        still owed a report."""
        self.declared.append(name)

    def report(self, name):
        self.reported.append(name)

    def reconcile(self, reporting_now=None):
        """Which declared rows never reported, and which reported undeclared.

        `reporting_now` is the row that is reconciling AS IT RECONCILES - the
        INVENTORY row itself. It is one of the declared rows, and the check()
        call that records it cannot happen until this method has returned the
        result it is checking, so without this it names itself as the row that
        never ran. It did that on every run: the first live run of 2026-09-10
        printed

            INVENTORY FAILED: 29 rows declared, 28 reported; NEVER RAN: INVENTORY
            RESULT selftest passed=26 failed=3 rows=29/29

        - the summary saying all 29 reported and the inventory row saying 28, in
        the same three lines. A clean run was arithmetically impossible.

        It is excused because it is reporting at this instant, NOT because of
        its name: it must have been declared like any other row, and every other
        missing row is still named. The fencepost is the only thing being fixed
        here.
        """
        want, got = {}, {}
        for n in self.declared:
            want[n] = want.get(n, 0) + 1
        for n in self.reported:
            got[n] = got.get(n, 0) + 1
        if reporting_now is not None:
            got[reporting_now] = got.get(reporting_now, 0) + 1
        missing = sorted(n for n in want if got.get(n, 0) < want[n])
        extra = sorted(n for n in got if got[n] > want.get(n, 0))
        detail = "%d rows declared, %d reported" % (
            len(self.declared), len(self.reported) + (1 if reporting_now is not None else 0))
        if missing:
            detail += "; NEVER RAN: " + ", ".join(missing)
        if extra:
            detail += "; reported but not declared: " + ", ".join(extra)
        return (not missing and not extra), detail


def _norm(t):
    return re.sub(r"\s+", " ", t or "").strip()


def _same_post(row, rec, urn):
    """Is the post read-post loaded the post the search row was about?

    Ruling R2.4. P2-6c used to assert that read-post returned a non-empty
    author, which proves the page loaded - something that was never in doubt. It
    could not tell a resolved permalink that named the right post from one that
    named a stranger's, which is precisely the failure the resolver could
    produce and the verbs would then act on.

    The text probe is the first 60 characters of what the search card showed.
    That is a judgement: too short and it stops distinguishing posts, too long
    and it starts failing on rendering differences between the search card and
    the post page. If a live run fails here on a post that is plainly the right
    one, the fix is to compare fewer characters and write down why - not to drop
    the comparison, which is what was there before.
    """
    want_author, got_author = _norm(row.get("author")), _norm(rec.get("author"))
    want_text, got_text = _norm(row.get("text")), _norm(rec.get("text"))
    probe = want_text[:60].rstrip()
    return [
        ("the permalink names the post that was read", rec.get("urn") == urn,
         "%r wanted %r" % (rec.get("urn"), urn)),
        ("the search row named an author", bool(want_author), repr(want_author)),
        ("author", bool(want_author) and want_author == got_author,
         "read-post says %r, the search row said %r" % (got_author, want_author)),
        ("the search row had enough text to compare", len(want_text) >= 20,
         "%d characters" % len(want_text)),
        ("text", len(want_text) >= 20 and bool(probe) and probe.lower() in got_text.lower(),
         "read-post text does not contain the search row's first %d characters %r"
         % (len(probe), probe)),
    ]


def _notification_holds(recs, limit):
    """What P2-7 can assert that `notifications` does not already enforce.

    Ruling R10, and READ THE LABEL. The verb itself filters to rows with text
    and refuses an empty list, so the row that checked "at least one row, and
    every row has text" could only ever go red if the verb crashed. It was a
    test that Python still works.

    This is honestly a SMOKE TEST plus shape invariants, and the phase does not
    claim `notifications` is proven by it. Proving it would mean checking each
    notification's actor and target against what is on the screen, and the only
    reading of that screen this suite has is the verb's own - so the choice R10
    offers is between a real correspondence check and an honest label, and this
    is the honest label. What follows are the things the producer does NOT
    guarantee, which is the most a shape check can be worth.
    """
    return [
        ("at least one notification", len(recs) >= 1, "%d rows" % len(recs)),
        ("the limit was respected", len(recs) <= limit, "%d rows for a limit of %d"
         % (len(recs), limit)),
        ("the ranks are 1..n with none missing or repeated",
         [r.get("rank") for r in recs] == list(range(1, len(recs) + 1)),
         repr([r.get("rank") for r in recs])),
        ("every row says who or what it is about",
         all_of((bool(r.get("actor") or r.get("url")) for r in recs), len(recs)),
         repr([(r.get("actor"), (r.get("url") or "")[:30]) for r in recs
               if not (r.get("actor") or r.get("url"))][:3])),
        ("every row is marked read or unread, as a boolean",
         all_of((isinstance(r.get("unread"), bool) for r in recs), len(recs)),
         repr([r.get("unread") for r in recs][:5])),
        ("every row has text", all_of(((r.get("text") or "").strip() for r in recs), len(recs)),
         "%d rows" % len(recs)),
    ]



def _run(name, fn, /, **kw):
    """Run one verb, capture its output, return (ok, everything it printed).

    `name` AND `fn` ARE POSITIONAL-ONLY, and that is not a style choice.
    Phase 3's `invite-to-follow` takes a `--name` argument of its own - the full
    name of the person to invite - and passing it through **kw collided with
    this function's own `name` parameter, so the call raised "got multiple
    values for argument 'name'" and the row could never have run. The bar makes
    the collision impossible rather than renamed, because the next verb with an
    argument called `fn` would reintroduce it. Found 2026-09-10 by a test that
    drove the Phase 3 block offline; the live run costs twenty views and would
    have found it the expensive way.
    """
    args = {"port": 9224, "expect": None, "text": None, "text_file": None,
            "limit": None, "resolve": False, "company": None, "title": None,
            "location": None, "page": None, "page_name": None, "days": None}
    args.update(kw)
    a = argparse.Namespace(**args)
    buf = io.StringIO()
    t0 = time.time()
    try:
        with redirect_stdout(buf):
            fn(a)
        ok = True
    except SystemExit as exc:
        ok = (exc.code in (0, None))
    except Exception as exc:          # a verb crashed instead of failing cleanly: a bug, shown as one
        ok = False
        buf.write("FAIL %s: %s\n" % (type(exc).__name__, str(exc).splitlines()[0][:160]))
    out = buf.getvalue()
    line = next((l for l in out.splitlines() if l.startswith("RESULT") or l.startswith("FAIL")),
                out.strip().splitlines()[-1] if out.strip() else "(no output)")
    print("[%s] %-16s %-70s %s  (%.0fs)"
          % (time.strftime("%H:%M:%S"), name, line[:70], "ok" if ok else "FAIL", time.time() - t0),
          flush=True)
    return ok, out


def every(subs):
    """All of these sub-checks passed, AND there was at least one of them.

    Each failure is printed with the value that failed it, because a row that
    says only "FAILED" sends the next reader back to the browser to find out
    what it saw.

    RULING R11. `all()` over an empty sequence is true, so a row that examined
    nothing used to report that everything it examined was fine. That is the
    phase's own zero-rows rule - a read that comes back empty is a failure,
    never a result - applied to the instrument instead of to the verbs.
    """
    subs = list(subs)
    if not subs:
        print("        - nothing was checked: a row that examines no sub-checks passes "
              "because it looked at nothing, which is not a pass", flush=True)
        return False
    bad = [s for s in subs if not s[1]]
    for name, _, detail in bad:
        print("        - %s: %s" % (name, detail), flush=True)
    return not bad


def all_of(subs, at_least_one):
    """`all(...)` paired with the cardinality assertion R11 requires, as one
    value. `at_least_one` is the count that makes the `all` mean something."""
    return bool(at_least_one) and all(subs)


def _records(out):
    """The JSON records a verb printed, one per line."""
    recs = []
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                recs.append(json.loads(line))
            except ValueError:
                pass
    return recs


def sweep_page(a):
    """URNs of earlier selftest posts still on the Page (a killed run leaves one)."""
    from .browser import Browser
    with Browser(a.port) as br:
        br.goto("https://www.linkedin.com/company/%s/admin/page-posts/published/" % a.page, settle=6)
        urns = br.page.evaluate("""() => [...document.querySelectorAll('[data-urn*="activity"]')]
            .filter(c => (c.innerText || '').includes('cc-linkedin selftest'))
            .map(c => c.getAttribute('data-urn'))""")
    if urns:
        print("      sweeping %d leftover selftest post(s): %s" % (len(urns), ", ".join(urns)), flush=True)
    return urns



# ============================================================================
# PHASE 3 ROWS. Added 2026-09-10.
#
# WHAT THIS BLOCK DELIBERATELY DOES NOT DO: it never passes --submit to
# `connect` or to `message`. Both reach a real human being and cannot be taken
# back, and the rows that need that are declared BLOCKED - reported by name,
# counted separately from passes and from failures, and enough to make the run
# exit non-zero. Design section 5 asks for exactly that: a blocked row must
# never read as a passed one.
#
# WHAT A "CLEAN" PHASE 3 RUN MEANS, therefore, and it is not exit 0: every row
# that CAN run passed, `failed=0`, and the blocked rows are named on the RESULT
# line with the reason. The process still exits non-zero, because there are
# acceptance rows nobody has proven.
# ============================================================================

PHASE3_ROWS = ("P3-1", "P3-4a", "P3-4b", "P3-9", "P3-10", "P3-5", "P3-11", "P3-12",
               "P3-13", "P3-14")
# Declared and BLOCKED, every run, until somebody consents. Named here so the
# inventory owes a report for each and none of them can go quiet.
PHASE3_BLOCKED = (
    ("P3-2", "connect --submit to a consenting person"),
    ("P3-3", "withdraw of that same invitation"),
    ("P3-6", "message --submit to a consenting person"),
    ("P3-7", "a multi-paragraph message, staged LIVE - the offline suite proves the "
             "line breaks and the guard, but proving Shift+Enter does not submit "
             "LinkedIn's form needs a thread where an accidental send harms nobody, "
             "and no such thread has been identified"),
    ("P3-8", "the Enter-sends guard broken on purpose, which sends a fragment on "
             "purpose"),
    ("P3-13b", "invite-to-follow --submit, which spends a real credit and puts an "
               "invitation in front of a real person"),
)


def _phase3(a, rows, step, check, blocked, attempt, every, all_of):
    """Every Phase 3 row this run can execute. Returns nothing; reports rows."""
    from kit import connections as N
    from kit import messaging as M
    from .browser import Pace, views_taken

    # -- P3-1: connect, STAGED, with a note -----------------------------------
    # Three capped views: the profile, the invitation page, and the profile
    # again. The third is not waste - it is the half of rule 0.1's proof that
    # the invitation manager cannot give, because a profile that has gone
    # Pending says so where the Sent tab might simply not have caught up.
    note = ("cc-linkedin selftest %s - a staged note. Nothing is sent: this run never "
            "passes --submit." % time.strftime("%H:%M:%S"))
    ok, out = attempt("connect-staged", N.connect, url=a.other_profile, note=note,
                      note_file=None, expect_name=None, submit=False, dump=None)
    m = re.search(r"note_limit_stated=(\d+)", out or "")
    subs = [
        ("the staged connect returned cleanly", ok, out.strip().splitlines()[-1][:90] if out else ""),
        ("it read a note limit OFF THE PAGE", bool(m),
         "the page stated %s" % (m.group(1) if m else "nothing - and this verb refuses "
                                                      "to fall back on a remembered number")),
        ("the profile still offers an invitation after the run",
         "still_connectable=true" in (out or ""), "rule 0.1, half one"),
        ("and the invitation manager does not list one",
         "not_in_sent_tab=true" in (out or ""), "rule 0.1, half two"),
        ("nothing was pressed", "pressed=nothing" in (out or ""), ""),
    ]
    check("P3-1", every(subs), "connect staged, %d checks" % len(subs))

    # -- P3-4a: --submit with no --expect-name, refused before the browser opens
    # THIS ROW OPENS NOTHING. The refusal is the first statement in the verb, so
    # it costs no view and touches no page - which is why it is safe to run with
    # --submit on the flag, and why P3-4b below is NOT.
    ok, out = attempt("connect-submit-without-a-name", N.connect, url=a.other_profile,
                      note=None, note_file=None, expect_name=None, submit=True, dump=None)
    check("P3-4a", (not ok) and "--expect-name is REQUIRED" in (out or "")
          and "RESULT" not in (out or ""),
          "connect --submit with no --expect-name refuses before opening anything")

    # -- P3-4b: a name that names somebody else, refused after reading the page
    # RUN WITHOUT --submit ON PURPOSE. The comparison under test is the same
    # line of code either way, and running it WITH --submit against a real
    # person means that a bug in that one line sends them an invitation. The
    # combination is proven in tests/test_phase3_verbs.py, where nothing is
    # real; here the risk is not worth the extra realism and the report says so.
    ok, out = attempt("connect-wrong-name", N.connect, url=a.other_profile, note=None,
                      note_file=None, expect_name="Not This Person At All",
                      submit=False, dump=None)
    check("P3-4b", (not ok) and "two different people" in (out or ""),
          "a mismatched --expect-name refuses and names both readings")

    # -- P3-9: read-inbox opens nothing --------------------------------------
    before_unread = None
    ok, out = attempt("read-inbox", M.read_inbox, limit=25, unread=False)
    rows_seen = _records(out)
    marker = "unread_marker_seen=true" in (out or "")
    if ok and rows_seen:
        before_unread = sum(1 for r in rows_seen if r.get("unread"))
    subs = [
        ("read-inbox returned cleanly", ok, ""),
        ("it returned conversations", len(rows_seen) >= 1, "%d rows" % len(rows_seen)),
        ("every row names a participant",
         all_of((bool(r.get("participant")) for r in rows_seen), len(rows_seen)),
         "%d rows" % len(rows_seen)),
        ("every row carries a thread_ref, because it cannot carry a URL (A3)",
         all_of(((r.get("thread_ref") or "").startswith(M.REF_PREFIX) for r in rows_seen),
                len(rows_seen)), ""),
        ("it says it opened nothing", "opened_nothing=true" in (out or ""), ""),
    ]
    check("P3-9", every(subs), "read-inbox, %d rows, unread marker seen=%s"
          % (len(rows_seen), marker))

    # -- P3-10 and P3-5: one thread, opened ONCE and used twice ---------------
    # OPENING A THREAD MARKS IT READ, so this block opens exactly one and it is
    # one it can PROVE is already read - the same construction survey.py uses:
    # keep only rows WITHOUT the unread marker, and refuse unless the list also
    # holds a row that HAS it, because a marker missing from every row is a
    # renamed marker and "nothing looks unread" would then be a broken
    # instrument reading as a clean result.
    already_read = [r for r in rows_seen if not r.get("unread")]
    any_unread = [r for r in rows_seen if r.get("unread")]
    if not rows_seen:
        blocked("P3-10", "read-inbox returned no rows, so no thread could be chosen")
        blocked("P3-5", "read-inbox returned no rows, so no thread could be chosen")
    elif not any_unread:
        blocked("P3-10", "no row on the inbox carries the unread marker, so 'this row is "
                         "already read' cannot be proven - only assumed. Opening one on "
                         "that basis could mark a real conversation read.")
        blocked("P3-5", "the same: no positive control for the unread marker")
    elif not already_read:
        blocked("P3-10", "every conversation on the inbox is unread, so opening any of "
                         "them marks a real one read")
        blocked("P3-5", "the same: no already-read conversation to compose in")
    else:
        ref = already_read[0]["thread_ref"]
        ok, out = attempt("read-thread", M.read_thread, url=ref)
        msgs = _records(out)
        thread_url = None
        mu = re.search(r"url=(\S+)", out or "")
        if mu:
            thread_url = mu.group(1)
        subs = [
            ("read-thread returned cleanly", ok, ""),
            ("it returned messages", len(msgs) >= 1, "%d messages" % len(msgs)),
            ("every message names a sender",
             all_of((bool(m2.get("sender")) for m2 in msgs), len(msgs)), ""),
            ("the RESULT line admits it marked the thread read",
             "marked_read=true" in (out or ""),
             "a side effect nobody mentions is how a tool loses somebody's trust"),
        ]
        check("P3-10", every(subs), "read-thread, %d messages" % len(msgs))

        # -- P3-5: message, STAGED, into that same already-read thread --------
        # ONE LINE, AND THE REASON IS WRITTEN HERE. A multi-paragraph draft
        # needs Shift+Enter, and that Shift+Enter does not submit LinkedIn's
        # form is a convention this code relies on rather than something anybody
        # has measured. A single line uses insertText only, which fires no key
        # events at all, so this row cannot send anything to anybody even if
        # that convention is wrong. The multi-paragraph row is P3-7 and it is
        # BLOCKED, not quietly folded into this one.
        if thread_url:
            draft = ("cc-linkedin selftest %s - a staged draft. It is typed, counted, "
                     "read back and deleted. Nothing is sent." % time.strftime("%H:%M:%S"))
            ok, out = attempt("message-staged", M.message, url=thread_url, text=draft,
                              text_file=None, expect_name=None, submit=False, dump=None)
            subs = [
                ("the staged message returned cleanly", ok,
                 (out or "").strip().splitlines()[-1][:90] if out else ""),
                ("the thread gained no message while the draft was typed",
                 "unchanged=true" in (out or ""), "rule 0.2's count, watched NOT firing"),
                ("the draft was taken back out and the reload agrees",
                 "draft_cleared=true" in (out or ""), "rule 0.1"),
                ("nothing was sent", "sent=nothing" in (out or ""), ""),
            ]
            check("P3-5", every(subs), "message staged, %d checks" % len(subs))
        else:
            blocked("P3-5", "read-thread returned no thread URL to compose in")

    # -- P3-11: invitations, parsed against the page's own count --------------
    ok, out = attempt("invitations", N.invitations, limit=25)
    invites = _records(out)
    mp = re.search(r"page_says=(\d+)", out or "")
    mr = re.search(r"rows=(\d+)", out or "")
    subs = [
        ("invitations returned cleanly", ok, ""),
        ("the page publishes a count for the filter whose rows were parsed", bool(mp),
         "A4: without one, the zero-rows exception does not apply"),
        ("the parse equals that count", bool(mp and mr and mp.group(1) == mr.group(1)),
         "parsed %s, page says %s" % (mr.group(1) if mr else "?",
                                      mp.group(1) if mp else "?")),
        ("every row names somebody",
         all_of((bool(r.get("name")) for r in invites), len(invites)) if invites else True,
         "%d rows" % len(invites)),
        ("it pressed nothing", "pressed=nothing" in (out or ""),
         "Accept and Ignore are the two controls here that change another person's world"),
    ]
    check("P3-11", every(subs), "invitations, %d rows" % len(invites))

    # -- P3-12: follow and unfollow, ENDING WHERE IT STARTED ------------------
    #
    # THE ROW IS A ROUND TRIP AND NOT A FIXED STARTING STATE, and that is a
    # deliberate change from design row P3-12's wording ("a Page not currently
    # followed"). What the design ASSERTS is "final state equals the initial
    # state, asserted after a reload", and a round trip proves that from either
    # end while a fixed starting state does not survive its own first run - the
    # row leaves the Page where it found it, so a fixture chosen as "not
    # followed" is still not followed, but a fixture that drifts would silently
    # stop exercising the flip.
    #
    # It also lets the default be the owner's OWN Page, which costs NOTHING
    # against the safety cap (view_self) and borrows nobody else's. Four capped
    # views a run, three times over, to flip a stranger's Page back and forth is
    # a real price for no extra coverage: the control, its three signals and the
    # top-card scoping are the same element on any organisation page. A third
    # party's Page can still be passed and then it is capped like any other.
    if not a.follow_company:
        blocked("P3-12", "no --follow-company and no default: without one the follow path "
                         "never runs, and a path that never executes is not covered by a "
                         "green suite however green.")
    else:
        ok1, out1 = attempt("follow", N.follow, url=a.follow_company, dump=None)
        started_following = "changed=false" in (out1 or "")
        if started_following:
            # Already followed - `follow` correctly pressed nothing. Go the
            # other way first, then come back.
            ok2, out2 = attempt("unfollow", N.unfollow, url=a.follow_company, dump=None)
            ok3, out3 = attempt("follow-back", N.follow, url=a.follow_company, dump=None)
            flipped_away, flipped_back = out2, out3
            want_end = "following=True"
            ok_away, ok_back = ok2, ok3
        else:
            ok2, out2 = attempt("unfollow", N.unfollow, url=a.follow_company, dump=None)
            flipped_away, flipped_back = out1, out2
            want_end = "following=False"
            ok_away, ok_back = ok1, ok2
        subs = [
            ("the first read of the control returned cleanly", ok1,
             "started %s" % ("following" if started_following else "not following")),
            ("one verb flipped the state away from where it started", ok_away
             and "changed=true" in (flipped_away or ""),
             (flipped_away or "").strip().splitlines()[-1][:80] if flipped_away else ""),
            ("the other flipped it back", ok_back and "changed=true" in (flipped_back or ""),
             (flipped_back or "").strip().splitlines()[-1][:80] if flipped_back else ""),
            ("THE FINAL STATE EQUALS THE INITIAL ONE", want_end in (flipped_back or ""),
             "this row borrows a Page and gives it back; it must not be the thing that "
             "changes what the owner follows"),
        ]
        check("P3-12", every(subs), "follow round trip from %s, %d checks"
              % ("following" if started_following else "not following", len(subs)))

    # -- P3-13: invite-to-follow, STAGED --------------------------------------
    if not (a.page and a.invite_name):
        blocked("P3-13", "no --invite-name: the full name of one of the owner's own "
                         "connections, exactly as the Page's invite dialog states it. "
                         "The dialog picks a person by that name and by nothing else.")
    else:
        ok, out = attempt("invite-to-follow-staged", N.invite_to_follow, page=a.page,
                          name=[a.invite_name], submit=False, dump=None)
        mc = re.search(r"credits=(\d+)", out or "")
        subs = [
            ("the staged invite returned cleanly", ok,
             (out or "").strip().splitlines()[-1][:90] if out else ""),
            ("it read the credit line off the page", bool(mc),
             "the credit is the thing that is actually spent"),
            ("the credits did not move", "unchanged=true" in (out or ""), "rule 0.1"),
            ("nothing was pressed", "pressed=nothing" in (out or ""), ""),
        ]
        check("P3-13", every(subs), "invite-to-follow staged, credits=%s"
              % (mc.group(1) if mc else "?"))

    # -- P3-14: the caps, exercised against a throwaway pacing file -----------
    # IT DOES NOT TOUCH THE REAL pace.json. The rolling window is a property of
    # a FILE, so the only way to exercise it is to write one - and writing a
    # hundred connects into the machine's own file to prove a cap would spend
    # the account's real allowance to test the thing that protects it.
    check("P3-14", every(_cap_checks()), "the rolling 7-day connect cap and the retention "
                                         "that makes it mean anything")


def _cap_checks():
    """P3-14, run against a temporary state directory.

    TWO SCENARIOS, because the two halves of this cap fail in opposite
    directions. A week already at the allowance must REFUSE and must not spend a
    slot doing it; and a week under the allowance must go through AND leave the
    history the next check will need. The second is what the retention change is
    for: pace.json used to delete every day but today, which makes a rolling sum
    identical to the daily count and a weekly cap unreachable forever.
    """
    import datetime
    import shutil
    import tempfile as _tf
    from . import browser as _B

    def day(o):
        return (datetime.date.today() + datetime.timedelta(days=o)).strftime("%Y-%m-%d")

    def seed(path, per_day):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({day(-o): {"connect": per_day} for o in range(1, 7)}, f)

    tmp = _tf.mkdtemp(prefix="cc-linkedin-caps-")
    keep_state, keep_gap = _B.STATE_DIR, _B.Pace.GAP
    _B.STATE_DIR, _B.Pace.GAP = tmp, (0, 0)
    try:
        path = os.path.join(tmp, "pace.json")
        limit, window = _B.Pace.ROLLING_CAPS["connect"]
        # 1. a week already holding the whole allowance
        seed(path, (limit // 6) + 1)
        refused = False
        with redirect_stdout(io.StringIO()):
            try:
                _B.Pace().before("connect")
            except SystemExit:
                refused = True
        with open(path, encoding="utf-8") as f:
            after_refusal = json.load(f)
        # 2. a quiet week, which must go through and keep its history
        seed(path, 1)
        went = True
        with redirect_stdout(io.StringIO()):
            try:
                _B.Pace().before("connect")
            except SystemExit:
                went = False
        with open(path, encoding="utf-8") as f:
            after_ok = json.load(f)
        kept = sorted(k for k in after_ok if _B.DAY_KEY.match(k))
        seeded_still_there = [day(-o) for o in range(1, 7) if day(-o) not in kept]
        return [
            ("a week already holding the whole allowance refuses the next invitation",
             refused, "cap %d over %d days" % (limit, window)),
            ("and it took no slot on the way to refusing",
             (after_refusal.get(day(0)) or {}).get("connect", 0) == 0,
             "a refusal that spent a slot would make tomorrow smaller for having been "
             "refused"),
            ("a quiet week is not refused", went,
             "a cap that refuses whatever the numbers are is not a check"),
            ("and the history the window counts over SURVIVES the save",
             not seeded_still_there,
             "dropped %s - pace.json used to delete every day but today, which makes "
             "the rolling sum identical to the daily count"
             % (", ".join(seeded_still_there) or "nothing")),
            ("the retention covers the window it is for",
             _B.Pace.RETAIN_DAYS >= window + 1,
             "retain %d, window %d" % (_B.Pace.RETAIN_DAYS, window)),
        ]
    finally:
        _B.STATE_DIR, _B.Pace.GAP = keep_state, keep_gap
        shutil.rmtree(tmp, ignore_errors=True)


def run(a):
    # RULING R9. --page and --page-name used to be optional, and a missing one
    # SILENTLY SKIPPED the whole Page publish-and-delete block: not a failed row,
    # no row at all. That is the skip-counted-as-a-pass that phase-2-design.md
    # section 8 already forbade, so this is the existing rule being enforced
    # rather than a new one.
    if not (a.page and a.page_name):
        print("FAIL --page and --page-name are required. Without them the run would skip "
              "publishing a post to the Page and deleting it again - the only place this "
              "suite writes anything outside a comment - and would say nothing about having "
              "skipped it. A missing fixture is a failed run, not a shorter one.", flush=True)
        sys.exit(1)
    # RULING R20, 2026-09-10. The flags still win, but a value not passed is
    # looked for in the machine's own fixtures file - outside the repository,
    # beside pace.json - so that finding a profile of the required shape is paid
    # for ONCE rather than by every seat, out of the daily view cap. What is
    # committed is the SHAPE; what is on the machine is the value. A value that
    # is in neither place still FAILS the run below - R20 moved where fixtures
    # live, it did not make any of them optional.
    from . import fixtures as FX
    # --post is a fixture as much as the profiles are: a permalink of a post WE
    # authored, which the comment rows write to and delete from. It is the
    # owner's own content rather than a third party's, so nothing stopped it
    # being committed - but it had no home either, and every seat found one by
    # hand. It lives with the others now.
    a.post = FX.value(a.post, "post", "url")
    a.other_profile = FX.value(a.other_profile, "other_profile", "url")
    a.other_expect = FX.value(a.other_expect, "other_profile", "expect")
    a.menu_profile = FX.value(a.menu_profile, "menu_profile", "url")
    a.menu_expect = FX.value(a.menu_expect, "menu_profile", "expect")
    # F3's fixture. It exists because a REAL invitation was sent to that person
    # on 2026-09-09, at the owner's instruction; nothing about it can be
    # fabricated and no other profile can stand in for it.
    a.pending_profile = FX.value(a.pending_profile, "pending_profile", "url")
    # Phase 3's own two fixtures, on the machine for the same reason as the
    # others (R20): both name a third party and this repository is public.
    a.follow_company = FX.value(a.follow_company, "follow_company", "url")
    a.invite_name = FX.value(a.invite_name, "invite_name", "name")
    if not a.post:
        print("FAIL --post is required: a permalink of a post WE authored, which the\n"
              "comment rows comment on and then delete from. Pass it, or put it in %s\n"
              "as \"post\" -> \"url\" (ruling R20)." % FX.path(), flush=True)
        sys.exit(1)
    if not (a.other_profile and a.other_expect and a.menu_profile and a.menu_expect
            and a.pending_profile):
        print("FAIL the Phase 2 profile fixtures are required, and none of them is committed: "
              "this repository is public, so no third party's URL or details go in it.\n"
              "  --other-profile  a 1st- or 2nd-degree profile URL (rows P2-2, P2-2b)\n"
              "  --other-expect   what a person reads off that profile\n"
              "  --menu-profile   THE SHAPE BOTH DEFECTS OF 2026-09-09 APPEARED ON: a profile\n"
              "                   whose invitation is a MENU ITEM behind More rather than a\n"
              "                   control on the top card, AND whose top card states no current\n"
              "                   employer (no company pill). Row P2-10.\n"
              "  --menu-expect    what a person reads off THAT profile; its company must be none\n"
              "  --pending-profile  a profile we have ALREADY SENT an invitation to, which has\n"
              "                   not been accepted, so its top card reads Pending. Row P2-11.\n"
              "                   No other fixture reaches that state and none of it can be\n"
              "                   fabricated - an invitation has to have been sent.\n"
              "  the expect syntax: " + EXPECT_SYNTAX + "\n"
              "Soren's own profile has no degree badge, no invite control and no Message button, "
              "so without profile B most of what read-profile returns is never exercised. The "
              "menu profile is specified that tightly because it is the only shape on which both "
              "defects are visible: on it, the code as it stood on 2026-09-09 reported the "
              "connections count as the employer and reported 'Message' as the connection state "
              "of somebody it could in fact invite. A row that never runs against that shape "
              "cannot go red when either fix is taken out.\n"
              "Pass them as flags, or put them in the machine's own fixtures file, "
              "which is outside this repository and is where these values are meant "
              "to live (ruling R20):\n"
              "  %s\n"
              '  {"other_profile": {"url": ..., "expect": ...},\n'
              '   "menu_profile":  {"url": ..., "expect": ...},\n'
              '   "pending_profile": {"url": ...}}\n'
              "Supplied now: %s." % (FX.path(), ", ".join(
                  "%s=%s" % (k, "yes" if v else "NO")
                  for k, v in (("other_profile", a.other_profile),
                               ("other_expect", a.other_expect),
                               ("menu_profile", a.menu_profile),
                               ("menu_expect", a.menu_expect),
                               ("pending_profile", a.pending_profile)))), flush=True)
        sys.exit(1)
    menu_exp = _expect(a.menu_expect, "--menu-expect")
    if menu_exp["company"].lower() != "none":
        print("FAIL --menu-expect says company=%r. The menu profile must be one whose top card "
              "states NO current employer, so that the field which used to be filled with a "
              "connections count is the field under test. Pick a profile with no company pill "
              "and say company=none." % menu_exp["company"], flush=True)
        sys.exit(1)

    stamp = time.strftime("%H:%M:%S")
    text = "cc-linkedin selftest %s. Test comment, deleted by the tool a minute later." % stamp
    reply_text = "Reply from the selftest %s, also deleted." % stamp
    passed = failed = blocked_n = 0

    rows = Rows()
    rows.declare(PHASE1_ROWS)
    rows.declare(PHASE2_ROWS)
    rows.declare(PHASE3_ROWS)
    rows.declare(tuple(name for name, _ in PHASE3_BLOCKED))
    rows.declare(("INVENTORY",))
    print("--- this run intends to execute %d rows: %s ---"
          % (len(rows.declared), ", ".join(rows.declared)), flush=True)

    # The tab census before anything opens a tab, so P2-9 can say whether the
    # run left one behind. Read from the DevTools endpoint, which needs no lock
    # and opens nothing.
    from .browser import open_tabs
    try:
        tabs_before = open_tabs(a.port)
    except Exception as exc:
        tabs_before = None
        print("      could not count the browser's tabs before the run (%s); P2-9 will fail "
              "on it rather than report a tidy zero" % str(exc).splitlines()[0][:80], flush=True)

    def step(row, name, fn, /, **kw):
        """Run one verb and record it against the row it is. Every row goes
        through exactly one accounting path (ruling R9)."""
        nonlocal passed, failed
        ok, out = _run(name, fn, port=a.port, **kw)
        rows.report(row)
        if ok:
            passed += 1
        else:
            failed += 1
            print("      %s FAILED: the verb did not return cleanly" % row, flush=True)
        return ok, out

    def attempt(name, fn, /, **kw):
        """Run a Phase 2 verb WITHOUT counting it. Every Phase 2 row is counted
        once, by its check - and row P2-3 is a row whose verb is SUPPOSED to
        fail, so a runner that counted a non-zero exit would score the correct
        behaviour as a defect and the whole run as red."""
        return _run(name, fn, port=a.port, **kw)

    def blocked(row, why):
        """A row nobody has proven, reported BY NAME and counted on its own.

        Design section 5: a blocked row must never read as a passed one. It is
        not a failure either - nothing is broken - so it gets its own counter,
        it appears on the RESULT line, and it is enough on its own to make the
        run exit non-zero. A suite that went green with acceptance rows nobody
        had run would be the largest fail-open instrument in this repository.
        """
        nonlocal blocked_n
        rows.report(row)
        blocked_n += 1
        print("[%s] %-16s %-70s %s" % (time.strftime("%H:%M:%S"), row, why[:70], "BLOCKED"),
              flush=True)
        if len(why) > 70:
            print("      BLOCKED: %s" % why, flush=True)

    def check(row, ok, detail):
        nonlocal passed, failed
        rows.report(row)
        if ok:
            passed += 1
        else:
            failed += 1
            print("      %s FAILED: %s" % (row, detail), flush=True)
        print("[%s] %-16s %-70s %s" % (time.strftime("%H:%M:%S"), row, detail[:70],
                                       "ok" if ok else "FAIL"), flush=True)
        return ok

    # ======================================================== PHASE 1: writing
    print("--- Phase 1: comments, replies, reactions, deletes ---", flush=True)
    ok, out = step("P1-read-post", "read-post", C.read_post, url=a.post)
    m = re.search(r'"text": "(.{0,40})', out)
    expect = None
    if m:
        expect = m.group(1).split("\\n")[0].strip('"')[:30]
    step("P1-comment", "comment", C.comment, url=a.post, expect=expect, text=text)
    ok, out = step("P1-read-comments-1", "read-comments", C.read_comments, url=a.post)
    check("P1-comment-is-there", text[:40] in out,
          "the comment just written is in the read-comments output")
    step("P1-reply", "reply", C.reply, url=a.post, expect=expect, to=text[:40], text=reply_text)
    ok, out = step("P1-read-comments-2", "read-comments", C.read_comments, url=a.post)
    check("P1-reply-is-there", reply_text[:30] in out,
          "the reply just written is in the read-comments output")
    step("P1-react", "react", C.react, url=a.post, expect=expect, kind="like")
    step("P1-unreact", "unreact", C.unreact, url=a.post)
    step("P1-delete-reply", "delete-reply", C.delete_comment, url=a.post, match=reply_text[:30])
    step("P1-delete-comment", "delete-comment", C.delete_comment, url=a.post, match=text[:40])
    ok, out = step("P1-read-comments-3", "read-comments", C.read_comments, url=a.post)
    check("P1-nothing-left", not (text[:40] in out or reply_text[:30] in out),
          "neither the selftest comment nor the reply is still on the post")

    if True:                      # never conditional again - ruling R9
        import cc_linkedin as tool
        for urn in sweep_page(a):
            # Discovered work: declared the moment it is known, so it is still
            # owed a report and cannot vanish from the inventory.
            rows.also("P1-delete-leftover")
            step("P1-delete-leftover", "delete-leftover", C.delete_post,
                 url=C.permalink(urn), expect="Throwaway post")
        body = "cc-linkedin selftest %s. Throwaway post, deleted by the tool a minute later." % stamp
        tf = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
        tf.write(body)
        tf.close()
        buf = io.StringIO()
        t0 = time.time()
        try:
            with redirect_stdout(buf):
                tool.cmd_post(argparse.Namespace(page=a.page, page_name=a.page_name, text=tf.name, media=None,
                                                 schedule=None, submit=True, shot=None, port=a.port, keep_tab=False))
            ok = True
        except SystemExit as exc:
            ok = exc.code in (0, None)
        os.unlink(tf.name)
        out = buf.getvalue()
        line = next((l for l in out.splitlines() if l.startswith("RESULT") or l.startswith("FAIL")), "(no output)")
        print("[%s] %-16s %-70s %s  (%.0fs)" % (time.strftime("%H:%M:%S"), "post (page)", line[:70],
                                                "ok" if ok else "FAIL", time.time() - t0), flush=True)
        m = re.search(r"url=(\S+)", line)
        check("P1-page-post", bool(ok and m),
              "the Page post was published and gave back a URL to delete it by")
        if ok and m:
            step("P1-page-delete-post", "delete-post", C.delete_post,
                 url=m.group(1), expect="Throwaway post")
        else:
            check("P1-page-delete-post", False,
                  "no post URL to delete; check the Page for a leftover selftest post")

    # ======================================================== PHASE 2: reading
    print("--- Phase 2: profiles, company, search, notifications, stats ---", flush=True)
    from . import people as P
    from . import search as Q
    from . import account as A

    pace = Pace()
    # BOTH counters, since the view/view_self split of 2026-09-10. P2-9 compares
    # each one against its own half of the registry: a comparison against the
    # TOTAL would stay green while a stranger's profile drifted onto the
    # uncapped counter, which is the one mistake that split can make.
    views_before = pace.count("view")
    self_views_before = pace.count("view_self")

    # -- P2-1: the owner's own profile, every field it returns ----------------
    ok, out = attempt("read-profile", P.read_profile, url=a.profile)
    recs = _records(out)
    r = recs[0] if recs else {}
    if not (ok and recs):
        check("P2-1", False, "read-profile did not return a record for the owner's own profile")
    else:
        subs = _profile_says(r, _expect(a.profile_expect, "--profile-expect")) \
             + _profile_holds(r, "sorenfrederiksen") \
             + [("about is the real one", len(r.get("about") or "") > 100,
                 "%d characters" % len(r.get("about") or ""))]
        check("P2-1", every(subs), "own profile, %d fields checked" % len(subs))

    # -- P2-2: profile B - every field, against what a reader saw on the page --
    want_b = (re.search(r"/in/([^/?#]+)", a.other_profile) or [None, a.other_profile.strip("/")])[1]
    ok, out = attempt("read-profile B", P.read_profile, url=a.other_profile)
    recs = _records(out)
    r = recs[0] if recs else {}
    if not (ok and recs):
        check("P2-2", False, "read-profile did not return a record for profile B")
        check("P2-2b", False, "no record to check the invariants of")
    else:
        says = _profile_says(r, _expect(a.other_expect, "--other-expect"))
        check("P2-2", every(says), "profile B against the page, %d fields" % len(says))
        holds = _profile_holds(r, want_b) + [
            ("degree is not self", r.get("degree") != "self", repr(r.get("degree"))),
            # RULING R12. The design asks for a 1st- or 2nd-degree profile here,
            # and the row used to accept 3rd and 3rd+ as well - accepting
            # whatever turned up instead of enforcing what was specified.
            ("degree is 1st or 2nd, as the design requires",
             (r.get("degree") or "").lower() in PROFILE_B_DEGREES,
             "%r is not one of %r; --other-profile must be a 1st- or 2nd-degree profile"
             % (r.get("degree"), PROFILE_B_DEGREES))]
        check("P2-2b", every(holds), "profile B invariants, %d of them" % len(holds))

    # -- P2-10: the invitation that lives BEHIND THE MORE MENU ----------------
    # The other half of the connection read, and the half the defect was in. On
    # some profiles Connect is a control on the top card and on others it is a
    # menu item behind More, and no field on the card says which. A run that
    # only ever sees the first kind never executes the menu path at all.
    want_m = (re.search(r"/in/([^/?#]+)", a.menu_profile) or [None, a.menu_profile.strip("/")])[1]
    ok, out = attempt("read-profile M", P.read_profile, url=a.menu_profile)
    recs = _records(out)
    r = recs[0] if recs else {}
    subs = [("a record came back", bool(ok and recs), "ok=%s records=%d" % (ok, len(recs)))]
    if ok and recs:
        cur = r.get("current") or {}
        subs += [
            ("can_connect", r.get("can_connect") is True, repr(r.get("can_connect"))),
            ("connect_via", r.get("connect_via") == "more-menu", repr(r.get("connect_via"))),
            ("the invite came from the menu, for this person",
             S.INVITE_HREF in (r.get("connect_url") or "")
             and want_m.lower() in (r.get("connect_url") or "").lower(),
             repr(r.get("connect_url"))),
            # The employer field on a top card that states no employer. Left to
            # position, this is the field that filled itself with the
            # connections count.
            ("no employer is stated, and the record says so rather than filling it",
             cur.get("company") is None and bool(cur.get("company_reason")),
             "company=%r reason=%r" % (cur.get("company"),
                                       (cur.get("company_reason") or "")[:50])),
        ] + _profile_says(r, menu_exp) + _profile_holds(r, want_m)
    check("P2-10", every(subs), "menu profile, %d checks" % len(subs))

    # -- P2-11: an invitation that has already been sent ----------------------
    # F3, 2026-09-10. The state no other fixture reaches. Until today this
    # profile answered can_connect: false - right - with the reason "no invite
    # control on the top card and none in the More menu", while the card in
    # front of it said Pending. This row is also the ONLY thing that notices if
    # LinkedIn changes the label the detection is matched on: without it, that
    # change turns invitation_pending quietly false and nothing goes red.
    #
    # It asserts no name, headline or location, because the fixture needs none:
    # what makes this profile the right one is a fact about the invitation, and
    # asking a person to transcribe three more fields for it would add nothing a
    # wrong reading could catch.
    want_p = (re.search(r"/in/([^/?#]+)", a.pending_profile)
              or [None, a.pending_profile.strip("/")])[1]
    ok, out = attempt("read-profile P", P.read_profile, url=a.pending_profile)
    recs = _records(out)
    r = recs[0] if recs else {}
    subs = [("a record came back", bool(ok and recs), "ok=%s records=%d" % (ok, len(recs)))]
    if ok and recs:
        why = r.get("can_connect_reason") or ""
        subs += [
            ("invitation_pending is true", r.get("invitation_pending") is True,
             repr(r.get("invitation_pending"))),
            ("can_connect is a definite no, not an undecided",
             r.get("can_connect") is False, repr(r.get("can_connect"))),
            ("the reason names the pending state", "pending" in why.lower(), repr(why[:90])),
            ("the reason is no longer the uninformative one",
             "no invite control" not in why.lower(), repr(why[:90])),
            ("no invitation is handed out",
             r.get("connect_via") is None and r.get("connect_url") is None,
             "via=%r url=%r" % (r.get("connect_via"), r.get("connect_url"))),
        ] + _profile_holds(r, want_p)
    check("P2-11", every(subs), "pending-invitation profile, %d checks" % len(subs))

    # -- P2-3: a deliberately wrong --expect must REFUSE ----------------------
    ok, out = attempt("read-profile X", P.read_profile, url=a.profile,
                   expect="Chief Marmalade Officer of Atlantis")
    check("P2-3", (not ok) and not _records(out) and "FAIL" in out,
          "wrong --expect refused: exited non-zero=%s, records printed=%d"
          % (not ok, len(_records(out))))

    # -- P2-4: the company page ----------------------------------------------
    ok, out = attempt("read-company", P.read_company, url=a.company)
    recs = _records(out)
    r = recs[0] if recs else {}
    check("P2-4", ok and bool(recs)
          and r.get("name") == "CenterConsulting, Inc."
          and isinstance(r.get("followers"), int) and r.get("followers") >= 1,
          "company: name=%r followers=%r" % (r.get("name"), r.get("followers")))

    # -- P2-5: people search --------------------------------------------------
    ok, out = attempt("search-people", Q.search_people, query=a.query_people, limit=5)
    recs = _records(out)
    check("P2-5", ok and bool(recs) and recs[0].get("url", "").rstrip("/") == SOREN.rstrip("/"),
          "first row url=%r" % (recs[0].get("url") if recs else None))

    # -- P2-6: content search, then the chain into Phase 1 --------------------
    ok, out = attempt("search-posts", Q.search_posts, query=a.query_posts, limit=5)
    recs = _records(out)
    check("P2-6a", ok and len(recs) >= 3
          and all(x.get("author") for x in recs)
          and all("lnkd.in" in (x.get("share_url") or "") for x in recs),
          "rows=%d, every row has an author and a lnkd.in share_url=%s"
          % (len(recs), all(x.get("author") and "lnkd.in" in (x.get("share_url") or "") for x in recs)))

    ok, out = attempt("search-posts -r", Q.search_posts, query=a.query_posts, limit=3, resolve=True)
    recs = _records(out)
    resolved = [x for x in recs if "urn:li:activity" in (x.get("permalink") or "")
                or re.search(r"urn:li:(activity|share|ugcPost):\d+", x.get("permalink") or "")]
    check("P2-6b", ok and len(recs) == 3 and len(resolved) == 3,
          "resolved %d of %d rows to a post urn" % (len(resolved), len(recs)))

    if resolved:
        # RULING R2.4. This used to assert that read-post came back with a
        # non-empty author, which proves the page loaded - never in doubt - and
        # could not tell a permalink naming the right post from one naming a
        # stranger's. It now compares the AUTHOR AND THE TEXT with the search row
        # the permalink came from, which is the only thing that distinguishes
        # them, and is the check that would have caught the resolver defect.
        row = resolved[0]
        ok, out = attempt("read-post chain", C.read_post, url=row["permalink"])
        chain = _records(out)
        subs = [("read-post returned a record", bool(ok and chain),
                 "ok=%s records=%d" % (ok, len(chain)))]
        if ok and chain:
            subs += _same_post(row, chain[0], C.urn_of(row["permalink"]))
        check("P2-6c", every(subs),
              "the resolved permalink loaded the post the search row was about")
    else:
        check("P2-6c", False, "no resolved permalink to feed to read-post")

    # -- P2-7: notifications --------------------------------------------------
    ok, out = attempt("notifications", A.notifications, limit=10)
    recs = _records(out)
    subs = [("the verb returned cleanly", ok, "ok=%s" % ok)] + _notification_holds(recs, 10)
    check("P2-7", every(subs),
          "SMOKE TEST ONLY - shape, not correspondence with the page (R10): %d rows"
          % len(recs))

    # -- P2-8: the Page's analytics -------------------------------------------
    ok, out = attempt("stats", A.stats, page=a.page, page_name=a.page_name, days=30)
    recs = _records(out)
    r = recs[0] if recs else {}
    posts = r.get("posts") or []
    # RULING R11. The per-post assertion used to be `all(...)` over `posts`, which
    # is TRUE when there are no posts: a stats record built from an empty table
    # satisfied it by examining nothing. Every "all rows satisfy X" is now paired
    # with the cardinality that makes it mean something, in the same check.
    check("P2-8", every([
        ("the verb returned a record", bool(ok and recs), "ok=%s records=%d" % (ok, len(recs))),
        ("followers is a number", isinstance(r.get("followers"), int), repr(r.get("followers"))),
        ("the Page is the one that was asked for", r.get("name") == a.page_name,
         "%r wanted %r" % (r.get("name"), a.page_name)),
        ("the window is the one that was asked for", r.get("window_days") == 30,
         repr(r.get("window_days"))),
        ("the window states its own dates", bool(r.get("window_start"))
         and bool(r.get("window_end")),
         "%r..%r" % (r.get("window_start"), r.get("window_end"))),
        ("the table had at least one post in it", len(posts) >= 1, "%d posts" % len(posts)),
        ("every post has an integer impressions count",
         all_of((isinstance(x.get("impressions"), int) for x in posts), len(posts)),
         repr([x.get("impressions") for x in posts][:5])),
    ]), "Page stats: %d posts, followers=%r" % (len(posts), r.get("followers")))

    # ======================================================== PHASE 3: reaching
    # It runs BEFORE P2-9, so the views it takes are inside the window P2-9
    # reconciles. A block that ran afterwards would be invisible to the one row
    # that checks the pacing file against what the run believes it opened.
    print("--- Phase 3: connect, message, the inbox, invitations, follow ---", flush=True)
    _phase3(a, rows, step, check, blocked, attempt, every, all_of)

    for name, why in PHASE3_BLOCKED:
        blocked(name, why)

    # -- P2-9: the run left nothing behind, and the two records of what it
    # -- viewed agree -------------------------------------------------------
    from .browser import open_file_dialogs, views_taken, STATE_DIR
    views_after = Pace().count("view")
    self_views_after = Pace().count("view_self")
    took = views_after - views_before
    took_self = self_views_after - self_views_before
    registered = views_taken()
    lock = os.path.join(STATE_DIR, "browser-%d.lock" % a.port)
    dialogs = open_file_dialogs()
    try:
        tabs_after = open_tabs(a.port)
        tabs_why = None
    except Exception as exc:
        tabs_after, tabs_why = None, str(exc).splitlines()[0][:100]

    print("      the views this run registered, in order:", flush=True)
    for i, v in enumerate(registered, 1):
        print("        %2d. [%s] %s" % (i, v["kind"], v["what"]), flush=True)
    print("      against the safety cap: %d of %d today. Our own surfaces: %d."
          % (views_after, Pace.VIEW_CAP, self_views_after), flush=True)

    check("P2-9", every([
        # R7: no constant. The pacing file's delta against the run's own registry
        # of what it viewed. There is no number here to retune into agreement.
        ("the pacing file and the run's own registry agree on the CAPPED counter",
         took == len(views_taken("view")),
         "the safety counter rose by %d, the run registered %d views of other people's "
         "surfaces" % (took, len(views_taken("view")))),
        # The split of 2026-09-10 made this a second, separate identity rather
        # than a wider one. Summing them would let a view move from the capped
        # counter to the uncapped one without a single row going red.
        ("the pacing file and the run's own registry agree on the SELF counter",
         took_self == len(views_taken("view_self")),
         "the self counter rose by %d, the run registered %d views of our own surfaces"
         % (took_self, len(views_taken("view_self")))),
        ("every registered view is on one of the two counters",
         all_of((v["kind"] in ("view", "view_self") for v in registered), len(registered)),
         repr(sorted({v["kind"] for v in registered}))),
        ("the run viewed something", len(registered) >= 1, "%d views" % len(registered)),
        ("the run viewed somebody else's surface", len(views_taken("view")) >= 1,
         "%d capped views - a selftest that never leaves our own surfaces is not "
         "exercising the read verbs" % len(views_taken("view"))),
        ("the browser lock is released", not os.path.exists(lock), lock),
        ("no native file dialog is on screen", not dialogs, repr(dialogs)),
        # The stray-tab assertion the design asked for and the row never had.
        ("the browser's tabs could be counted", tabs_before is not None
         and tabs_after is not None,
         "before=%s after=%s (%s)" % (tabs_before is not None, tabs_after is not None, tabs_why)),
        ("the run left no stray tab", tabs_before is not None and tabs_after is not None
         and len(tabs_after) <= len(tabs_before),
         "%d tabs before, %d after: %s"
         % (len(tabs_before or []), len(tabs_after or []),
            ", ".join(t[:60] for t in (tabs_after or []))[:200])),
    ]), "views %d capped + %d own, lock released=%s, dialogs=%d, tabs %s->%s"
        % (took, took_self, not os.path.exists(lock), len(dialogs),
           len(tabs_before or []) if tabs_before is not None else "?",
           len(tabs_after or []) if tabs_after is not None else "?"))

    # -- the inventory: did every row this run declared actually report? -------
    # RULING R9. A count of passes means nothing without the denominator it came
    # from, and a row that never ran is a failed run, not an absent line.
    # INVENTORY is itself a declared row, and it is reporting at the moment it
    # reconciles - see Rows.reconcile.
    ok, detail = rows.reconcile(reporting_now="INVENTORY")
    check("INVENTORY", ok, detail)

    print("RESULT selftest passed=%d failed=%d blocked=%d rows=%d/%d"
          % (passed, failed, blocked_n, len(rows.reported), len(rows.declared)), flush=True)
    # BLOCKED EXITS NON-ZERO TOO, and design section 5 asks for exactly that.
    # A CLEAN Phase 3 run is `failed=0` with the blocked rows named - not exit
    # 0, which would say every acceptance row had been proven when six of them
    # have not.
    if failed or blocked_n:
        sys.exit(1)
