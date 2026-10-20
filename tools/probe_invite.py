# -*- coding: utf-8 -*-
"""Probe: what does pressing a profile's invite control actually open, for `connect`?

    py -3.11 tools/probe_invite.py <profile URL> [--via-href] [--note-probe]

Without --via-href it PRESSES THE CARD'S (or the menu's) invite control, which
is how the SDUI post-connect request below was found; with it, it navigates to
that control's href instead, which is the route `connect` uses.

Survey section 10.1 and 10.2 record that the custom-invite surface - the dialog,
"Add a note", its character limit, "Send" and "Send without a note" - was NEVER
measured, because nobody knew whether pressing Connect opens a dialog or sends.
This measures it, and it is built so that it cannot send even if pressing
Connect turns out to send at once:

  * EVERY non-GET request the page makes from the moment the invite control is
    pressed is recorded, and any whose address or body mentions an invitation,
    a relationship or a connection is ABORTED before it leaves the browser. If
    the dialog needs such a request to open, it does not open and the output
    says which request was refused - a probe that fails closed.
  * Nothing named Send is pressed. With --note-probe, "Add a note" is pressed
    (it only reveals a text box), four characters are typed into the box and
    read back, and the box is cleared. Enter is never pressed.
  * The dialog is dismissed, the profile is reloaded, and the top card is read
    again: the invite control must still be there and no Pending control.

IT ROUTES "**/*" AND THEN SLEEPS, which is the pattern that hung `connect` on
2026-10-20 (docs/phase-3-amendments.md): with the sync API a routed request is
answered only while Python is inside a Playwright call. It worked for these six
runs; if a run sits on a spinner, that is why, and the fix is the regex route
`connect` uses.

Costs two CAPPED views (the profile, and the proving reload) and leaves the
ordinary "viewed your profile" trace. Output names a real person and is never
committed.
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cc_linkedin_kit import people as P
from cc_linkedin_kit import selectors as S
from cc_linkedin_kit.browser import Browser, Pace, log

GUARD = re.compile(r"invit|relationship|connect|growth", re.I)
MODAL = "dialog[open], [role=dialog][aria-labelledby=send-invite-modal]"
# Every BLOCKED request in full, written to %TEMP%\probe_invite_blocked.json. It
# carries a member id and a slug, which is why it goes to TEMP and nowhere else.
FULL = []

WHAT_IS_OPEN = r"""
() => {
  const vis = e => !!(e.offsetParent || e.getClientRects().length);
  const t = e => (e.innerText || '').replace(/\s+/g, ' ').trim();
  const out = [];
  for (const d of document.querySelectorAll('dialog, [role=dialog], [role=alertdialog], [aria-modal=true], [data-testid*=dialog]')) {
    if (!vis(d)) continue;
    out.push({
      tag: d.tagName, open: d.hasAttribute('open'), role: d.getAttribute('role'),
      testid: d.getAttribute('data-testid'), label: d.getAttribute('aria-label'),
      labelledby: d.getAttribute('aria-labelledby'),
      text: t(d).slice(0, 900),
      buttons: [...d.querySelectorAll('button, a, [role=button]')].filter(vis).map(b => ({
        tag: b.tagName, text: t(b).slice(0, 80), aria: b.getAttribute('aria-label'),
        type: b.getAttribute('type'), disabled: b.disabled === true || b.getAttribute('aria-disabled') === 'true',
        href: b.getAttribute('href')})),
      fields: [...d.querySelectorAll('textarea, input, [contenteditable=true], [role=textbox]')].map(f => ({
        tag: f.tagName, type: f.getAttribute('type'), name: f.getAttribute('name'), id: f.id,
        aria: f.getAttribute('aria-label'), placeholder: f.getAttribute('placeholder'),
        maxlength: f.getAttribute('maxlength'), value: (f.value !== undefined ? f.value : t(f)),
        visible: vis(f)})),
      counters: [...d.querySelectorAll('*')].filter(e => !e.children.length && /\d+\s*\/\s*\d+/.test(t(e))).map(t).slice(0, 5),
    });
  }
  return {url: location.href, dialogs: out};
}
"""


def card_state(br):
    card = br.page.evaluate(P.TOPCARD_JS, [S.PROFILE_TOPCARD, {"fill": S.PROFILE_PRIMARY_FILL}])
    if not card:
        return None, None, None
    return card, P._invite(card["controls"]), P._pending(card["controls"])


def main():
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    note_probe = "--note-probe" in sys.argv
    if not args:
        print(__doc__)
        return 2
    url = args[0]
    pace = Pace()
    seen = []
    armed = {"on": False}

    def guard(route, request):
        if request.method == "GET":
            return route.continue_()
        body = ""
        try:
            body = request.post_data or ""
        except Exception:                                         # noqa: BLE001
            body = "<binary>"
        hit = armed["on"] and bool(GUARD.search(request.url) or GUARD.search(body))
        seen.append({"t": round(time.time(), 1), "method": request.method,
                     "url": request.url[:220], "body": body[:500], "aborted": hit})
        if hit:
            FULL.append({"url": request.url, "body": body,
                         "headers": request.headers})
        if hit:
            return route.abort()
        return route.continue_()

    with Browser(9224) as br:
        pace.before_view("probe: profile, for its invite control")
        final = br.read(url, "the profile", settle=7)
        pace.after_view()
        print("landed:", final)
        card, invite, pending = card_state(br)
        if not card:
            print("RESULT probe no-topcard")
            return 1
        print("name:", card["name"])
        print("pending control:", json.dumps(pending))
        print("invite on card:", json.dumps(invite))
        if pending:
            print("RESULT probe already-pending (nothing pressed)")
            return 0

        br.page.route("**/*", guard)
        top = br.page.locator(S.PROFILE_TOPCARD).first
        target = None
        if invite:
            cands = top.locator('a[href*="%s"]' % S.INVITE_HREF)
            vis = [cands.nth(i) for i in range(cands.count()) if cands.nth(i).is_visible()]
            print("visible invite links in the top card:", len(vis))
            if len(vis) != 1:
                print("RESULT probe ambiguous-card-invite")
                return 1
            target = vis[0]
        else:
            more = top.get_by_role("button", name=S.PROFILE_MORE_NAME)
            mb = [more.nth(i) for i in range(more.count()) if more.nth(i).is_visible()]
            if len(mb) != 1:
                print("RESULT probe no-single-more-button (%d)" % len(mb))
                return 1
            mb[0].click(timeout=6000)
            time.sleep(2)
            items = br.page.locator('[role=menu] [role=menuitem]')
            hits = [items.nth(i) for i in range(items.count())
                    if items.nth(i).is_visible()
                    and S.INVITE_HREF in (items.nth(i).get_attribute("href") or "")]
            print("menu items carrying the invite href:", len(hits))
            for i in range(items.count()):
                it = items.nth(i)
                if it.is_visible():
                    print("  menuitem:", json.dumps({"text": it.inner_text()[:60],
                                                     "aria": it.get_attribute("aria-label"),
                                                     "href": it.get_attribute("href"),
                                                     "tag": it.evaluate("e => e.tagName")}))
            if len(hits) != 1:
                print("RESULT probe no-single-menu-invite")
                return 1
            target = hits[0]

        if "--via-href" in sys.argv:
            href = target.get_attribute("href")
            dest = href if href.startswith("http") else "https://www.linkedin.com" + href
            if "/in/" in final and S.INVITE_HREF not in dest:
                print("RESULT probe href-is-not-custom-invite %s" % dest)
                return 1
            armed["on"] = True
            log("NAVIGATING to the invite control's own href (a GET), with invitation-shaped "
                "requests BLOCKED")
            pace.before_view("probe: the custom-invite page")
            br.goto(dest, settle=6)
            pace.after_view()
            target = None
        if target is not None:
            print("target:", json.dumps({"tag": target.evaluate("e => e.tagName"),
                                         "text": target.inner_text()[:40],
                                         "aria": target.get_attribute("aria-label"),
                                         "href": target.get_attribute("href")}))
            br.page.evaluate("() => { window.__ccProbe = 1; }")
            armed["on"] = True
            log("pressing the invite control, with invitation-shaped requests BLOCKED")
            target.click(timeout=10000)
            time.sleep(4)
            survived = br.page.evaluate("() => window.__ccProbe === 1")
            print("page survived the press (no navigation):", survived)
        state = br.page.evaluate(WHAT_IS_OPEN)
        print("AFTER PRESS:", json.dumps(state, indent=1, ensure_ascii=True))
        shot = os.path.join(os.environ.get("TEMP", "."), "probe_invite_1.png")
        br.screenshot(shot)
        print("shot:", shot)

        if note_probe and state["dialogs"]:
            d = br.page.locator(MODAL)
            add = d.get_by_role("button", name=re.compile(r"^Add a (free )?note", re.I))
            print("Add-a-note buttons:", add.count())
            if add.count() == 1:
                add.first.click(timeout=8000)
                time.sleep(2)
                state2 = br.page.evaluate(WHAT_IS_OPEN)
                print("AFTER ADD A NOTE:", json.dumps(state2, indent=1, ensure_ascii=True))
                box = br.page.locator(MODAL + " textarea")
                print("textareas in the open dialog:", box.count())
                if box.count() == 1:
                    box.first.click()
                    br.page.keyboard.insert_text("abcd")
                    time.sleep(1)
                    state3 = br.page.evaluate(WHAT_IS_OPEN)
                    print("AFTER TYPING 4 CHARS:", json.dumps(state3, indent=1, ensure_ascii=True))
                    shot2 = os.path.join(os.environ.get("TEMP", "."), "probe_invite_2.png")
                    br.screenshot(shot2)
                    print("shot:", shot2)
                    box.first.fill("")
                    time.sleep(0.5)

        # Dismiss: the dialog's own Dismiss control, else Escape.
        dis = br.page.locator(MODAL).get_by_role("button", name=re.compile(r"^Dismiss$", re.I))
        if dis.count() == 1:
            dis.first.click(timeout=8000)
            print("dismissed with the dialog's Dismiss button")
        else:
            br.page.keyboard.press("Escape")
            print("dismissed with Escape (Dismiss buttons found: %d)" % dis.count())
        time.sleep(2)
        state4 = br.page.evaluate(WHAT_IS_OPEN)
        print("AFTER DISMISS:", json.dumps(state4, indent=1, ensure_ascii=True))
        armed["on"] = False
        with open(os.path.join(os.environ.get("TEMP", "."), "probe_invite_blocked.json"), "w",
                  encoding="utf-8") as f:
            json.dump(FULL, f, indent=1)
        print("NON-GET REQUESTS SINCE THE PRESS:")
        for r in seen:
            print("  " + json.dumps(r, ensure_ascii=True))

        pace.before_view("probe: the profile again, to prove nothing was sent")
        br.read(url, "the profile", settle=7)
        pace.after_view()
        card2, invite2, pending2 = card_state(br)
        print("after reload: invite on card=%s pending=%s"
              % (json.dumps(invite2), json.dumps(pending2)))
        print("RESULT probe done pending_after_reload=%s" % bool(pending2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
