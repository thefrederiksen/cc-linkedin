# -*- coding: utf-8 -*-
"""STAGE 1 - the identity code as it stood on 2026-09-09, extracted UNCHANGED.

This file exists for one commit only. It is the defect the inspection found,
lifted out of `kit/search.py` and `kit/comments.py` without altering a
character of its behaviour, so that the breaking inputs the inspector handed us
can be put on it and WATCHED FAILING before the fix is written. The commit that
follows replaces the body of every function here.
"""
import re

ACTIVITY = re.compile(r"urn:li:(?:activity|ugcPost|share):\d+")
POSTS_PATH = re.compile(r"-(activity|share|ugcPost)-(\d+)", re.I)
URN_KIND = {"activity": "activity", "share": "share", "ugcpost": "ugcPost"}


def permalink(urn):
    return "https://www.linkedin.com/feed/update/%s/" % urn


def resolve_post_identity(final_url, stated):
    """(urn, error) for the post the browser landed on. `stated` is what the
    page itself said about its own identity - which STAGE 1 ignores entirely."""
    urn = None
    m = ACTIVITY.search(final_url or "")
    if m:
        urn = m.group(0)
    else:
        m = POSTS_PATH.search(final_url or "")
        if m:
            urn = "urn:li:%s:%s" % (URN_KIND[m.group(1).lower()], m.group(2))
    if urn:
        return urn, None
    return None, ("the short link went to %s, which carries neither a urn nor a "
                  "-<kind>-<id> path" % (final_url or "")[:140])


def urn_of(url, die):
    m = ACTIVITY.search(url or "")
    if not m:
        die("not a post permalink (no urn:li:activity in it): %s" % url)
    return m.group(0)


def may_use_any_card(n_any, stated, wanted):
    """May Post.load() fall back to whatever post card is on the page?"""
    return True
