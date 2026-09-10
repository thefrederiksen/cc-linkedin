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

TWO BLOCKS, and the run does BOTH. Phase 1 writes: on a post of ours it
comments, replies, reacts, unreacts and deletes everything it made, and on the
Page it publishes a throwaway post and deletes it. Phase 2 only reads: a
profile, a second person's profile, a refusal, a company page, two searches,
the notifications page and the Page's analytics.

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
from .browser import Pace, log

DEGREES_NOT_SELF = ("1st", "2nd", "3rd", "3rd+", "you")
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
        out.append(("can_connect=null only on our own profile",
                    r.get("degree") == "self" and via is None and curl is None,
                    "degree=%r via=%r" % (r.get("degree"), via)))
    return out

# What one full Phase 2 block must cost on the view clock. read-profile costs
# one each - the owner's, profile B, the menu profile, and the refusal, which
# navigates before it refuses - read-company one, and each search one; the two
# searches that share a query still open two pages. notifications and stats cost
# NOTHING: they are our own screens, not anybody's profile. Resolving a short
# link is a navigation to a post, not a profile view.
EXPECTED_VIEWS = 8


def _run(name, fn, **kw):
    """Run one verb, capture its output, return (ok, everything it printed)."""
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


def run(a):
    if not (a.other_profile and a.other_expect and a.menu_profile and a.menu_expect):
        print("FAIL the Phase 2 profile fixtures are required, and none of them is committed: "
              "this repository is public, so no third party's URL or details go in it.\n"
              "  --other-profile  a 1st- or 2nd-degree profile URL (rows P2-2, P2-2b)\n"
              "  --other-expect   what a person reads off that profile\n"
              "  --menu-profile   THE SHAPE BOTH DEFECTS OF 2026-09-09 APPEARED ON: a profile\n"
              "                   whose invitation is a MENU ITEM behind More rather than a\n"
              "                   control on the top card, AND whose top card states no current\n"
              "                   employer (no company pill). Row P2-10.\n"
              "  --menu-expect    what a person reads off THAT profile; its company must be none\n"
              "  the expect syntax: " + EXPECT_SYNTAX + "\n"
              "Soren's own profile has no degree badge, no invite control and no Message button, "
              "so without profile B most of what read-profile returns is never exercised. The "
              "menu profile is specified that tightly because it is the only shape on which both "
              "defects are visible: on it, the code as it stood on 2026-09-09 reported the "
              "connections count as the employer and reported 'Message' as the connection state "
              "of somebody it could in fact invite. A row that never runs against that shape "
              "cannot go red when either fix is taken out.", flush=True)
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
    passed = failed = 0

    def step(name, fn, **kw):
        nonlocal passed, failed
        ok, out = _run(name, fn, port=a.port, **kw)
        if ok:
            passed += 1
        else:
            failed += 1
        return ok, out

    def attempt(name, fn, **kw):
        """Run a Phase 2 verb WITHOUT counting it. Every Phase 2 row is counted
        once, by its check - and row P2-3 is a row whose verb is SUPPOSED to
        fail, so a runner that counted a non-zero exit would score the correct
        behaviour as a defect and the whole run as red."""
        return _run(name, fn, port=a.port, **kw)

    def check(row, ok, detail):
        nonlocal passed, failed
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
    ok, out = step("read-post", C.read_post, url=a.post)
    m = re.search(r'"text": "(.{0,40})', out)
    expect = None
    if m:
        expect = m.group(1).split("\\n")[0].strip('"')[:30]
    step("comment", C.comment, url=a.post, expect=expect, text=text)
    ok, out = step("read-comments", C.read_comments, url=a.post)
    if text[:40] not in out:
        print("      the new comment is NOT in the read-comments output", flush=True)
        failed += 1
    step("reply", C.reply, url=a.post, expect=expect, to=text[:40], text=reply_text)
    ok, out = step("read-comments", C.read_comments, url=a.post)
    if reply_text[:30] not in out:
        print("      the reply is NOT in the read-comments output", flush=True)
        failed += 1
    step("react", C.react, url=a.post, expect=expect, kind="like")
    step("unreact", C.unreact, url=a.post)
    step("delete-reply", C.delete_comment, url=a.post, match=reply_text[:30])
    step("delete-comment", C.delete_comment, url=a.post, match=text[:40])
    ok, out = step("read-comments", C.read_comments, url=a.post)
    if text[:40] in out or reply_text[:30] in out:
        print("      leftovers: the selftest comment or reply is still on the post", flush=True)
        failed += 1

    if a.page and a.page_name:
        import cc_linkedin as tool
        for urn in sweep_page(a):
            step("delete-leftover", C.delete_post, url=C.permalink(urn), expect="Throwaway post")
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
        if ok and m:
            passed += 1
            step("delete-post", C.delete_post, url=m.group(1), expect="Throwaway post")
        else:
            failed += 1
            print("      no post URL to delete; check the Page for a leftover selftest post", flush=True)

    # ======================================================== PHASE 2: reading
    print("--- Phase 2: profiles, company, search, notifications, stats ---", flush=True)
    from . import people as P
    from . import search as Q
    from . import account as A

    pace = Pace()
    views_before = pace.count("view")

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
            ("degree is somebody else's", (r.get("degree") or "").lower() in DEGREES_NOT_SELF,
             repr(r.get("degree")))]
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
        ok, out = attempt("read-post chain", C.read_post, url=resolved[0]["permalink"])
        chain = _records(out)
        check("P2-6c", ok and bool(chain) and bool(chain[0].get("author")),
              "a resolved permalink fed to read-post returned author=%r"
              % (chain[0].get("author") if chain else None))
    else:
        check("P2-6c", False, "no resolved permalink to feed to read-post")

    # -- P2-7: notifications --------------------------------------------------
    ok, out = attempt("notifications", A.notifications, limit=10)
    recs = _records(out)
    check("P2-7", ok and len(recs) >= 1 and all((x.get("text") or "").strip() for x in recs),
          "rows=%d, every row has text=%s"
          % (len(recs), all((x.get("text") or "").strip() for x in recs)))

    # -- P2-8: the Page's analytics -------------------------------------------
    ok, out = attempt("stats", A.stats, page=a.page, page_name=a.page_name, days=30)
    recs = _records(out)
    r = recs[0] if recs else {}
    posts = r.get("posts") or []
    check("P2-8", ok and bool(recs)
          and isinstance(r.get("followers"), int)
          and r.get("name") == a.page_name
          and r.get("window_days") == 30
          and bool(r.get("window_start")) and bool(r.get("window_end"))
          and all(isinstance(p.get("impressions"), int) for p in posts),
          "followers=%r name matched=%s window=%rd (%s..%s) posts with integer impressions=%s"
          % (r.get("followers"), r.get("name") == a.page_name, r.get("window_days"),
             r.get("window_start"), r.get("window_end"),
             all(isinstance(p.get("impressions"), int) for p in posts)))

    # -- P2-9: the run left nothing behind, and cost what it should -----------
    from .browser import BrowserLock, open_file_dialogs, STATE_DIR
    views_after = Pace().count("view")
    took = views_after - views_before
    lock = os.path.join(STATE_DIR, "browser-%d.lock" % a.port)
    dialogs = open_file_dialogs()
    check("P2-9", took == EXPECTED_VIEWS and not os.path.exists(lock) and not dialogs,
          "views rose by %d (expected %d), lock released=%s, native dialogs=%d"
          % (took, EXPECTED_VIEWS, not os.path.exists(lock), len(dialogs)))

    print("RESULT selftest passed=%d failed=%d" % (passed, failed), flush=True)
    if failed:
        sys.exit(1)
