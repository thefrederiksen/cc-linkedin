# -*- coding: utf-8 -*-
"""Read several conversations in one run, by participant name.

    py -3.11 tools/read_threads.py <names.json> --out DIR [--rows N] [--port P]

<names.json> is a list of participant names exactly as read-inbox printed them.

The list is loaded ONCE, then each named row is opened, the name on the open
thread's header is compared with the name asked for, and every message is
written to DIR/<name>.json. A name that matches no row, or more than one, is
skipped and reported - never guessed.

OPENING A THREAD MARKS IT READ and can show the other person a read receipt.
Each thread is one capped view through the toolkit's own pacing. Nothing in a
thread is clicked: no composer, no quick reply.
"""
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kit.browser import Browser, Pace, log
from kit import messaging as M


def main():
    args = sys.argv[1:]
    if len(args) < 3 or "--out" not in args:
        print("usage: read_threads.py <names.json> --out DIR [--rows N] [--port P]")
        return 2
    names = json.load(io.open(args[0], encoding="utf-8"))
    out = args[args.index("--out") + 1]
    rows_wanted = int(args[args.index("--rows") + 1]) if "--rows" in args else 120
    port = int(args[args.index("--port") + 1]) if "--port" in args else 9224
    os.makedirs(out, exist_ok=True)

    pace = Pace()
    done, skipped = 0, []
    with Browser(port) as br:
        inbox = M.Inbox(br, pace).load(want=rows_wanted)
        for name in names:
            target = os.path.join(out, re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_") + ".json")
            if os.path.exists(target):
                log("%s: already on disk, not opened again" % name)
                continue
            fresh = br.page.evaluate(M.ROWS_JS, M._sel_list())
            hits = [r for r in fresh if (r["participant"] or "") == name]
            if len(hits) != 1:
                skipped.append("%s (%d rows carry that name)" % (name, len(hits)))
                continue
            pace.before_view("one messaging thread (%s)" % name)
            try:
                M._click_row(br, hits[0])
            except Exception as ex:                               # noqa: BLE001
                # ONE AWKWARD ROW MUST NOT COST THE WHOLE RUN. Paging the list
                # down to a few hundred rows takes about five minutes, and it
                # happens before the first thread is opened; letting a click
                # failure escape threw all of that away and the next attempt
                # started the paging again from nothing. Measured 2026-09-20,
                # when a click on row 162 timed out and killed a run that had
                # just spent five minutes getting there.
                skipped.append("%s (could not be opened: %s)"
                               % (name, str(ex).splitlines()[0][:90]))
                continue
            pace.after_view()
            head = M._thread_header(br)
            # The header is the name, then the person's CURRENT headline on its
            # own line (measured live 2026-09-20). The first line is the identity.
            shown = (head["name"] or "").splitlines() or [""]
            headline = " ".join(x.strip() for x in shown[1:]).strip()
            if shown[0].strip() != name:
                skipped.append("%s (the open thread's header says %r)" % (name, head["name"]))
                continue
            msgs = br.page.evaluate(M.MESSAGES_JS, M._sel_thread())
            if not msgs:
                skipped.append("%s (the thread opened with zero message bubbles)" % name)
                continue
            rec = {"name": name, "headline": headline, "slug": head["slug"], "url": head["url"],
                   "list_when": hits[0]["when"], "messages": msgs,
                   "quick_reply_rows": br.page.locator(M.S.QUICK_REPLIES).count()}
            with io.open(target, "w", encoding="utf-8") as f:
                json.dump(rec, f, ensure_ascii=True, indent=1)
            done += 1
            log("%s: %d messages written" % (name, len(msgs)))
    for s in skipped:
        print("SKIPPED %s" % s)
    print("RESULT read-threads read=%d skipped=%d marked_read=true" % (done, len(skipped)))
    return 0 if not skipped else 1


if __name__ == "__main__":
    sys.exit(main())
