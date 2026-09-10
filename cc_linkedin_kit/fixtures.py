# -*- coding: utf-8 -*-
"""Where the selftest's third-party fixtures live - RULING R20, 2026-09-10.

THE PROBLEM THIS SOLVES. This repository is PUBLIC, so no third party's URL,
name, headline or location may be committed to it. That rule is right and it
does not move. But it was only half a rule: it said where the values may not go
and left them nowhere else. The two profiles the Phase 2 rows need were
therefore rediscovered by hand by every new seat - a search costing several
views out of a daily safety cap of eighty - measured, used, and thrown away
again. Three seats paid that price and none of them kept the answer, because
there was nowhere to keep it.

THE SPLIT, and it is the whole design:

  * the REPOSITORY documents the SHAPE a fixture must have. `--menu-profile`
    needs a profile whose invitation is a menu item behind More AND whose top
    card states no current employer. That sentence carries the entire
    engineering point and identifies nobody, so it belongs in git.
  * the MACHINE holds the VALUES, in this file, beside pace.json in the state
    directory - which is not in git, is not in the worktree, and never will be.
  * the FLAGS still exist and still win when passed, so a one-off run against a
    different profile needs no file at all.

WHAT THIS MUST NEVER BECOME. The oldest defect in this suite is a missing
fixture producing not a failed row but NO ROW AT ALL, and moving values into a
file is exactly the change that could bring it back - a half-filled file is much
easier to end up with than a half-typed command line. So every absence here is
LOUD: a missing file, a missing key, an empty value and a file that will not
parse all end the run naming what is absent and both ways of supplying it. There
is deliberately no default, no fallback and no skip.
"""
import json
import os
import sys

from . import browser

# The last message `require` or `value` died with. For tests, and for a caller
# that wants to say more before exiting.
last_message = ""

NAME = "selftest-fixtures.json"


def path():
    """The fixtures file. Beside pace.json, in the machine's state directory,
    outside every checkout - that is the point of it.

    Read through the module rather than bound at import, so the directory is
    resolved when it is USED. A value captured at import time is a value that
    cannot be redirected, which matters both for a test and for anything that
    ever wants a state directory chosen at run time."""
    return os.path.join(browser.STATE_DIR, NAME)


def _die(message):
    global last_message
    last_message = message
    print("FAIL " + message, flush=True)
    sys.exit(1)


def _load():
    """The file's contents, or None if there is no file.

    A file that exists and will not parse is a BROKEN INSTRUMENT and is fatal.
    It must never read as "no fixtures are configured", because that answer
    sends the caller down the same path as a machine that was simply never set
    up, and the two need different actions from a person.
    """
    p = path()
    try:
        with open(p, encoding="utf-8") as f:
            raw = f.read()
    except FileNotFoundError:
        return None
    except OSError as exc:
        _die("the fixtures file %s exists but could not be read (%s). That is a broken "
             "instrument, not an unconfigured machine." % (p, str(exc).splitlines()[0][:80]))
    try:
        data = json.loads(raw)
    except ValueError as exc:
        _die("the fixtures file %s does not parse as JSON (%s). Fix or delete it; an "
             "unreadable fixtures file must not be mistaken for an absent one."
             % (p, str(exc)[:80]))
    if not isinstance(data, dict):
        _die("the fixtures file %s holds %s at the top level, and it must hold an object "
             "keyed by fixture name." % (p, type(data).__name__))
    return data


def value(passed, fixture, field):
    """What to use for one fixture field: the flag if it was passed, else the
    file, else None. Answering None is not a verdict - see `require`."""
    if passed is not None and str(passed).strip():
        return passed
    data = _load()
    if not data:
        return None
    entry = data.get(fixture)
    if not isinstance(entry, dict):
        return None
    got = entry.get(field)
    if got is None or not str(got).strip():
        return None
    return got


def require(passed, fixture, field, flag):
    """The same, but a missing value ends the run naming both ways to supply it.

    A fixture that is absent is a FAILED RUN, never a shorter one.
    """
    got = value(passed, fixture, field)
    if got is None:
        _die("no value for the selftest fixture %s.%s. Supply it either on the command line "
             "as %s, or as %r -> %r in %s, which is outside the repository and is where "
             "these values are meant to live (ruling R20). A missing fixture is a failed "
             "run, not a shorter one: without it a row would not fail, it would not exist."
             % (fixture, field, flag, fixture, field, path()))
    return got


def record(fixture, **fields):
    """Write what was just measured, so the next seat does not pay for it again.

    Discovering a fixture costs views out of the daily safety cap. A seat that
    spends them and keeps nothing has made the next seat spend them too, which
    is exactly what R20 exists to stop.
    """
    data = _load() or {}
    entry = data.setdefault(fixture, {})
    entry.update({k: v for k, v in fields.items() if v is not None})
    os.makedirs(browser.STATE_DIR, exist_ok=True)
    p = path()
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=1, sort_keys=True)
    os.replace(tmp, p)
    return p
