# -*- coding: utf-8 -*-
r"""cc-linkedin: post to a LinkedIn Page through your own signed-in browser.

    cc-linkedin post      --page ID --page-name NAME --text FILE [--media FILE ...]
                          [--schedule "YYYY-MM-DD HH:MM"] [--submit] [--shot PNG] [--port N]
    cc-linkedin scheduled  --page ID --page-name NAME [--port N]
    cc-linkedin unschedule --page ID --page-name NAME --match "opening words" [--port N]

It drives a Chrome that is ALREADY RUNNING and ALREADY SIGNED IN, over its remote
debugging port, using Playwright as a library. No new browser, no login, no API.
The flow is the human flow: open the composer, attach the file, type the text,
press Post (or pick a date and time and press Schedule).

Every step is followed by a PRESENCE check that names what it expects to see.
A missing thing is a failed run, never a skipped step. Without --submit the post
is staged, screenshotted and then DISCARDED, and that is the recommended first
run for any new text or media: it exercises everything except the final press.

Output contract (for callers):
    RESULT staged file=... shot=... seconds=N
    RESULT posted file=... urn=urn:li:activity:N url=... seconds=N
    RESULT scheduled file=... when="..." seconds=N
    RESULT already-posted file=...
    FAIL <reason>            exit 1, composer discarded, tab closed, nothing left

MEASURED ON THE LIVE PAGE, 2026-09-09 (every rule below was watched failing first)
  * `?share=true` on the page-posts admin URL opens the composer directly, as the
    Page. Identity is still checked: the dialog must name the page.
  * "Add media" opens an in-page Editor with exactly ONE file input
    (id media-editor-file-selector__file-input). The file is set on that input.
    "Upload from computer" is NEVER clicked: it opens a native OS dialog that no
    browser automation can close.
  * Media FIRST, text second. Leaving the media editor remounts the text editor.
  * Text goes in as insertText runs with one Enter per newline. One insertText
    with newlines inside multiplies them.
  * A Page keeps ONE server-side draft per admin and offers it back into the
    next composer. A composer that opens non-empty is discarded and reopened
    once; twice means something is wrong and the run stops.
  * THE VIDEO IS UPLOADED AFTER THE POST CLICK, from inside the page. Navigating
    away kills it and nothing is posted. The published list does not update
    live either. So: wait for the upload traffic to finish, THEN reload.
  * Dismiss and Discard are pressed with the KEYBOARD (focus + Enter). The
    prompt's Discard button sits exactly over the admin page's Photo button; a
    mouse click that lands after the prompt is gone opens Photo's native file
    chooser. A keystroke cannot fall through.
  * Some videos leave inert role=dialog shells behind (the player's modal). A
    live dialog is one holding a Dismiss, Discard, Post or Schedule button.
  * The working tab is created in the BACKGROUND so the person using the browser
    is not interrupted. A background tab cannot be screenshotted; the final
    screenshot brings it to the front.
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import datetime
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout, Error as PWError

from kit.browser import BrowserLock

VIDEO_EXT = (".mp4", ".mov", ".webm", ".avi", ".m4v", ".mpeg", ".mpg", ".wmv", ".flv")
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp")
FILE_INPUT = "input#media-editor-file-selector__file-input"
LIVE_BUTTON = re.compile(r"^(Dismiss|Discard|Post|Schedule)$")


def log(msg):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


def die(msg):
    print("FAIL " + msg, flush=True)
    sys.exit(1)


def needle(text):
    """The opening words of the text, used to find the post on the page afterwards."""
    return text.split("\n")[0].strip().strip('"')[:60]


# ---------------------------------------------------------------- native dialogs

def open_file_dialogs():
    """Handles of visible native 'Open' file dialogs on this desktop (Windows)."""
    if not hasattr(ctypes, "windll"):
        return []
    user32 = ctypes.windll.user32
    found = []
    proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)

    def cb(h, _):
        if not user32.IsWindowVisible(h):
            return True
        cls = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(h, cls, 64)
        if cls.value != "#32770":
            return True
        title = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(h, title, 256)
        if title.value == "Open":
            found.append(int(h))
        return True

    user32.EnumWindows(proc(cb), 0)
    return found


def close_file_dialogs(where):
    """Cancel any native 'Open' dialog (WM_CLOSE) and name the step that spawned it.

    Clean-up, not a fix: a run that spawned one still FAILS, because a chooser
    means a click landed on something that opens one, and that click is a bug.
    """
    handles = open_file_dialogs()
    for h in handles:
        ctypes.windll.user32.SendMessageW(h, 0x0010, 0, 0)
    if handles:
        log("NATIVE OPEN DIALOG appeared after %s (hwnd %s); cancelled it" % (where, handles))
    return handles


# ---------------------------------------------------------------- page helpers

ENUM_INPUTS = """() => {
  const walk = (root, acc) => {
    for (const el of root.querySelectorAll('*')) {
      if (el.tagName === 'INPUT' && el.type === 'file') acc.push({id: el.id, accept: el.accept});
      if (el.shadowRoot) walk(el.shadowRoot, acc);
    }
    return acc;
  };
  return walk(document, []);
}"""

EDITOR_TEXT = """() => {
  const ed = document.querySelector('.share-creation-state .ql-editor');
  if (!ed) return null;
  return [...ed.querySelectorAll('p')].map(p => p.textContent).join(String.fromCharCode(10));
}"""

DIALOG_TEXT = "() => { const d = document.querySelector('[role=dialog]'); return d ? d.innerText : null; }"

FIND_CARD = """(first) => {
  for (const card of document.querySelectorAll('[data-urn], [data-id]')) {
    if ((card.innerText || '').includes(first))
      return card.getAttribute('data-urn') || card.getAttribute('data-id');
  }
  return null;
}"""


class Page(object):
    """One LinkedIn Page admin, driven through one background tab."""

    def __init__(self, browser, page_id, page_name, shot):
        self.browser = browser
        self.page_id = page_id
        self.page_name = page_name
        self.shot = shot
        self.admin = "https://www.linkedin.com/company/%s/admin/page-posts/published/" % page_id
        ctx = browser.contexts[0]
        # Background target: ctx.new_page() would become the active tab in the
        # user's window and interrupt them.
        root = browser.new_browser_cdp_session()
        with ctx.expect_page(timeout=15000) as opened:
            root.send("Target.createTarget", {"url": "about:blank", "background": True})
        self.page = opened.value

    # -- state -------------------------------------------------------------

    def buttons(self):
        return self.page.evaluate("""() => [...document.querySelectorAll('[role=dialog] button')]
            .map(b => (b.getAttribute('aria-label') || b.innerText || '').trim()).filter(Boolean)""")

    def composer_open(self):
        return self.page.locator(".share-creation-state").count() > 0

    def live_dialog(self):
        return self.page.locator("[role=dialog]").filter(
            has=self.page.get_by_role("button", name=LIVE_BUTTON))

    def editor_text(self):
        return self.page.evaluate(EDITOR_TEXT) or ""

    def dialog(self):
        return self.page.locator("[role=dialog]")

    def has_button(self, name):
        return self.dialog().get_by_role("button", name=name, exact=True).count() > 0

    # -- composer ----------------------------------------------------------

    def open_composer(self):
        self.page.goto(self.admin + "?share=true", wait_until="domcontentloaded", timeout=60000)
        self.page.wait_for_selector(".share-creation-state .ql-editor", timeout=45000)
        time.sleep(2)
        header = self.page.evaluate(DIALOG_TEXT) or ""
        if self.page_name not in header:
            die("the composer does not name %r. It began: %r. Refusing to post as the wrong "
                "identity." % (self.page_name, header[:120]))
        log("composer open as %s" % self.page_name)

    def ensure_empty_composer(self):
        """Open the composer and prove it is empty, discarding one restored draft."""
        self.open_composer()
        for attempt in (1, 2):
            body = self.editor_text().strip()
            media = [b for b in ("Remove media", "Play") if self.has_button(b)]
            if not body and not media:
                log("composer is empty")
                return
            if attempt == 2:
                die("composer is still not empty after discarding the restored draft "
                    "(%d chars, media: %s)" % (len(body), media or "none"))
            log("composer restored a draft (%d chars, media: %s); discarding it" % (len(body), media or "none"))
            self.discard("restored draft")
            self.open_composer()

    def press(self, locator, what):
        """Activate a button with the keyboard. See the module header on why."""
        locator.focus()
        self.page.keyboard.press("Enter")
        log("%s pressed" % what)
        if close_file_dialogs(what):
            die("%s spawned a native file dialog" % what)

    def discard(self, why):
        """Dismiss the composer and choose Discard. Proven by the composer being
        gone and the page's own 'Start a post' box being back."""
        log("discarding composer (%s)" % why)
        if self.live_dialog().count() == 0 and not self.composer_open():
            return
        had_content = bool(self.editor_text().strip()) or self.has_button("Remove media")
        dismiss = self.page.locator("[role=dialog] button[aria-label='Dismiss']")
        if dismiss.count() == 0:
            die("composer is open but has no Dismiss button; buttons=%s" % self.buttons()[:12])
        self.press(dismiss.first, "Dismiss")
        choice = self.page.get_by_role("button", name="Discard", exact=True)
        # An empty composer closes without a "save as draft?" prompt, so only a
        # composer with content is worth waiting on for one.
        try:
            choice.first.wait_for(state="visible", timeout=8000 if had_content else 2500)
            self.press(choice.first, "Discard")
        except PWTimeout:
            log("no Discard prompt appeared; buttons=%s" % self.buttons()[:12])
        try:
            self.page.locator(".share-creation-state").wait_for(state="detached", timeout=8000)
            self.page.get_by_role("button", name="Start a post").first.wait_for(state="visible", timeout=8000)
        except PWTimeout:
            die("composer still open after Dismiss + Discard; buttons=%s" % self.buttons()[:12])
        if self.live_dialog().count():
            die("a live dialog remains after discard: %s" % self.buttons()[:12])
        log("composer discarded, nothing kept")

    # -- media -------------------------------------------------------------

    def attach(self, files):
        names = [os.path.basename(f) for f in files]
        is_video = names[0].lower().endswith(VIDEO_EXT)
        self.page.locator(".share-creation-state button[aria-label='Add media']").click(timeout=10000)
        self.page.wait_for_selector(FILE_INPUT, state="attached", timeout=20000)
        inputs = self.page.evaluate(ENUM_INPUTS)
        if len(inputs) != 1:
            die("expected exactly one file input in the media editor, found %r" % inputs)
        accept = inputs[0]["accept"]
        for n in names:
            ext = os.path.splitext(n)[1].lower()
            if ext == ".mp4" and "video/mp4" not in accept:
                die("the file input does not accept video/mp4: %r" % accept)
            if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp") and "image/" not in accept:
                die("the file input does not accept images: %r" % accept)
        self.page.locator(FILE_INPUT).set_input_files(files)
        log("file set: %s (%.1f MB)" % (", ".join(names), sum(os.path.getsize(f) for f in files) / 1048576.0))
        # proof the editor took THESE files: a control named after each, and Next enabled
        for n in names:
            self.page.wait_for_selector("[role=dialog] [aria-label*='%s']" % n.replace("'", "\\'"),
                                        timeout=180000)
        nxt = "[role=dialog] button:has-text('Next'):not([disabled])"
        self.page.wait_for_selector(nxt, timeout=60000)
        log("media editor shows %s, Next enabled" % ", ".join(names))
        self.page.locator(nxt).click(timeout=10000)
        self.page.wait_for_selector(".share-creation-state .ql-editor", timeout=45000)
        self.dialog().get_by_role("button", name="Remove media", exact=True).first.wait_for(timeout=60000)
        if is_video:
            self.dialog().get_by_role("button", name="Play", exact=True).first.wait_for(timeout=60000)
        log("media attached in composer (Remove media%s)" % (" + Play" if is_video else ""))
        return is_video

    def media_still_attached(self):
        return self.has_button("Remove media")

    # -- text --------------------------------------------------------------

    def type_text(self, text):
        editor = self.page.locator(".share-creation-state .ql-editor")
        editor.click(timeout=10000)
        for run in re.split(r"(\n+)", text):
            if not run:
                continue
            if run[0] == "\n":
                for _ in range(len(run)):
                    self.page.keyboard.press("Enter")
            else:
                self.page.keyboard.insert_text(run)
        time.sleep(1.5)
        got = self.editor_text().strip()
        if got != text:
            with open(self.shot + ".mismatch.txt", "w", encoding="utf-8") as f:
                f.write("WANT\n%s\n\nGOT\n%s\n" % (text, got))
            die("text in the composer does not match the file (%d vs %d chars); wrote %s.mismatch.txt"
                % (len(got), len(text), self.shot))
        log("text verified: %d chars, exact" % len(text))

    # -- schedule ----------------------------------------------------------

    def set_schedule(self, when):
        """Fill the Schedule dialog. `when` is a naive local datetime.

        Proven by reading both fields back and by the composer's primary button
        turning into 'Schedule'.
        """
        self.page.locator(".share-creation-state button[aria-label='Schedule post']").click(timeout=10000)
        date_box = self.page.locator("#share-post__scheduled-date")
        time_box = self.page.locator("#share-post__scheduled-time")
        date_box.wait_for(state="visible", timeout=15000)
        want_date = "%d/%d/%d" % (when.month, when.day, when.year)
        want_time = when.strftime("%I:%M %p").lstrip("0")
        # The date box is an artdeco datepicker: typed text is thrown away, the
        # calendar's own day buttons are the control. Their accessible names are
        # "Thursday, September 10, 2026." plus any state suffix.
        date_box.click()
        day_name = "%s, %s %d, %d." % (when.strftime("%A"), when.strftime("%B"), when.day, when.year)
        day = self.dialog().get_by_role("button", name=re.compile("^" + re.escape(day_name)))
        for _ in range(4):
            if day.count():
                break
            self.dialog().get_by_role("button", name="Next month", exact=True).first.click(timeout=10000)
            time.sleep(0.5)
        if day.count() != 1:
            die("calendar has no day named %r (is it more than three months out?)" % day_name)
        day.first.click(timeout=10000)
        time.sleep(0.5)
        time_box.click()
        self.page.keyboard.press("Control+A")
        self.page.keyboard.insert_text(want_time)
        self.page.keyboard.press("Tab")
        time.sleep(1)
        got_date, got_time = date_box.input_value(), time_box.input_value()
        if got_date != want_date or got_time != want_time:
            die("schedule fields read back %r %r, wanted %r %r" % (got_date, got_time, want_date, want_time))
        log("schedule set to %s %s" % (got_date, got_time))
        nxt = self.dialog().get_by_role("button", name="Next", exact=True)
        nxt.first.click(timeout=10000)
        try:
            self.page.locator(".share-creation-state").get_by_role(
                "button", name="Schedule", exact=True).wait_for(state="visible", timeout=15000)
        except PWTimeout:
            die("after Next the composer shows no Schedule button; buttons=%s" % self.buttons()[:14])
        log("composer primary button is now Schedule")

    # -- scheduled posts dialog ---------------------------------------------
    # Scheduled posts have no URL of their own. They are listed in a dialog
    # reached from an open composer: Schedule post -> "View all scheduled
    # posts". Each row is a preview button plus an "Actions menu for scheduled
    # post on <date>" button whose menu holds Post now / Modify schedule /
    # Edit post / Delete post.

    SCHED_ROWS = """() => {
      const NL = String.fromCharCode(10);
      const dlg = [...document.querySelectorAll('[role=dialog]')].find(d => /scheduled posts/i.test(d.innerText));
      if (!dlg) return null;
      const menus = [...dlg.querySelectorAll('button[aria-label^="Actions menu for scheduled post"]')];
      return menus.map((m, i) => {
        const row = m.closest('li') || m.parentElement.parentElement;
        return {index: i, when: m.getAttribute('aria-label').replace(/^Actions menu for scheduled post on /, ''),
                text: (row.innerText || '').split(NL).map(s => s.trim()).filter(Boolean).join(' | ')};
      });
    }"""

    def open_scheduled_dialog(self):
        self.open_composer()
        self.page.locator(".share-creation-state button[aria-label='Schedule post']").click(timeout=10000)
        view = self.page.get_by_role("button", name="View all scheduled posts")
        view.first.wait_for(state="visible", timeout=15000)
        view.first.click(timeout=10000)
        deadline = time.time() + 20
        while time.time() < deadline:
            rows = self.page.evaluate(self.SCHED_ROWS)
            if rows is not None:
                time.sleep(1.5)
                return self.page.evaluate(self.SCHED_ROWS)
            time.sleep(0.5)
        die("the scheduled-posts dialog did not open; buttons=%s" % self.buttons()[:12])

    def close_scheduled_dialog(self):
        """Back to the composer, then discard the (empty) composer."""
        back = self.page.get_by_role("button", name="Back to post creation")
        if back.count():
            self.press(back.first, "Back to post creation")
            time.sleep(1)
        back2 = self.dialog().get_by_role("button", name="Back", exact=True)
        if back2.count():
            self.press(back2.first, "Back")
            time.sleep(1)
        self.discard("closing the scheduled-posts view")

    # -- submit ------------------------------------------------------------

    def submit(self, label, first):
        """Press Post or Schedule, wait for the page's upload traffic to finish."""
        pending = {}

        def is_upload(r):
            return r.method in ("PUT", "POST") and ("upload" in r.url.lower() or "dms-uploads" in r.url)

        self.page.on("request", lambda r: pending.__setitem__(id(r), time.time()) if is_upload(r) else None)
        self.page.on("requestfinished", lambda r: pending.pop(id(r), None))
        self.page.on("requestfailed", lambda r: pending.pop(id(r), None))
        btn = self.page.locator(".share-creation-state").get_by_role("button", name=label, exact=True)
        if btn.count() != 1:
            die("expected one %s button, found %d" % (label, btn.count()))
        btn.first.click(timeout=10000)
        clicked = time.time()
        log("%s clicked" % label)
        self.page.wait_for_selector(".share-creation-state", state="detached", timeout=90000)
        log("composer closed; waiting for the page to finish uploading")
        quiet_since = time.time()
        while time.time() - clicked < 600:
            # A request "pending" for two minutes is a long poll that happened
            # to match, not an upload; it must not hold the run (one run sat
            # ten minutes on such a request, 2026-09-09 14:45).
            live = [t for t in pending.values() if time.time() - t < 120]
            if live:
                quiet_since = time.time()
            elif time.time() - quiet_since >= 15 and time.time() - clicked >= 20:
                break
            time.sleep(1)
        log("upload traffic finished (%.0fs after %s)" % (time.time() - clicked, label))

    def find_post(self, url, first, minutes):
        deadline = time.time() + minutes * 60
        while time.time() < deadline:
            self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(5)
            urn = self.page.evaluate(FIND_CARD, first)
            if urn:
                return urn
            time.sleep(10)
        return None

    def screenshot(self, path):
        self.page.bring_to_front()
        time.sleep(1)
        self.page.screenshot(path=path)

    def close(self):
        self.page.close()


