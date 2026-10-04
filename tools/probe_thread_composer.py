# -*- coding: utf-8 -*-
"""Read-only probe of an OPEN conversation's composer, for the `message` verb.

    py -3.11 tools/probe_thread_composer.py <thread_ref | thread URL> [--send-options]

Opens one conversation exactly the way read-thread does (so it MARKS IT READ and
counts on the capped view line), then dumps what the composer and the thread
header expose: the editor, its contents, the Send button and its state, the
"Open send options" control, the bubble count, and who the page says the
conversation is with.

IT TYPES NOTHING AND PRESSES NO KEY EXCEPT Escape (to close the send-options
menu, which --send-options opens to READ the Enter-to-send setting; no menu item
is clicked). Nothing here can send: Send is never clicked, the editor is never
focused, and no quick-reply button is touched.

Output names real people. It goes to stdout and is never committed.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cc_linkedin_kit import inbox as I
from cc_linkedin_kit.browser import Browser, Pace, log

DUMP = r"""
() => {
  const t = e => e ? (e.innerText || '').replace(/\s+/g, ' ').trim() : '';
  const attrs = e => e ? Object.fromEntries([...e.attributes].map(a => [a.name, a.value.slice(0, 120)])) : null;
  const eds = [...document.querySelectorAll('.msg-form__contenteditable, [role=textbox][contenteditable=true]')];
  const sends = [...document.querySelectorAll('button.msg-form__send-button, button[type=submit]')];
  const opts = [...document.querySelectorAll('button')].filter(b => /send options/i.test(b.getAttribute('aria-label') || b.innerText || ''));
  const forms = [...document.querySelectorAll('form.msg-form, form')].map(f => ({cls: f.className.slice(0, 100), n_ed: f.querySelectorAll('[contenteditable=true]').length}));
  const heads = [...document.querySelectorAll('.msg-entity-lockup__entity-title, h2.msg-overlay-bubble-header__title, .msg-thread__link-to-profile, .msg-title-bar h2, .msg-title-bar a[href*="/in/"]')]
      .map(e => ({tag: e.tagName, cls: e.className.slice(0, 90), text: t(e), href: e.getAttribute('href')}));
  const events = [...document.querySelectorAll('li.msg-s-message-list__event')];
  const groups = [...document.querySelectorAll('.msg-s-message-group__name')].map(t);
  const meta = [...document.querySelectorAll('.msg-s-message-group__meta, .msg-s-message-group__profile-link')].slice(-4).map(e => ({cls: e.className.slice(0,80), text: t(e).slice(0,80)}));
  const lastEv = events.length ? events[events.length - 1] : null;
  const qr = [...document.querySelectorAll('li.msg-s-message-list__quick-replies-container button')].map(b => (b.getAttribute('aria-label') || '').slice(0, 30));
  const me = document.querySelector('img.global-nav__me-photo');
  return {
    url: location.href,
    editors: eds.map(e => ({attrs: attrs(e), text: e.innerText, html: e.innerHTML.slice(0, 300)})),
    sends: sends.map(b => ({attrs: attrs(b), text: t(b), disabled: b.disabled})),
    send_options: opts.map(b => ({attrs: attrs(b), text: t(b)})),
    forms: forms,
    headers: heads,
    events: events.length,
    group_names: groups.slice(-6),
    last_event_html: lastEv ? lastEv.outerHTML.slice(0, 1500) : null,
    meta: meta,
    quick_replies: qr,
    me_alt: me ? me.getAttribute('alt') : null,
    other_bubbles: {
      'li.msg-s-message-list__event': events.length,
      '.msg-s-event-listitem': document.querySelectorAll('.msg-s-event-listitem').length,
      '.msg-s-event-listitem--other': document.querySelectorAll('.msg-s-event-listitem--other').length,
    },
  };
}
"""

MENU = r"""
() => [...document.querySelectorAll('[role=menu], .artdeco-dropdown__content, [role=menuitem], [role=menuitemradio], [role=radio], input[type=radio]')]
   .slice(0, 20).map(e => ({tag: e.tagName, role: e.getAttribute('role'), cls: (e.className || '').toString().slice(0, 80),
      text: (e.innerText || e.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim().slice(0, 160),
      checked: e.getAttribute('aria-checked') || (e.checked === undefined ? null : e.checked)}))
"""


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    target = args[0]
    pace = Pace()
    with Browser(9224) as br:
        if target.startswith("http"):
            pace.before_view("probe: a conversation thread (MARKS IT READ)")
            br.read(target, "the conversation", settle=6)
            pace.after_view()
        else:
            I._open_from_ref(br, pace, I.parse_ref(target))
        time.sleep(4)
        got = br.page.evaluate(DUMP)
        print(json.dumps(got, indent=1, ensure_ascii=True))
        shot = os.path.join(os.environ.get("TEMP", "."), "probe_thread_composer.png")
        br.screenshot(shot)
        print("shot:", shot)
        if "--send-options" in args:
            b = br.page.locator("button.msg-form__send-toggle")
            log("send-options buttons: %d" % b.count())
            if b.count():
                b.first.click(timeout=5000)
                time.sleep(1.5)
                print(json.dumps(br.page.evaluate(MENU), indent=1, ensure_ascii=True))
                shot2 = shot.replace(".png", "-options.png")
                br.screenshot(shot2)
                print("shot:", shot2)
                br.page.keyboard.press("Escape")
                time.sleep(1)
        print("RESULT probe done (nothing typed, nothing sent) marked_read=true")
    return 0


if __name__ == "__main__":
    sys.exit(main())
