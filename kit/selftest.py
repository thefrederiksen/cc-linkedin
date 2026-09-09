# -*- coding: utf-8 -*-
"""The Phase 1 selftest: every verb, on things we own, leaving nothing behind.

    cc-linkedin selftest --post <Soren's post permalink> --page ID --page-name NAME

On the given post (one of ours): read it, comment, read the comments and see
the comment, reply, see the reply as its own row, react (Like), unreact,
delete the reply, delete the comment, read again and see neither.
On the Page: publish a throwaway text post, delete it, prove the permalink is
empty. Each step is a verb run exactly as a user would run it; a FAIL in any
step is counted and the run continues so one report shows everything.
"""
import argparse
import io
import os
import re
import sys
import tempfile
import time
from contextlib import redirect_stdout

from . import comments as C
from .browser import log


def _run(name, fn, **kw):
    """Run one verb, capture its output, return (ok, RESULT line or FAIL line)."""
    args = {"port": 9224, "expect": None, "text": None, "text_file": None}
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
    except Exception as exc:          # a verb crashed instead of failing cleanly: that is a bug, shown as one
        ok = False
        buf.write("FAIL %s: %s\n" % (type(exc).__name__, str(exc).splitlines()[0][:160]))
    out = buf.getvalue()
    line = next((l for l in out.splitlines() if l.startswith("RESULT") or l.startswith("FAIL")), out.strip().splitlines()[-1] if out.strip() else "(no output)")
    print("[%s] %-16s %-70s %s  (%.0fs)" % (time.strftime("%H:%M:%S"), name, line[:70], "ok" if ok else "FAIL", time.time() - t0), flush=True)
    return ok, out


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

    # -- the post we own -----------------------------------------------------
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

    # -- the Page: sweep leftovers, publish a throwaway post, delete it ------------
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
        print("[%s] %-16s %-70s %s  (%.0fs)" % (time.strftime("%H:%M:%S"), "post (page)", line[:70], "ok" if ok else "FAIL", time.time() - t0), flush=True)
        m = re.search(r"url=(\S+)", line)
        if ok and m:
            passed += 1
            step("delete-post", C.delete_post, url=m.group(1), expect="Throwaway post")
        else:
            failed += 1
            print("      no post URL to delete; check the Page for a leftover selftest post", flush=True)

    print("RESULT selftest passed=%d failed=%d" % (passed, failed), flush=True)
    if failed:
        sys.exit(1)
