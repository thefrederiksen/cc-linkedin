# -*- coding: utf-8 -*-
"""Redact the ALREADY-COMMITTED survey dumps in place, by the rules in survey.py.

    py -3.11 tools/redact_surveys.py [--check] [FILE ...]

RULING R13.2, 2026-09-09. The fourth inspection pass found that the survey
redactor knew three identifier forms - /in/ slugs, ACoA member ids, and a fixed
list of query parameters - and that everything else was sitting in the committed
dumps: organisation slugs and numeric ids, post and event urns, a job id,
article paths, three shortened post links, and a precise postal-code map URL.
This repository is PUBLIC.

The dumps cannot be retaken tonight - that needs live pages and the daily view
cap is spent - so they are redacted where they lie. This script is committed
alongside them so the edit is reproducible rather than a hand pass nobody can
check, and it is IDEMPOTENT: running it again changes nothing, which is also how
--check proves a dump is clean.

It uses tools/survey.py's own redact_identifiers, deliberately. Two lists of
rules drift apart; one does not.
"""
import argparse
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from survey import redact_identifiers

DEFAULT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "docs", "surveys", "*.txt")


def main():
    ap = argparse.ArgumentParser(prog="redact_surveys.py",
                                 description=__doc__.split("\n")[0])
    ap.add_argument("files", nargs="*", help="the dumps to redact (default: docs/surveys/*.txt)")
    ap.add_argument("--check", action="store_true",
                    help="change nothing; exit non-zero if any file would change")
    a = ap.parse_args()

    paths = a.files or sorted(glob.glob(DEFAULT))
    if not paths:
        print("FAIL no survey dumps found at %s. A redaction pass that found nothing to read "
              "is a broken instrument, not a clean repository." % DEFAULT)
        sys.exit(1)

    dirty = 0
    for path in paths:
        with open(path, encoding="utf-8") as f:
            before = f.read().splitlines()
        after = [redact_identifiers(line) for line in before]
        changed = [(i + 1, b) for i, (b, x) in enumerate(zip(before, after)) if b != x]
        if not changed:
            print("clean   %s (%d lines)" % (path, len(before)))
            continue
        dirty += 1
        print("REDACT  %s: %d line(s)" % (path, len(changed)))
        for n, b in changed[:6]:
            print("          %d: %s" % (n, b.strip()[:110]))
        if len(changed) > 6:
            print("          ... and %d more" % (len(changed) - 6))
        if not a.check:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write("\n".join(after) + "\n")

    if a.check and dirty:
        print("FAIL %d dump(s) still carry identifiers the redactor knows how to remove." % dirty)
        sys.exit(1)
    print("RESULT redact-surveys files=%d changed=%d" % (len(paths), dirty))


if __name__ == "__main__":
    main()
