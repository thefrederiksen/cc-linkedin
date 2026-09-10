# -*- coding: utf-8 -*-
"""Send a batch of direct messages, paced, staged by default.

    py -3.11 tools/send_batch.py <messages.json> [--submit] [--limit N]
                                [--only "Name"] [--log out.json]

<messages.json> is a list of {"name": ..., "message": ...}.

STAGED BY DEFAULT. Without --submit it addresses each recipient and types the
message, proves the box holds it, and presses nothing.

It obeys the toolkit's own pacing: cap 30 messages a day, 45 to 90 seconds
between outbound actions, shared with every other outbound verb through
pace.json. Over the cap it stops and says so rather than pressing on.

Every send is written to the log file as it happens, so an interrupted run
never loses track of who has already been written to.
"""
import io
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cc_linkedin_kit.browser import Browser, Pace, log
from cc_linkedin_kit.messaging import send_one


def main():
    args = sys.argv[1:]
    if not args:
        print("usage: send_batch.py <messages.json> [--submit] [--limit N] "
              "[--only NAME] [--log FILE]")
        return 2
    path = args[0]
    submit = "--submit" in args
    limit = None
    only = None
    logfile = os.path.join(os.path.dirname(path), "sent-log.json")
    for i, a in enumerate(args):
        if a == "--limit":
            limit = int(args[i + 1])
        if a == "--only":
            only = args[i + 1]
        if a == "--log":
            logfile = args[i + 1]

    people = json.load(io.open(path, encoding="utf-8"))
    if isinstance(people, dict):
        people = people.get("ready") or people.get("send") or []
    if only:
        people = [p for p in people if p["name"] == only]
    if limit:
        people = people[:limit]

    done = {}
    if os.path.exists(logfile):
        try:
            done = {r["name"]: r for r in json.load(io.open(logfile, encoding="utf-8"))}
        except Exception:                                   # noqa: BLE001
            done = {}

    pace = Pace()
    todo = [p for p in people if done.get(p["name"], {}).get("result") != "sent"]
    log("%d to do, %d already sent, cap is %d a day and %d used"
        % (len(todo), len(people) - len(todo), Pace.CAPS["message"],
           pace.count("message")))

    out = list(done.values())
    with Browser(9224) as br:
        for i, p in enumerate(todo, 1):
            name = p["name"]
            log("--- %d/%d  %s" % (i, len(todo), name))
            try:
                result, row = send_one(br, name, p["message"], submit=submit)
                rec = {"name": name, "result": result, "row": row[:140],
                       "when": time.strftime("%Y-%m-%d %H:%M:%S")}
            except SystemExit as ex:
                rec = {"name": name, "result": "refused", "why": str(ex)[:200],
                       "when": time.strftime("%Y-%m-%d %H:%M:%S")}
                log("REFUSED %s: %s" % (name, str(ex)[:160]))
            except Exception as ex:                          # noqa: BLE001
                rec = {"name": name, "result": "error", "why": str(ex)[:200],
                       "when": time.strftime("%Y-%m-%d %H:%M:%S")}
                log("ERROR %s: %s" % (name, str(ex)[:160]))
            out = [r for r in out if r["name"] != name] + [rec]
            json.dump(out, io.open(logfile, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
            log("    %s" % rec["result"])

    from collections import Counter
    c = Counter(r["result"] for r in out)
    print("RESULT send_batch %s log=%s" % (dict(c), logfile))
    return 0


if __name__ == "__main__":
    sys.exit(main())
