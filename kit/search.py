# -*- coding: utf-8 -*-
"""Phase 2 search: people and posts. Read-only, JSON out, one record per line.

Zero rows is a FAIL, not an empty list. A genuinely empty result set and a
broken selector look identical from here, and the broken selector is far more
likely - so a search that finds nothing says so as a failure and names the query
it ran.

MEASURED ON THE LIVE PAGE, 2026-09-09. Dumps in docs/surveys/.

PEOPLE SEARCH
  * The new server-driven React rendering only. A result is a
    div[role=listitem]; the person's NAME is the text of the first anchor to
    /in/ that sits inside a <p>. The anchor wrapping the whole card also points
    at /in/, so matching on "p a" is what separates the name from the card.
  * That <p>'s parent holds two further "div > p" pairs, in order: the headline,
    then the location. The degree badge is a <span> inside the name's own <p>,
    reading "- 1st", "- 2nd", "- 3rd+" - or "- You", on the signed-in member's
    own row, which no other surface produces.
  * THE FIXTURE IN THE DESIGN WAS WRONG ABOUT THE WORLD. Searching people for
    "Soren Frederiksen" does NOT return the owner first: the first ten rows are
    ten other people of that name, the first a realtor in Winnipeg, and his own
    profile is not on page one at all. "Soren Frederiksen mindzie" returns his
    profile as the first and only row. Both dumps are committed, the failing one
    included.

CONTENT SEARCH - AND WHY THERE IS NO PERMALINK
  This is the finding that shaped the verb, so it is written out in full rather
  than left for the next reader to rediscover the hard way.

  * The surface is the new server-driven React rendering and ONLY that. Loaded
    four times, minutes apart: [data-urn] 0 every time, [data-id] 0 every time,
    [data-sdui-screen] 1 every time. There is no classic rendering of a content
    search to reload until, unlike the post permalink Phase 1 met.
  * A result card carries no permalink. Six cards on the first page, and
    a[href*="/feed/update/"] counts 1 - and that one belongs to a post quoted
    INSIDE a card, not to the card itself. a[href*="urn:li:activity"] counts 0.
  * The card's control menu does offer "Copy link to post". It is a menuitem
    with no href: it writes to the clipboard. Read back through granted
    clipboard permission, for three consecutive cards, it returned
    https://lnkd.in/p/gb95KeRa, https://lnkd.in/p/gJm39pjw and
    https://lnkd.in/p/gSCBypgw. A shortener. No activity id anywhere in it.
  * The document that renders the page does embed six activity urns, one per
    card. They cannot be attached to a card with confidence: the per-card DOM
    token (div#expanded<token>FeedType_FLAGSHIP_SEARCH) either appears in the
    raw document with no urn within 4,000 characters either side, or - for the
    last three cards - does not appear in it at all, because those cards are
    fetched after load. Pairing the six urns to the six cards BY ORDER would be
    an assumption dressed as a proof.

  So the record carries `share_url` (the lnkd.in link, always present) and
  `permalink` (the real urn:li:activity URL, or null). There is deliberately no
  field called `url`: a caller reaching for one and silently getting a shortener
  is the same fail-open shape as an empty read. `--resolve` follows the short
  link IN THE BROWSER - never by an HTTP request made outside it, which is the
  shape of the thing the owner shut down - and is hard-capped at 10 rows.
"""
import json
import re
import time

from . import selectors as S
from .browser import Browser, Pace, log, die

PEOPLE_URL = "https://www.linkedin.com/search/results/people/?keywords=%s"
CONTENT_URL = "https://www.linkedin.com/search/results/content/?keywords=%s"
ACTIVITY = re.compile(r"urn:li:(?:activity|ugcPost|share):\d+")
# MEASURED 2026-09-09: a lnkd.in short link does NOT land on /feed/update/. It
# lands on the human-readable post page, /posts/<slug>_<words>-<kind>-<id>-<hash>,
# where <kind> is activity, share or ugcPost. The id is in the path, not in a
# urn, so the urn has to be rebuilt from it. Three consecutive cards resolved to
# ...-share-7495007268124495872-..., ...-share-7503446054340755456-... and
# ...-ugcPost-7409603631332831232-...; Phase 1's verbs accept all three kinds.
POSTS_PATH = re.compile(r"-(activity|share|ugcPost)-(\d+)", re.I)
URN_KIND = {"activity": "activity", "share": "share", "ugcpost": "ugcPost"}
RESOLVE_CAP = 10          # ruling 1, amendment 3