# ---------------------------------------------------------------- commands

_LOCK = None


def connect(p, port):
    """Attach to Chrome, holding the one-run-per-browser lock for the rest of
    the process. Two Playwright clients on one Chrome block each other's
    navigations (measured 2026-09-09 14:34), so a second run waits its turn."""
    global _LOCK
    _LOCK = BrowserLock(port)
    _LOCK.__enter__()
    try:
        return p.chromium.connect_over_cdp("http://localhost:%d" % port, timeout=15000)
    except PWError as exc:
        release()
        die("no Chrome is listening on port %d (%s). Start the signed-in profile first, "
            "e.g. bh-profiles.ps1 up cencon" % (port, str(exc).splitlines()[0]))


def release():
    """Give the browser back. Called whenever a session ends, so a caller that
    runs several commands in one process (the selftest) does not wait on a
    lock its own process holds (that stall cost 462s on 2026-09-09)."""
    global _LOCK
    if _LOCK is not None:
        _LOCK.__exit__(None, None, None)
        _LOCK = None


def cmd_post(a):
    files = [os.path.abspath(f) for f in (a.media or [])]
    for f in files:
        if not os.path.isfile(f):
            die("media not found: " + f)
    kinds = {("video" if f.lower().endswith(VIDEO_EXT) else "image" if f.lower().endswith(IMAGE_EXT) else "?")
             for f in files}
    if "?" in kinds:
        die("media must be video (%s) or images (%s)" % (", ".join(VIDEO_EXT), ", ".join(IMAGE_EXT)))
    if kinds == {"video", "image"} or (kinds == {"video"} and len(files) > 1):
        die("one video alone, or up to 20 images; not both")
    text = open(a.text, encoding="utf-8").read().strip()
    if not text:
        die("text file is empty")
    if len(text) > 3000:
        die("text is %d chars; the limit is 3000" % len(text))
    first = needle(text)
    if not first:
        die("text has no opening line to verify the post by")
    when = None
    if a.schedule:
        try:
            when = datetime.datetime.strptime(a.schedule, "%Y-%m-%d %H:%M")
        except ValueError:
            die("--schedule must be 'YYYY-MM-DD HH:MM' in the browser's local time")
        if when < datetime.datetime.now() + datetime.timedelta(minutes=30):
            die("--schedule must be at least 30 minutes from now")
        if when.minute % 15:
            die("--schedule minutes must be a multiple of 15 (LinkedIn's grid)")
    if open_file_dialogs():
        die("a native 'Open' file dialog is already on screen; close it first")
    base = ", ".join(os.path.basename(f) for f in files) or "-"
    t0 = time.time()
    with sync_playwright() as p:
        browser = connect(p, a.port)
        lp = Page(browser, a.page, a.page_name, a.shot or "cc-linkedin")
        ok = False
        try:
            lp.ensure_empty_composer()
            if first in (lp.page.evaluate("() => document.body.innerText") or ""):
                lp.discard("post already on the page")
                print("RESULT already-posted file=%s" % base)
                ok = True
                return
            if files:
                lp.attach(files)
            lp.type_text(text)
            if files and not lp.media_still_attached():
                die("media is no longer attached after typing")
            if when:
                lp.set_schedule(when)
            if not a.submit:
                if a.shot:
                    lp.screenshot(a.shot)
                lp.discard("staged only, no --submit")
                print("RESULT staged file=%s shot=%s seconds=%.0f" % (base, a.shot or "-", time.time() - t0))
                ok = True
                return
            if when:
                lp.submit("Schedule", first)
                rows = lp.open_scheduled_dialog()
                hit = [r for r in rows if first in r["text"]]
                if len(hit) != 1:
                    die("Schedule was clicked but the scheduled-posts list holds %d posts beginning %r"
                        % (len(hit), first))
                log("scheduled post is listed: %s" % hit[0]["when"])
                lp.close_scheduled_dialog()
                print("RESULT scheduled file=%s when=\"%s\" listed=\"%s\" seconds=%.0f"
                      % (base, when.strftime("%Y-%m-%d %H:%M"), hit[0]["when"], time.time() - t0))
            else:
                lp.submit("Post", first)
                urn = lp.find_post(lp.admin, first, 5)
                if not urn:
                    die("Post was clicked and the upload finished, but no post beginning %r is on "
                        "the published list after 5 minutes" % first)
                log("post is on the page: %s" % urn)
                print("RESULT posted file=%s urn=%s url=https://www.linkedin.com/feed/update/%s/ seconds=%.0f"
                      % (base, urn, urn, time.time() - t0))
            ok = True
            if a.shot:
                lp.screenshot(a.shot)
        except PWTimeout as exc:
            log("timeout: %s" % str(exc).splitlines()[0])
            log("buttons visible: %s" % lp.buttons()[:14])
            shot = (a.shot or "cc-linkedin") + ".fail.png"
            try:
                lp.screenshot(shot)
            except Exception:
                pass
            die("timed out; see %s" % shot)
        finally:
            if not ok:
                try:
                    if lp.composer_open() or lp.live_dialog().count():
                        lp.discard("clearing up after failure")
                except SystemExit:
                    raise
                except Exception as exc:
                    log("could not clear up: %s" % exc)
            if ok and a.submit and not when and getattr(a, "keep_tab", True):
                log("leaving the tab open on the published post so it can be seen")
            else:
                lp.close()
            browser.close()
            release()
            if close_file_dialogs("the run"):
                die("a native 'Open' file dialog was spawned during the run; cancelled it")


