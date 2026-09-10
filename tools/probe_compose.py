# -*- coding: utf-8 -*-
"""Read-only probe of the compose surface AFTER a recipient is chosen.

Run BEFORE writing the `message` verb's selectors. It types a name into the
recipient typeahead, reads the option rows, picks the one asked for, and then
dumps what the page exposes about who is now in the To field.

IT NEVER PRESSES SEND. There is no code path here that can.

The question it exists to answer: the typeahead option rows carry no profile
link, so picking by name alone cannot prove identity. Something after the pick
has to, or the verb cannot be made safe.

    py -3.11 tools/probe_compose.py "Alex Poberezhniuk"
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cc_linkedin_kit.browser import Browser, log

COMPOSE = "https://www.linkedin.com/messaging/compose/"
FIELD = "input.msg-connections-typeahead__search-field"
OPTION = "li.msg-connections-typeahead__search-result"

DUMP_OPTIONS = r"""
() => [...document.querySelectorAll('li.msg-connections-typeahead__search-result')]
  .slice(0, 8).map(li => ({
     text: (li.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 120),
     href: (li.querySelector('a') || {}).getAttribute
             ? li.querySelector('a').getAttribute('href') : null,
     links: [...li.querySelectorAll('[href]')].map(a => a.getAttribute('href')),
     data: Object.keys(li.dataset || {}),
     html_ids: (li.getAttribute('id') || ''),
  }))
"""

DUMP_AFTER = r"""
() => {
  const pill = document.querySelector('.msg-connections-typeahead__added-recipients');
  const links = [...document.querySelectorAll('a[href*="/in/"]')]
      .map(a => a.getAttribute('href')).slice(0, 12);
  const heads = [...document.querySelectorAll('h2, .msg-entity-lockup__entity-title, .msg-thread__link-to-profile')]
      .map(e => (e.innerText || '').trim()).filter(Boolean).slice(0, 8);
  return {
    recipients_text: pill ? (pill.innerText || '').replace(/\s+/g,' ').trim() : null,
    in_links: links,
    headings: heads,
    has_editor: !!document.querySelector('.msg-form__contenteditable'),
  };
}
"""


def main():
    if len(sys.argv) < 2:
        print("usage: probe_compose.py \"<full name>\"")
        return 2
    who = sys.argv[1]

    with Browser(9224) as br:
        page = br.page
        br.goto(COMPOSE, settle=5)
        br.assert_signed_in("the compose surface")

        print("field count:", page.locator(FIELD).count())
        box = page.locator(FIELD).first
        box.wait_for(state="visible", timeout=20000)
        box.click()
        br.type_text(who)
        time.sleep(4)
        print("field value after typing: %r" % box.input_value())
        page.screenshot(path=os.path.join(
            os.environ.get("TEMP", "."), "probe_compose.png"))
        print("shot:", os.path.join(os.environ.get("TEMP", "."), "probe_compose.png"))
        # count every candidate container, so a zero is attributable
        for sel in (OPTION, "li[role=option]", "ul[role=listbox] li",
                    ".msg-connections-typeahead__search-result-row"):
            print("   %-52s %d" % (sel, page.locator(sel).count()))

        opts = page.evaluate(DUMP_OPTIONS)
        print("--- typeahead rows for %r" % who)
        for o in opts:
            print("   ", o)

        n = page.locator(OPTION).count()
        print("--- option count:", n)
        if not n:
            print("RESULT probe no-options")
            return 1

        page.locator(OPTION).first.click()
        time.sleep(2.5)

        after = page.evaluate(DUMP_AFTER)
        print("--- after picking the first row")
        for k, v in after.items():
            print("   %-16s %s" % (k, v))
        print("RESULT probe done (nothing sent)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