PEOPLE_JS = r"""
(sel) => [...document.querySelectorAll(sel.item)].map(li => {
  const a = li.querySelector(sel.name);
  if (!a) return null;
  const p = a.closest('p');
  const name = (a.innerText || '').replace(/\s+/g, ' ').trim();
  const badge = p ? (p.innerText || '').replace(/\s+/g, ' ').replace(name, '').trim() : '';
  const box = p ? p.parentElement : null;
  const lines = box ? [...box.querySelectorAll(':scope > div > p')]
                        .map(x => (x.innerText || '').replace(/\s+/g, ' ').trim()).filter(Boolean)
                    : [];
  return {name: name, url: (a.getAttribute('href') || '').split('?')[0],
          degree: badge, headline: lines[0] || '', location: lines[1] || ''};
}).filter(Boolean)
"""


def _limit(a, what):
    n = int(getattr(a, "limit", None) or 25)
    if n < 1:
        die("--limit must be at least 1")
    if n > 100:
        die("--limit is %d; the hard cap for %s is 100 results in one run" % (n, what))
    return n


def _query(a):
    q = (a.query or "").strip()
    if not q:
        die("no query given")
    return q


# ---------------------------------------------------------------- search-people

def search_people(a):
    q = _query(a)
    limit = _limit(a, "search-people")
    url = PEOPLE_URL % _quote(q)
    for name, value in (("company", "currentCompany"), ("title", "title"), ("location", "geoUrn")):
        v = getattr(a, name, None)
        if v:
            url += "&%s=%s" % (value, _quote(v))
    pace = Pace()
    with Browser(a.port) as br:
        pace.before_view("a people search")
        final = br.read(url, "the people search for %r" % q, settle=8)
        pace.after_view()
        if "/search/results/people" not in final:
            die("asked for a people search and landed on %s" % final)

        rows = br.page.evaluate(PEOPLE_JS, {"item": S.SEARCH_ITEM, "name": S.SEARCH_PERSON_NAME})
        rows = [r for r in rows if r["name"] and "/in/" in r["url"]][:limit]
        if not rows:
            die("no people found for %r. Zero rows is a broken selector far more often than an "
                "empty result set, so this is a failure and not an empty list. The page was %s"
                % (q, final))

        out = []
        for i, r in enumerate(rows, 1):
            m = S.DEGREE_TEXT.match(r["degree"])
            rec = {"kind": "person_result", "rank": i, "name": r["name"],
                   "url": r["url"] if r["url"].startswith("http") else "https://www.linkedin.com" + r["url"],
                   "headline": r["headline"] or None, "location": r["location"] or None,
                   "degree": m.group(1).lower() if m else None,
                   "degree_raw": r["degree"] or None}
            out.append(rec)
            print(json.dumps(rec, ensure_ascii=True))
        print("RESULT search-people query=%r rows=%d first=%s" % (q, len(out), out[0]["url"]))


# ---------------------------------------------------------------- search-posts

POSTS_JS = r"""
(menuPattern) => [...document.querySelectorAll('[role=listitem]')].map((li, i) => {
  const menu = li.querySelector('button[aria-label^="Open control menu for post by"]');
  if (!menu) return null;
  const label = menu.getAttribute('aria-label') || '';
  const body = li.querySelector('[data-testid="expandable-text-box"]');
  const text = body ? (body.innerText || '').replace(/\s+/g, ' ').trim()
                    : (li.innerText || '').replace(/\s+/g, ' ').trim();
  // "Feed post <author> - <degree> <headline> <age> - <the post>". The age is
  // the last standalone token before the body that looks like 2w / 7h / 3d.
  const whole = (li.innerText || '').replace(/\s+/g, ' ').trim();
  const age = (whole.match(/\b(\d+\s*(?:s|m|h|d|w|mo|yr))\b/) || [null, null])[1];
  return {index: i, author: label.replace(/^Open control menu for post by\s*/, '').trim(),
          text: text.slice(0, 600), when: age};
}).filter(Boolean)
"""


