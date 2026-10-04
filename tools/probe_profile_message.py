# -*- coding: utf-8 -*-
"""Read-only probe: where does a profile's Message control lead, for `message`?

    py -3.11 tools/probe_profile_message.py <profile URL>

Opens the profile (one CAPPED view, and the person gets the ordinary "viewed
your profile" trace), reads the top card's Message control, then follows its
href and dumps what that page holds: the final address, the composer, whether a
conversation's history is shown (bubbles), and the header naming who it is with.

IT TYPES NOTHING, CLICKS NOTHING AND PRESSES NO KEY. Following the href is a
navigation; if that lands on an existing conversation it MARKS IT READ, and the
output says so. Output names real people and is never committed.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cc_linkedin_kit import people as P
from cc_linkedin_kit import selectors as S
from cc_linkedin_kit.browser import Browser, Pace, log

AFTER = r"""
() => {
  const t = e => e ? (e.innerText || '').replace(/\s+/g, ' ').trim() : '';
  const ed = document.querySelector('.msg-form__contenteditable');
  const send = document.querySelector('button.msg-form__send-button');
  return {
    url: location.href,
    editor: ed ? {label: ed.getAttribute('aria-label'), html: ed.innerHTML.slice(0, 200)} : null,
    send: send ? {disabled: send.disabled, text: t(send)} : null,
    to_field: !!document.querySelector('input.msg-connections-typeahead__search-field'),
    to_pills: [...document.querySelectorAll('.msg-connections-typeahead__added-recipients, .msg-compose__profile-link, .artdeco-pill')].map(t).slice(0, 4),
    thread_list: !!document.querySelector('.msg-s-message-list-content'),
    events: document.querySelectorAll('li.msg-s-message-list__event').length,
    header_h2: t(document.querySelector('.msg-entity-lockup__entity-title')),
    header_link: (document.querySelector('a.msg-thread__link-to-profile') || {getAttribute: () => null}).getAttribute('href'),
    active_rows: document.querySelectorAll('.msg-conversations-container__convo-item-link--active').length,
    overlay_bubbles: [...document.querySelectorAll('.msg-overlay-conversation-bubble, .msg-overlay-bubble-header__title')].map(t).slice(0, 4),
  };
}
"""


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    url = sys.argv[1]
    pace = Pace()
    with Browser(9224) as br:
        pace.before_view("probe: profile for its Message control")
        final = br.read(url, "the profile", settle=7)
        pace.after_view()
        print("profile landed:", final)
        card = br.page.evaluate(P.TOPCARD_JS, [S.PROFILE_TOPCARD, {"fill": S.PROFILE_PRIMARY_FILL}])
        if not card:
            print("RESULT probe no-topcard")
            return 1
        print("name:", card["name"])
        msgs = [c for c in card["controls"] if "messag" in (c["text"] + c["aria"]).lower()]
        print(json.dumps(msgs, indent=1, ensure_ascii=True))
        hrefs = [c["href"] for c in msgs if "/messaging/" in c["href"]]
        if not hrefs:
            print("RESULT probe no-message-href")
            return 1
        href = hrefs[0]
        if href.startswith("/"):
            href = "https://www.linkedin.com" + href
        log("following %s" % href.split("?")[0])
        pace.before_view("probe: the profile's Message destination (MAY MARK A THREAD READ)")
        br.read(href, "the message destination", settle=7)
        pace.after_view()
        time.sleep(3)
        print(json.dumps(br.page.evaluate(AFTER), indent=1, ensure_ascii=True))
        shot = os.path.join(os.environ.get("TEMP", "."), "probe_profile_message.png")
        br.screenshot(shot)
        print("shot:", shot)
        print("RESULT probe done (nothing typed, nothing clicked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
