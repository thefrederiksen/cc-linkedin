# -*- coding: utf-8 -*-
"""Which of these people can actually be messaged?

A LinkedIn direct message needs a 1st-degree CONNECTION. An invitation sitting
in the mailbox proves they asked; it never proved the owner accepted. So a list
built from invitation notifications contains people who are not connections,
and for those the message cannot be sent at all.

This asks the compose typeahead, which searches connections only, and records
for each name:

    connected   the typeahead offered a 1st-degree row whose headline matches
                the one we hold, so it is the right person
    ambiguous   a row came back but the headline does not match what we hold,
                or several plausible rows did. NEVER auto-send to these.
    absent      "No results found" - not a connection, cannot be messaged

Read-only. It types names and reads rows. It never opens a thread and it
cannot send: there is no Send in this file.

    py -3.11 tools/check_reachable.py <people.json> <out.json>
"""
import io
import json
import os
import re
import sys
import time
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cc_linkedin_kit.browser import Browser, log

COMPOSE = "https://www.linkedin.com/messaging/compose/"
FIELD = "input.msg-connections-typeahead__search-field"
OPTION = "li.msg-connections-typeahead__search-result"

ROWS_JS = r"""
() => [...document.querySelectorAll('li.msg-connections-typeahead__search-result')]
  .slice(0, 10).map(li => (li.innerText || '').replace(/\s+/g, ' ').trim())
"""


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9 ]", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def words(s):
    return set(w for w in norm(s).split() if len(w) > 3)


def degree_of(row):
    m = re.search(r"\b(1st|2nd|3rd)\b", row)
    return m.group(1) if m else ""


def classify(person, rows):
    """Match a typeahead row to the person we meant, on name AND headline."""
    want_name = norm(person["name"])
    want_head = words(person.get("headline"))
    best = None
    for r in rows:
        rn = norm(r)
        # the row text starts with status noise, so test containment
        if want_name and want_name in rn:
            overlap = len(want_head & words(r)) if want_head else 0
            cand = {"row": r[:160], "degree": degree_of(r), "overlap": overlap}
            if best is None or overlap > best["overlap"]:
                best = cand
    if best is None:
        return ("absent", None) if not rows else ("ambiguous", {"rows": rows[:3]})
    if best["degree"] != "1st":
        return "ambiguous", best
    # headline agreement is what proves it is the same person, not a namesake
    if best["overlap"] >= 2 or not words(person.get("headline")):
        return "connected", best
    return "ambiguous", best


def main():
    if len(sys.argv) < 3:
        print("usage: check_reachable.py <people.json> <out.json>")
        return 2
    people = json.load(io.open(sys.argv[1], encoding="utf-8"))
    if isinstance(people, dict):
        people = people.get("send") or people.get("cleared") or []

    out = []
    with Browser(9224) as br:
        page = br.page
        br.goto(COMPOSE, settle=5)
        br.assert_signed_in("the compose surface")
        box = page.locator(FIELD).first
        box.wait_for(state="visible", timeout=20000)

        for i, p in enumerate(people, 1):
            name = p["name"]
            try:
                box.click()
                box.fill("")
                time.sleep(0.4)
                br.type_text(name)
                time.sleep(2.6)
                rows = page.evaluate(ROWS_JS)
                state, ev = classify(p, rows)
            except Exception as ex:                       # noqa: BLE001
                state, ev, rows = "error", {"error": str(ex)[:160]}, []
            out.append({"name": name, "slug": p.get("slug"),
                        "company": p.get("company"), "country": p.get("country"),
                        "state": state, "evidence": ev, "row_count": len(rows)})
            log("%3d/%d  %-28s %s" % (i, len(people), name[:28], state))
            box.fill("")
            time.sleep(0.5)

    json.dump(out, io.open(sys.argv[2], "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    from collections import Counter
    c = Counter(o["state"] for o in out)
    print("RESULT reachable %s" % dict(c))
    return 0


if __name__ == "__main__":
    sys.exit(main())
