# -*- coding: utf-8 -*-
"""The selftest: every verb, on things we own, leaving nothing behind.

    cc-linkedin selftest --post <a permalink of ours> --page ID --page-name NAME
                         --other-profile <a 1st- or 2nd-degree /in/ URL>

TWO BLOCKS, and the run does BOTH. Phase 1 writes: on a post of ours it
comments, replies, reacts, unreacts and deletes everything it made, and on the
Page it publishes a throwaway post and deletes it. Phase 2 only reads: a
profile, a second person's profile, a refusal, a company page, two searches,
the notifications page and the Page's analytics.

NOTHING IS SKIPPED. A fixture that is missing fails the run and says which one.
A verb quietly skipped is how a suite goes green over code that never ran, and
this file exists precisely to stop that - so there is deliberately no flag here
that runs "just the fast half".

THE ONE FIXTURE WITH NO DEFAULT IS --other-profile, and that is on purpose. This
repository is PUBLIC, so a second person's profile URL is never committed - not
in the code, not in the docs, not in an evidence file. It is passed at run time
and the evidence calls that person "profile B". Row P2-2 is the only row that
proves read-profile works on anybody other than its owner: on Soren's own
profile there is no Connect button, no degree badge and no Message button, so
without profile B half the record is never exercised at all.
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
from .browser import Pace, log

DEGREES_NOT_SELF = ("1st", "2nd", "3rd", "3rd+", "you")
STATES = ("Connect", "Pending", "Message", "Follow", "Following")
SOREN = "https://www.linkedin.com/in/sorenfrederiksen/"

# What one full Phase 2 block must cost on the view clock. read-profile costs
# one each (the refusal too - it navigates before it refuses), read-company one,
# each search one, and the two searches that share a query still open two pages.
# notifications and stats cost NOTHING: they are our own screens, not anybody's
# profile. Resolving a short link is a navigation to a post, not a profile view.
EXPECTED_VIEWS = 7


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
    if not a.other_profile:
        print("FAIL --other-profile is required. Row P2-2 is the only row that proves read-profile "
              "works on somebody other than its owner - Soren's own profile has no degree badge, no "
              "Connect button and no Message button - and this repository is public, so no second "
              "person's URL is committed as a default. Pass a 1st- or 2nd-degree profile URL.",
              flush=True)
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

    # -- P2-1: the owner's own profile ---------------------------------------
    ok, out = step("read-profile", P.read_profile, url=a.profile)
    recs = _records(out)
    r = recs[0] if recs else {}
    check("P2-1", ok and bool(recs)
          and "Soren Frederiksen" in (r.get("name") or "")
          and r.get("slug") == "sorenfrederiksen"
          and bool(r.get("headline"))
          and r.get("degree") == "self",
          "own profile: name=%r slug=%r headline=%s degree=%r"
          % (r.get("name"), r.get("slug"), bool(r.get("headline")), r.get("degree")))

    # -- P2-2: profile B, the only row that exercises the other half ----------
    want_b = (re.search(r"/in/([^/?#]+)", a.other_profile) or [None, a.other_profile.strip("/")])[1]
    ok, out = step("read-profile B", P.read_profile, url=a.other_profile)
    recs = _records(out)
    r = recs[0] if recs else {}
    check("P2-2", ok and bool(recs)
          and bool(r.get("name"))
          and (r.get("degree") or "").lower() in DEGREES_NOT_SELF
          and r.get("degree") != "self"
          and r.get("connection_state") in STATES
          and (r.get("slug") or "").lower() == want_b.lower(),
          "profile B: slug matched=%s degree=%r state=%r name present=%s"
          % ((r.get("slug") or "").lower() == want_b.lower(), r.get("degree"),
             r.get("connection_state"), bool(r.get("name"))))

    # -- P2-3: a deliberately wrong --expect must REFUSE ----------------------
    ok, out = step("read-profile X", P.read_profile, url=a.profile,
                   expect="Chief Marmalade Officer of Atlantis")
    check("P2-3", (not ok) and not _records(out) and "FAIL" in out,
          "wrong --expect refused: exited non-zero=%s, records printed=%d"
          % (not ok, len(_records(out))))

    # -- P2-4: the company page ----------------------------------------------
    ok, out = step("read-company", P.read_company, url=a.company)
    recs = _records(out)
    r = recs[0] if recs else {}
    check("P2-4", ok and bool(recs)
          and r.get("name") == "CenterConsulting, Inc."
          and isinstance(r.get("followers"), int) and r.get("followers") >= 1,
          "company: name=%r followers=%r" % (r.get("name"), r.get("followers")))

    # -- P2-5: people search --------------------------------------------------
    ok, out = step("search-people", Q.search_people, query=a.query_people, limit=5)
    recs = _records(out)
    check("P2-5", ok and bool(recs) and recs[0].get("url", "").rstrip("/") == SOREN.rstrip("/"),
          "first row url=%r" % (recs[0].get("url") if recs else None))

    # -- P2-6: content search, then the chain into Phase 1 --------------------
    ok, out = step("search-posts", Q.search_posts, query=a.query_posts, limit=5)
    recs = _records(out)
    check("P2-6a", ok and len(recs) >= 3
          and all(x.get("author") for x in recs)
          and all("lnkd.in" in (x.get("share_url") or "") for x in recs),
          "rows=%d, every row has an author and a lnkd.in share_url=%s"
          % (len(recs), all(x.get("author") and "lnkd.in" in (x.get("share_url") or "") for x in recs)))

    ok, out = step("search-posts -r", Q.search_posts, query=a.query_posts, limit=3, resolve=True)
    recs = _records(out)
    resolved = [x for x in recs if "urn:li:activity" in (x.get("permalink") or "")
                or re.search(r"urn:li:(activity|share|ugcPost):\d+", x.get("permalink") or "")]
    check("P2-6b", ok and len(recs) == 3 and len(resolved) == 3,
          "resolved %d of %d rows to a post urn" % (len(resolved), len(recs)))

    if resolved:
        ok, out = step("read-post chain", C.read_post, url=resolved[0]["permalink"])
        chain = _records(out)
        check("P2-6c", ok and bool(chain) and bool(chain[0].get("author")),
              "a resolved permalink fed to read-post returned author=%r"
              % (chain[0].get("author") if chain else None))
    else:
        check("P2-6c", False, "no resolved permalink to feed to read-post")

    # -- P2-7: notifications --------------------------------------------------
    ok, out = step("notifications", A.notifications, limit=10)
    recs = _records(out)
    check("P2-7", ok and len(recs) >= 1 and all((x.get("text") or "").strip() for x in recs),
          "rows=%d, every row has text=%s"
          % (len(recs), all((x.get("text") or "").strip() for x in recs)))

    # -- P2-8: the Page's analytics -------------------------------------------
    ok, out = step("stats", A.stats, page=a.page, page_name=a.page_name, days=30)
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