def _copy_link(br, index):
    """The short link for card `index`, taken the way a person takes it: open
    that card's control menu, press "Copy link to post", read the clipboard.

    Returns (share_url, error). Never raises - a card whose link cannot be read
    is recorded with the reason, because a row silently dropped from a search is
    the same lie as an empty read.
    """
    menus = br.page.get_by_role("button", name=S.SEARCH_POST_MENU)
    if index >= menus.count():
        return None, "the card is no longer on the page"
    try:
        br.page.evaluate("() => navigator.clipboard.writeText('')")
    except Exception:
        pass
    try:
        menus.nth(index).click(timeout=10000)
        time.sleep(1.2)
        item = br.page.get_by_role("menuitem", name=S.COPY_LINK_ITEM).first
        item.wait_for(state="visible", timeout=8000)
        item.click(timeout=8000)
        time.sleep(1.0)
        got = br.page.evaluate("() => navigator.clipboard.readText().then(t => t).catch(e => '')")
    except Exception as exc:
        try:
            br.page.keyboard.press("Escape")
        except Exception:
            pass
        return None, str(exc).splitlines()[0][:120]
    m = S.SHORT_LINK.search(got or "")
    if not m:
        return None, "the clipboard held %r after Copy link to post" % (got or "")[:60]
    return m.group(0), None


def search_posts(a):
    q = _query(a)
    limit = _limit(a, "search-posts")
    if a.resolve and limit > RESOLVE_CAP:
        die("--resolve opens each post to read its permalink and is capped at %d rows a run; "
            "--limit is %d. Lower --limit to %d or fewer." % (RESOLVE_CAP, limit, RESOLVE_CAP))
    pace = Pace()
    with Browser(a.port) as br:
        root = br.browser.new_browser_cdp_session()
        try:
            root.send("Browser.grantPermissions", {"origin": "https://www.linkedin.com",
                                                   "permissions": ["clipboardReadWrite",
                                                                   "clipboardSanitizedWrite"]})
        except Exception as exc:
            die("could not grant clipboard access, which is how a post's own 'Copy link to post' "
                "hands over its link (%s)" % str(exc).splitlines()[0][:100])

        pace.before_view("a content search")
        final = br.read(CONTENT_URL % _quote(q), "the content search for %r" % q, settle=9)
        pace.after_view()
        if "/search/results/content" not in final:
            die("asked for a content search and landed on %s" % final)

        cards = br.page.evaluate(POSTS_JS, None)
        if not cards:
            die("no posts found for %r. Zero rows is a broken selector far more often than an "
                "empty result set, so this is a failure and not an empty list. The page was %s"
                % (q, final))
        cards = cards[:limit]

        rows = []
        for rank, c in enumerate(cards, 1):
            share, err = _copy_link(br, c["index"])
            rows.append({"kind": "post_result", "rank": rank, "author": c["author"] or None,
                         "text": c["text"] or None, "when": c["when"],
                         "share_url": share, "share_error": err,
                         "permalink": None, "resolve_error": None})
        missing = [r["rank"] for r in rows if not r["share_url"]]
        if len(missing) == len(rows):
            die("not one of the %d cards for %r gave up a link through 'Copy link to post'. "
                "That control is how this verb gets a post's address, so this is a failed read."
                % (len(rows), q))

        resolved = 0
        if a.resolve:
            for r in rows:
                if not r["share_url"]:
                    r["resolve_error"] = "no short link to resolve: " + (r["share_error"] or "")
                    continue
                # In the browser, never as an HTTP request made outside it. A post
                # permalink is not a profile and notifies nobody, so this costs a
                # navigation and NOT a view against the read cap.
                try:
                    br.goto(r["share_url"], settle=5)
                    dest = br.page.url
                except Exception as exc:
                    r["resolve_error"] = str(exc).splitlines()[0][:120]
                    continue
                urn = None
                m = ACTIVITY.search(dest)
                if m:
                    urn = m.group(0)
                else:
                    m = POSTS_PATH.search(dest)
                    if m:
                        urn = "urn:li:%s:%s" % (URN_KIND[m.group(1).lower()], m.group(2))
                if urn:
                    r["permalink"] = "https://www.linkedin.com/feed/update/%s/" % urn
                    resolved += 1
                else:
                    r["resolve_error"] = ("the short link went to %s, which carries neither a "
                                          "urn nor a -<kind>-<id> path" % dest[:140])

        for r in rows:
            print(json.dumps(r, ensure_ascii=True))
        line = "RESULT search-posts query=%r rows=%d links=%d" % (q, len(rows), len(rows) - len(missing))
        if a.resolve:
            line += " resolved=%d/%d" % (resolved, len(rows))
        print(line)


def _quote(s):
    from urllib.parse import quote
    return quote(s)