def cmd_scheduled(a):
    with sync_playwright() as p:
        browser = connect(p, a.port)
        lp = Page(browser, a.page, a.page_name, "")
        try:
            rows = lp.open_scheduled_dialog()
            if not rows:
                print("no scheduled posts")
            for r in rows:
                print("%s  %s" % (r["when"], r["text"][:200]))
            lp.close_scheduled_dialog()
        finally:
            lp.close()
            browser.close()
            release()


def cmd_unschedule(a):
    with sync_playwright() as p:
        browser = connect(p, a.port)
        lp = Page(browser, a.page, a.page_name, "")
        try:
            rows = lp.open_scheduled_dialog()
            hit = [r for r in rows if a.match in r["text"]]
            if len(hit) != 1:
                die("expected exactly one scheduled post containing %r, found %d" % (a.match, len(hit)))
            when = hit[0]["when"]
            menu = lp.page.get_by_role("button", name="Actions menu for scheduled post on " + when, exact=True)
            if menu.count() != 1:
                die("expected one actions menu for %r, found %d" % (when, menu.count()))
            menu.first.click(timeout=10000)
            item = lp.page.get_by_role("button", name="Delete post", exact=True)
            if item.count() == 0:
                item = lp.page.get_by_text("Delete post", exact=True)
            item.first.wait_for(state="visible", timeout=10000)
            item.first.click(timeout=10000)
            confirm = lp.page.get_by_role("button", name=re.compile(r"^Delete( post)?$"))
            confirm.first.wait_for(state="visible", timeout=10000)
            lp.press(confirm.first, "Delete (confirm)")
            deadline = time.time() + 20
            while time.time() < deadline:
                rows = lp.page.evaluate(lp.SCHED_ROWS) or []
                if not [r for r in rows if a.match in r["text"]]:
                    break
                time.sleep(1)
            else:
                die("the scheduled post %r is still listed after Delete" % when)
            log("scheduled post for %s is gone from the list" % when)
            lp.close_scheduled_dialog()
            print("RESULT unscheduled when=\"%s\"" % when)
        finally:
            lp.close()
            browser.close()
            release()


def main():
    ap = argparse.ArgumentParser(prog="cc-linkedin", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--page", required=True, help="LinkedIn Page (organization) numeric id")
        sp.add_argument("--port", type=int, default=9224, help="Chrome remote debugging port (default 9224)")

    sp = sub.add_parser("post", help="stage, post, or schedule a post")
    common(sp)
    sp.add_argument("--page-name", required=True, help="exact Page name the composer must show")
    sp.add_argument("--text", required=True, help="UTF-8 text file, <= 3000 chars")
    sp.add_argument("--media", action="append", help="one video, or repeat for up to 20 images")
    sp.add_argument("--schedule", help="'YYYY-MM-DD HH:MM' local time, 15-minute grid")
    sp.add_argument("--submit", action="store_true", help="press Post/Schedule. Default stages and discards.")
    sp.add_argument("--shot", help="write a screenshot here (brings the tab to the front for it)")
    sp.set_defaults(fn=cmd_post)

    sp = sub.add_parser("scheduled", help="list the Page's scheduled posts")
    common(sp)
    sp.add_argument("--page-name", required=True, help="exact Page name the composer must show")
    sp.set_defaults(fn=cmd_scheduled)

    sp = sub.add_parser("unschedule", help="delete one scheduled post")
    common(sp)
    sp.add_argument("--page-name", required=True, help="exact Page name the composer must show")
    sp.add_argument("--match", required=True, help="words that appear in exactly one scheduled post")
    sp.set_defaults(fn=cmd_unschedule)

    # -- Phase 1: comments and reactions (kit/comments.py) --------------------
    from kit import comments as C

    def post_verb(name, fn, help_, text=False, expect=True, extra=None):
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("url", help="post permalink (contains urn:li:activity:...)")
        sp.add_argument("--port", type=int, default=9224)
        if expect:
            sp.add_argument("--expect", help="a phrase that must be in the post, or the verb refuses")
        if text:
            sp.add_argument("--text", help="the text")
            sp.add_argument("--text-file", help="UTF-8 file holding the text")
        for args, kw in (extra or []):
            sp.add_argument(*args, **kw)
        sp.set_defaults(fn=fn)

    post_verb("read-post", C.read_post, "print a post as JSON", expect=False)
    post_verb("read-comments", C.read_comments, "print every comment as JSON, one per line", expect=False)
    post_verb("comment", C.comment, "comment on a post", text=True)
    post_verb("reply", C.reply, "reply to one comment", text=True,
              extra=[(("--to",), {"required": True, "help": "words that appear in exactly one comment"})])
    post_verb("delete-comment", C.delete_comment, "delete one of our comments", expect=False,
              extra=[(("--match",), {"required": True, "help": "words that appear in exactly one comment"})])
    post_verb("react", C.react, "react to a post",
              extra=[(("--kind",), {"default": "like", "help": "like, celebrate, support, love, insightful, funny"})])
    post_verb("unreact", C.unreact, "remove our reaction", expect=False)
    post_verb("delete-post", C.delete_post, "delete one of our posts")

    # -- Phase 2: reading people, companies, search, notifications, stats ----
    from kit import people as P

    sp = sub.add_parser("read-profile", help="print one person's profile as JSON")
    sp.add_argument("url", help="a /in/ profile URL, or just the slug")
    sp.add_argument("--expect", help="a phrase that must appear in the top card, or the verb refuses")
    sp.add_argument("--port", type=int, default=9224)
    sp.set_defaults(fn=P.read_profile)

    sp = sub.add_parser("read-company", help="print one company page as JSON")
    sp.add_argument("url", help="a /company/ URL, or just the slug")
    sp.add_argument("--port", type=int, default=9224)
    sp.set_defaults(fn=P.read_company)

    from kit import search as Q

    sp = sub.add_parser("search-people", help="search people, print each result as JSON")
    sp.add_argument("query", help="what to search for")
    sp.add_argument("--company", help="narrow to a current company")
    sp.add_argument("--title", help="narrow to a job title")
    sp.add_argument("--location", help="narrow to a location")
    sp.add_argument("--limit", type=int, default=25, help="rows to return (hard cap 100)")
    sp.add_argument("--port", type=int, default=9224)
    sp.set_defaults(fn=Q.search_people)

    sp = sub.add_parser(
        "search-posts", help="search posts, print each result as JSON",
        description="Search posts and print each result as JSON. "
                    "SIDE EFFECT, STATED BECAUSE IT IS ONE (ruling R16, 2026-09-09): a "
                    "content-search card carries no post address anywhere in its DOM, so this "
                    "verb takes each one the way a person does - it opens the card's control "
                    "menu and presses 'Copy link to post', which writes to YOUR SYSTEM "
                    "CLIPBOARD. Whatever was on the clipboard is read first and put back "
                    "afterwards, and the RESULT line says whether that worked. Clipboard "
                    "contents this tool cannot read as text - an image, a file - cannot be "
                    "restored, and the run says so rather than pretending otherwise. The "
                    "clipboard permission it grants the browser is a temporary override and is "
                    "reset before the command exits.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sp.add_argument("query", help="what to search for")
    sp.add_argument("--limit", type=int, default=25, help="rows to return (hard cap 100)")
    sp.add_argument("--resolve", action="store_true",
                    help="follow each short link in the browser to fill permalink (capped at 10 rows)")
    sp.add_argument("--port", type=int, default=9224)
    sp.set_defaults(fn=Q.search_posts)

    from kit import account as A

    sp = sub.add_parser("notifications", help="print the notifications page as JSON, one row per line")
    sp.add_argument("--limit", type=int, default=25)
    sp.add_argument("--port", type=int, default=9224)
    sp.set_defaults(fn=A.notifications)

    sp = sub.add_parser("stats", help="print a Page's own analytics as JSON")
    sp.add_argument("--page", required=True, help="LinkedIn Page (organization) numeric id")
    sp.add_argument("--page-name", help="exact Page name the analytics screen must show")
    sp.add_argument("--days", type=int, default=30,
                    help="window to drive the control to: 7, 15 or 30. 0 reports the window on screen.")
    sp.add_argument("--port", type=int, default=9224)
    sp.set_defaults(fn=A.stats)

    # -- Phase 3: the invitations we sent ------------------------------------
    from kit import connections as N

    sp = sub.add_parser(
        "withdraw", help="withdraw one invitation we sent",
        description="Withdraw ONE outstanding invitation, from the invitation manager's "
                    "Sent tab. Staged by default: without --submit it finds the row, names "
                    "the person twice, reports the age the page displays, and presses "
                    "NOTHING. "
                    "IT SPENDS SOMETHING THAT CANNOT BE GOT BACK: LinkedIn restricts "
                    "inviting the same person again after a withdrawal, and the RESULT line "
                    "carries what the live surface said about that - including saying that "
                    "it said nothing, which is what was measured on 2026-09-10. "
                    "The control is an ANCHOR whose href is the feed, so a click the page "
                    "does not swallow navigates away and withdraws nothing, silently; this "
                    "verb asserts afterwards that it is still on the invitation manager and "
                    "that the list is exactly one shorter with the page's own count "
                    "agreeing.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sp.add_argument("url", help="the person's profile URL, or just the /in/ slug")
    sp.add_argument("--expect-name", help="the person's name as the withdraw control states "
                                          "it. REQUIRED with --submit (design rule 0.3).")
    sp.add_argument("--older-than-months", type=int,
                    help="refuse unless the age the page DISPLAYS proves at least this many "
                         "whole months. LinkedIn rounds down, so '3 months ago' proves three "
                         "and an age this cannot parse refuses rather than guesses.")
    sp.add_argument("--submit", action="store_true",
                    help="actually withdraw it. Default stages and presses nothing.")
    sp.add_argument("--dump", help="write everything the run measured to this JSON file")
    sp.add_argument("--port", type=int, default=9224)
    sp.set_defaults(fn=N.withdraw)

    # -- Phase 3: reaching people -------------------------------------------
    from kit import messaging as M

    sp = sub.add_parser(
        "connect", help="send one person an invitation to connect",
        description="Send ONE invitation. STAGED BY DEFAULT: without --submit it opens the "
                    "person's profile, finds the invitation wherever it lives, opens the "
                    "invitation page, types the note, and then PROVES NOTHING HAPPENED - it "
                    "dismisses, re-reads the profile from scratch and re-reads the "
                    "invitation manager, and both must still agree that no invitation "
                    "exists. "
                    "THE NOTE LIMIT IS READ OFF THE PAGE, never remembered: LinkedIn states "
                    "it (300 characters on 2026-09-10) and the textarea carries NO maxlength, "
                    "so the browser does not enforce it and a longer note is cut or rejected "
                    "at the one moment nobody can see. "
                    "The invitation control is an <a> named 'Invite <Name> to connect' - the "
                    "word Connect identifies nothing on a profile page - and this verb uses "
                    "read-profile's own resolver rather than hunting for a word. "
                    "It refuses if an invitation is already pending, and it counts against "
                    "TWO caps: 20 a day and 100 in any rolling seven days.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sp.add_argument("url", help="the person's profile URL, or just the /in/ slug")
    sp.add_argument("--note", help="a personal note. The page states the limit and this "
                                   "verb enforces what the page says.")
    sp.add_argument("--note-file", help="UTF-8 file holding the note")
    sp.add_argument("--expect-name", help="the person's name as their top card states it. "
                                          "REQUIRED with --submit (design rule 0.3), and "
                                          "checked against the profile AND against the "
                                          "invitation dialog, which names them again.")
    sp.add_argument("--submit", action="store_true",
                    help="actually send it. Default stages and sends nothing.")
    sp.add_argument("--dump", help="write everything the run measured to this JSON file")
    sp.add_argument("--port", type=int, default=9224)
    sp.set_defaults(fn=N.connect)

    sp = sub.add_parser(
        "invitations", help="print the invitations OTHER PEOPLE have sent us",
        description="The invitation manager's Received tab, as JSON, one row per line. "
                    "READ-ONLY IN FACT: this verb presses nothing, and the two controls on "
                    "that page which change another person's world - Accept and Ignore - are "
                    "out of scope for Phase 3. "
                    "The count the page publishes is a PER-FILTER PILL ('Focused (1)'), not "
                    "a sentence, so the parse is checked against the pill of the SAME filter "
                    "whose rows are on screen; if that pill cannot be read, zero rows is a "
                    "FAIL like everywhere else in this toolkit. "
                    "NOTE AND WHEN: design 4.6 asks for both and the rows measured on "
                    "2026-09-10 stated neither. They are reported as null when the row does "
                    "not state them, and a null note means the row did not say - NOT that "
                    "the person sent no note.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sp.add_argument("--limit", type=int, default=25)
    sp.add_argument("--port", type=int, default=9224)
    sp.set_defaults(fn=N.invitations)

    for verb, fn, what in (("follow", N.follow, "follow"), ("unfollow", N.unfollow, "unfollow")):
        sp = sub.add_parser(
            verb, help="%s a company page" % what,
            description="Read the Follow control's current state on the Page's TOP CARD, "
                        "flip it, and assert it flipped after a reload. "
                        "Three independent signals agree on the state - aria-pressed, the "
                        "is-following class token and the accessible name - and all three "
                        "are read: a control whose signals disagree is one this code cannot "
                        "read, and pressing it would be a guess about somebody's Page. "
                        "Follow controls for OTHER organisations sit further down the same "
                        "page on recommendation cards, so the search is scoped to the top "
                        "card. Already in the asked-for state, it presses nothing and says "
                        "so.",
            formatter_class=argparse.RawDescriptionHelpFormatter)
        sp.add_argument("url", help="a /company/ URL, or just the slug")
        sp.add_argument("--dump", help="write what the run measured to this JSON file")
        sp.add_argument("--port", type=int, default=9224)
        sp.set_defaults(fn=fn)

    sp = sub.add_parser(
        "invite-to-follow", help="invite connections to follow a Page we administer",
        description="The Page's own 'Invite to follow' dialog, reachable by URL. "
                    "STAGED BY DEFAULT: it opens the dialog, reads the credit line, ticks "
                    "the people named, and then dismisses and RE-READS the credit line, "
                    "which must not have moved. "
                    "THE PROOF OF A REAL RUN IS THE CREDIT COUNT AND NOT A ROW THAT SAYS "
                    "'Invited': a credit is the thing that is actually spent, so the page's "
                    "own 'N/50 credits available' is read before and after and must fall by "
                    "exactly the number invited. "
                    "A person is picked BY NAME, off the row control that names them "
                    "('Select <Full Name>') - the checkbox beside it has no label at all and "
                    "twenty rows are on screen before anybody searches. "
                    "At most five credits a run; the Page's whole monthly budget is 50.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sp.add_argument("--page", required=True, help="the Page's numeric id or slug")
    sp.add_argument("--name", action="append",
                    help="a person's full name exactly as the dialog states it. Repeat for "
                         "more than one; at most five.")
    sp.add_argument("--submit", action="store_true",
                    help="actually spend the credits. Default stages and spends nothing.")
    sp.add_argument("--dump", help="write what the run measured to this JSON file")
    sp.add_argument("--port", type=int, default=9224)
    sp.set_defaults(fn=N.invite_to_follow)

    sp = sub.add_parser(
        "read-inbox", help="print the messaging inbox as JSON, one conversation per line",
        description="The conversation LIST only. IT DOES NOT OPEN A THREAD, AND IT PROVES "
                    "IT: opening one marks it read and can show the other participant a read "
                    "receipt, which is a write wearing a read's clothes. The list is reached "
                    "through a bare /messaging/compose/, measured to render it with nothing "
                    "selected, and the run asserts no thread is open rather than trusting "
                    "the route. "
                    "It cannot return a thread URL - the rows are not links and carry no id "
                    "in any attribute (amendment A3) - so each row carries an opaque "
                    "thread_ref that read-thread and message both accept. "
                    "Unread is read from TWO independent signals and a disagreement is a "
                    "FAIL; an inbox where no row carries the marker says so on the RESULT "
                    "line rather than reporting a quiet nothing-unread.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sp.add_argument("--limit", type=int, default=25)
    sp.add_argument("--unread", action="store_true",
                    help="drive the inbox's OWN Unread filter, rather than filtering rows here")
    sp.add_argument("--port", type=int, default=9224)
    sp.set_defaults(fn=M.read_inbox)

    sp = sub.add_parser(
        "read-thread", help="print one conversation as JSON, one message per line",
        description="OPENING A THREAD MARKS IT READ and that cannot be undone invisibly - "
                    "the unread signal is gone even if it is later marked unread again, and "
                    "the other participant may see a read receipt. So this verb is read-only "
                    "in name only, its RESULT line carries marked_read=true, and a thread is "
                    "the one messaging read that stays on the daily safety cap. "
                    "It takes a thread URL or a thread_ref that read-inbox printed.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sp.add_argument("url", help="a /messaging/thread/<id>/ URL, or a thread_ref from read-inbox")
    sp.add_argument("--port", type=int, default=9224)
    sp.set_defaults(fn=M.read_thread)

    sp = sub.add_parser(
        "message", help="compose a message to one person",
        description="STAGED BY DEFAULT: it opens the conversation, checks who it is with, "
                    "counts the messages already in it, types the draft, proves nothing was "
                    "sent, takes the draft back out and re-reads the thread to prove that "
                    "too. "
                    "ON LINKEDIN'S MESSAGE BOX, ENTER SENDS, and the shared typing helper "
                    "presses one Enter per newline - so this verb has its own typing path "
                    "that never presses a bare Enter, and it is BACKED BY A COUNT: the "
                    "number of messages in the thread is read before typing and again after "
                    "every line, and a rise means a fragment has already reached the "
                    "recipient and it says so at once. "
                    "A thread also carries one-click quick-reply buttons that send canned "
                    "text with no draft stage, so nothing inside a thread is clicked here: "
                    "the composer is reached with focus(), which dispatches no pointer "
                    "event, and the only click is Send under --submit. "
                    "It takes a profile URL, a thread URL or a thread_ref.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sp.add_argument("url", help="a profile URL, a /messaging/thread/<id>/ URL, or a thread_ref")
    sp.add_argument("--text", help="the message")
    sp.add_argument("--text-file", help="UTF-8 file holding the message")
    sp.add_argument("--expect-name", help="the recipient's name as the conversation's title "
                                          "bar states it. REQUIRED with --submit (rule 0.3).")
    sp.add_argument("--submit", action="store_true",
                    help="actually send it. Default stages and sends nothing.")
    sp.add_argument("--dump", help="write everything the run measured to this JSON file")
    sp.add_argument("--port", type=int, default=9224)
    sp.set_defaults(fn=M.message)


    from kit import selftest as T
    sp = sub.add_parser("selftest",
                        help="run every verb on things we own, leaving nothing behind")
    sp.add_argument("--post", help="permalink of a post WE authored (comments go here). REQUIRED: pass it here, or record it in the machine's selftest fixtures file (R20). The run FAILS without it either way.")
    sp.add_argument("--page", help="Page id for the publish + delete-post round trip, and for stats")
    sp.add_argument("--page-name", help="exact Page name")
    sp.add_argument("--profile", default="https://www.linkedin.com/in/sorenfrederiksen/",
                    help="the owner's own profile (row P2-1)")
    sp.add_argument("--profile-expect", default=T.SOREN_EXPECT,
                    help="what the owner's own profile says, field by field, for row P2-1: "
                         + T.EXPECT_SYNTAX)
    sp.add_argument("--other-profile",
                    help="a 1st- or 2nd-degree profile URL for rows P2-2 and P2-2b. REQUIRED "
                         "and never committed: this repository is public. Without it the run "
                         "fails.")
    sp.add_argument("--other-expect",
                    help="what THAT profile says, read off the screen by a person, for row "
                         "P2-2. REQUIRED and never committed. " + T.EXPECT_SYNTAX)
    sp.add_argument("--menu-profile",
                    help="row P2-10, and the shape both defects of 2026-09-09 appeared on: a "
                         "profile whose invitation is a MENU ITEM behind More rather than a "
                         "control on the top card, AND whose top card states no current employer. "
                         "REQUIRED and never committed. Without it the More-menu path never runs "
                         "and the empty-employer guard is never exercised.")
    sp.add_argument("--menu-expect",
                    help="what THAT profile says, for row P2-10. REQUIRED, never committed, and "
                         "its company must be none. " + T.EXPECT_SYNTAX)
    sp.add_argument("--pending-profile",
                    help="row P2-11: a profile we have ALREADY SENT an invitation to, which has "
                         "not been accepted, so its top card reads Pending. REQUIRED and never "
                         "committed. No other fixture reaches that state, and none of it can be "
                         "fabricated - an invitation has to have been sent to a real person.")
    sp.add_argument("--follow-company", default="centerconsulting-inc",
                    help="row P3-12: the company Page the follow round trip borrows. It is "
                         "flipped away from whatever state it is in and then flipped BACK, "
                         "so it ends exactly where it started whichever end it began at. "
                         "Defaults to the owner's OWN Page, which costs nothing against the "
                         "daily safety cap and borrows nobody else's; pass a third party's "
                         "slug to exercise the same control on a Page we do not administer, "
                         "and then it is capped like any other read.")
    sp.add_argument("--invite-name",
                    help="row P3-13: the full name of one of the owner's own connections, "
                         "exactly as the Page's invite dialog states it. The dialog picks a "
                         "person by that name and by nothing else. REQUIRED and never "
                         "committed.")
    sp.add_argument("--company", default="centerconsulting-inc", help="company slug (row P2-4)")
    sp.add_argument("--query-people", default="Soren Frederiksen mindzie",
                    help="people search whose first row is the owner (row P2-5)")
    sp.add_argument("--query-posts", default="mindzie", help="content search (row P2-6)")
    sp.add_argument("--port", type=int, default=9224)
    sp.set_defaults(fn=T.run)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
