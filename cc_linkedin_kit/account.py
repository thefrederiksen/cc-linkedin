# -*- coding: utf-8 -*-
"""Phase 2, the signed-in account's own surfaces: what happened to me, and how
my Page is doing. Read-only, JSON out.

MEASURED ON THE LIVE PAGE, 2026-09-09. Dumps in docs/surveys/.

NOTIFICATIONS - the classic rendering, and the cleanest surface in Phase 2.
  * article.nt-card, ten on the first page, each with data-nt-card-index and
    data-view-name="notification-card-container". Unread carries the extra
    class nt-card--unread and the accessible label "Unread notification.".
  * The actor is a[data-view-name="notification-card-image"], whose aria-label
    reads "View <name>'s profile." and whose href is that person's /in/ URL.
  * The text is a.nt-card__headline > .nt-card__text--3-line, and that anchor's
    href is where the notification points - which for a post carries the
    activity urn, url-encoded, as highlightedUpdateUrn.
  * The age is p.nt-card__time-ago.
  * It costs nothing against the SAFETY CAP: this is our own notifications
    page, not somebody's profile, and opening it tells nobody anything. It is
    still COUNTED, on the uncapped `view_self` line - F2, 2026-09-10. It counted
    nothing at all until then, which left one of this toolkit's own navigations
    invisible in pace.json and unreconcilable against a run's registry.
  * PUBLIC REPO. This output names third parties. It goes to stdout for the
    caller and is never pasted into a committed file.

PAGE STATS - and the trap that would have made it wrong forever.
  * THE TRAP. /admin/analytics/updates/ carries exactly one four-number
    headline card, and it is titled "Your profile view highlights". It is the
    signed-in MEMBER's own analytics widget, not the Page's. Its selector
    .member-analytics-addon-summary__list-item has four hits, the right shape
    and the right four labels - Impressions, Reactions, Comments, Reposts - and
    on 2026-09-09 it read 5 impressions while the Page's own table read 48 for
    the single post in the same window. Reading it returns a plausible, precise,
    wrong answer with no error, on every run, forever, and nothing downstream
    could catch it. So every number here is read from INSIDE the Content
    engagement table, and the table's header labels are asserted BEFORE any cell
    is read - a presence check, so that a layout change is loud instead of
    quiet.
  * The Page's real numbers are in a genuine <table>, headed Post title, Post
    type, Audience, Impressions, Views, Clicks, CTR, Reactions, Comments,
    Reposts, Follows, Engagement rate - one row per post.
  * The window is stated on button.org-analytics__time-range-dropdown-trigger,
    which reads "Time range: Aug 26, 2026 - Sep 9, 2026". Its dropdown offers
    Last 7 days / Last 15 days / Last 30 days / Last 12 weeks / Last 6 months /
    Last 12 months / Custom, then Cancel and Update. LinkedIn's own default is
    FIFTEEN days, not thirty, so a run that accepted the default would silently
    report half a window under a thirty-day name.
  * `followers` is in the admin header next to the Page name. Zero is a valid
    follower count - a new Page has none - so this fails on a value it cannot
    PARSE, never on a value it does not like.
"""
import datetime
import json
import re
import time

from . import selectors as S
from .browser import Browser, Pace, is_own_page, log, die
from .people import to_int

NOTIFICATIONS_URL = "https://www.linkedin.com/notifications/"
ANALYTICS_URL = "https://www.linkedin.com/company/%s/admin/analytics/updates/"

# The columns the Content engagement table must have before a single cell is
# read. A header that does not match is a FAIL, never a fall back to something
# else on the page.
REQUIRED_COLUMNS = ("Post title", "Impressions", "Reactions", "Comments", "Reposts")
SUM_COLUMNS = ("Impressions", "Views", "Clicks", "Reactions", "Comments", "Reposts")
SUM_SOURCE = "content-engagement-table-sum"
PRESETS = {7: "Last 7 days", 15: "Last 15 days", 30: "Last 30 days"}
RANGE_TRIGGER = "button.org-analytics__time-range-dropdown-trigger"


# ---------------------------------------------------------------- notifications

NOTIFICATIONS_JS = r"""
(sel) => [...document.querySelectorAll(sel.card)].map((c, i) => {
  const head = c.querySelector(sel.headline);
  const body = c.querySelector(sel.text);
  const actor = c.querySelector(sel.actor_link);
  const when = c.querySelector(sel.when);
  return {
    index: i,
    unread: c.className.indexOf(sel.unread) >= 0,
    text: body ? (body.innerText || '').replace(/\s+/g, ' ').trim()
               : (c.innerText || '').replace(/\s+/g, ' ').trim(),
    href: head ? head.getAttribute('href') || '' : '',
    actor_label: actor ? actor.getAttribute('aria-label') || '' : '',
    actor_url: actor ? (actor.getAttribute('href') || '').split('?')[0] : '',
    strong: body && body.querySelector('strong') ? body.querySelector('strong').innerText.trim() : '',
    when: when ? (when.innerText || '').replace(/\s+/g, ' ').trim() : ''
  };
})
"""


def notifications(a):
    limit = int(a.limit or 25)
    if limit < 1:
        die("--limit must be at least 1")
    pace = Pace()
    with Browser(a.port) as br:
        # F2, 2026-09-10. This used to count NOTHING - not even view_self - on
        # the grounds that our own notifications page costs the account nothing.
        # That is true and it is not the question: the view_self track exists so
        # that pace.json shows everything this toolkit opened, and a surface that
        # appears nowhere cannot be reconciled against a run's own registry. The
        # URL is a constant and it is ours, so this is the one call site where
        # the uncapped counter needs no test to reach it.
        pace.before_self_view("our own notifications page")
        final = br.read(NOTIFICATIONS_URL, "the notifications page", settle=8)
        pace.after_view()
        if "/notifications" not in final:
            die("asked for the notifications page and landed on %s" % final)

        rows = br.page.evaluate(NOTIFICATIONS_JS, S.NOTIFICATION)
        rows = [r for r in rows if r["text"]][:limit]
        if not rows:
            die("no notifications on %s. Zero rows is a broken selector far more often than an "
                "account with nothing waiting, so this is a failure and not an empty list "
                "(the card selector is %s)." % (final, S.NOTIFICATION["card"]))

        out = []
        for i, r in enumerate(rows, 1):
            am = S.NOTIFICATION_ACTOR.match(r["actor_label"] or "")
            url = r["href"]
            if url and url.startswith("/"):
                url = "https://www.linkedin.com" + url
            urn = None
            um = S.HIGHLIGHTED_URN.search(url or "")
            if um:
                from urllib.parse import unquote
                urn = unquote(um.group(1))
            rec = {"kind": "notification", "rank": i, "text": r["text"],
                   "actor": (am.group(1) if am else r["strong"]) or None,
                   "actor_url": ("https://www.linkedin.com" + r["actor_url"]
                                 if r["actor_url"].startswith("/") else r["actor_url"]) or None,
                   "url": url or None, "urn": urn,
                   "when": r["when"] or None, "unread": bool(r["unread"])}
            out.append(rec)
            print(json.dumps(rec, ensure_ascii=True))
        print("RESULT notifications rows=%d unread=%d"
              % (len(out), sum(1 for r in out if r["unread"])))


# ---------------------------------------------------------------- stats

STATS_JS = r"""
() => {
  const heads = [...document.querySelectorAll('h1,h2,h3')];
  const ce = heads.find(h => /Content engagement/i.test(h.innerText || ''));
  const sec = ce ? ce.closest('section, div[class*="card"]') : null;
  const table = sec ? sec.querySelector('table') : null;
  const h1 = document.querySelector('h1');
  // The follower count in the ADMIN HEADER, found by walking up from the page
  // name until an ancestor holds a leaf that reads "<n> followers". Scoped that
  // way so it cannot pick up a follower count belonging to some other page.
  let followers = '';
  if (h1) {
    let node = h1;
    for (let up = 0; up < 8 && node && !followers; up++) {
      node = node.parentElement;
      if (!node) break;
      for (const e of node.querySelectorAll('*')) {
        if (e.children.length === 0 && /^\s*[\d,]+\s+followers?\s*$/i.test(e.innerText || '')) {
          followers = e.innerText.trim();
          break;
        }
      }
    }
  }
  const trigger = document.querySelector('button.org-analytics__time-range-dropdown-trigger');
  return {
    pageName: h1 ? (h1.innerText || '').replace(/\s+/g, ' ').trim() : '',
    followers: followers,
    range: trigger ? (trigger.innerText || '').replace(/\s+/g, ' ').trim() : '',
    hasSection: !!sec,
    header: table ? [...table.querySelectorAll('th')].map(th => (th.innerText || '').replace(/\s+/g, ' ').trim()) : null,
    rows: table ? [...table.querySelectorAll('tbody tr')].map(tr =>
            [...tr.querySelectorAll('td')].map(td => (td.innerText || '').replace(/\s+/g, ' ').trim())) : null
  };
}
"""

def page_key(url):
    """The Page a /company/ URL is about, lower-cased, or None.

    MEASURED 2026-09-09 (docs/surveys/stats-2026-09-09.txt, header lines 3-4):
    the numeric Page id is preserved in the final URL of the analytics screen -
    request and final are the same string. So the requested Page and the landed
    Page are directly comparable, which is what ruling R4 needs.
    """
    m = re.search(r"/company/([^/?#]+)", url or "", re.I)
    return m.group(1).lower() if m else None


def rows_to_posts(header, rows, columns, to_number):
    """One record per table row, or a FAIL naming the row that could not be read.

    RULING R4. A row shorter than the header used to be silently skipped with
    `continue`, so a table caught mid-hydration - every row short - produced
    `posts: []` and a successful exit. An unreadable row is a failed read, not a
    row that is not there.
    """
    idx = {c: header.index(c) for c in header}
    out = []
    for i, row in enumerate(rows or [], 1):
        if len(row) < len(header):
            die("row %d of the Content engagement table has %d cells and the header has %d. "
                "A short row is a table read while it was still rendering, not a post with "
                "missing numbers, and skipping it would turn a half-read table into a "
                "confident smaller one." % (i, len(row), len(header)))
        rec = {"title": row[idx["Post title"]][:200]}
        for col in columns:
            if col in idx:
                raw = row[idx[col]]
                rec[col.lower() + "_raw"] = raw
                rec[col.lower()] = None if raw in ("-", "") else to_number(
                    raw.rstrip("%"), "%s for a post" % col)
        out.append(rec)
    return out


def sum_of_posts(posts, columns, source):
    """The per-column sums, with the cells that had no number COUNTED, not zeroed.

    RULING R4. `sum((p.get(key) or 0) for p in posts)` turned a cell reading "-"
    into a literal zero inside an aggregate, and the aggregate then looked like a
    measurement. A sum that skipped a post says so; a sum with nothing to add
    says that instead of saying nought.
    """
    out = {}
    for col in columns:
        key = col.lower()
        present = [p for p in posts if key in p]
        if not present:
            continue
        numbers = [p[key] for p in present if isinstance(p[key], int)]
        blank = len(present) - len(numbers)
        if not numbers:
            out[key] = {"value": None, "source": source, "posts_counted": 0,
                        "posts_without_a_number": blank,
                        "reason": "not one of the %d posts stated a %s" % (blank, col)}
        else:
            out[key] = {"value": sum(numbers), "source": source,
                        "posts_counted": len(numbers),
                        "posts_without_a_number": blank}
    return out


DATE = re.compile(r"([A-Z][a-z]{2})\s+(\d{1,2}),\s*(\d{4})")
MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}


def _window(range_text):
    """The window the page STATES, parsed. Never the window that was asked for -
    a run that reports its own argument back has proved nothing."""
    dates = DATE.findall(range_text or "")
    if len(dates) != 2:
        die("could not read the time range off the analytics page. The control reads %r and a "
            "window is what every number here is relative to, so this is a FAIL rather than a "
            "run with an unknown window." % (range_text or "(nothing)"))
    out = []
    for mon, day, year in dates:
        if mon not in MONTHS:
            die("the time range names a month this does not know: %r" % mon)
        out.append(datetime.date(int(year), MONTHS[mon], int(day)))
    start, end = out
    return start, end, (end - start).days + 1


def _stated_days(br):
    """How many days the control on screen currently says, or None if it will
    not parse. Read from the page, never from the argument."""
    trigger = br.page.locator(RANGE_TRIGGER).first
    if trigger.count() == 0:
        return None, ""
    text = trigger.inner_text().strip()
    dates = DATE.findall(text)
    if len(dates) != 2:
        return None, text
    try:
        d = [datetime.date(int(y), MONTHS[m], int(day)) for m, day, y in dates]
    except (KeyError, ValueError):
        return None, text
    return (d[1] - d[0]).days + 1, text


def _set_window(br, days):
    """Drive the time-range control to `days`.

    The condition it waits for is that the control STATES the window asked for -
    not that the text changed. An earlier version waited for a change, which
    would have failed on a page that already showed the right window: correct
    state, reported as a failure. LinkedIn's own default is 15 days, so skipping
    this altogether would report a fortnight under a thirty-day name.
    """
    if days not in PRESETS:
        die("--days %d is not one of the ranges the control offers (%s). Use one of those, or "
            "--days 0 to report whatever window the page is already showing."
            % (days, ", ".join(str(d) for d in sorted(PRESETS))))
    have, text = _stated_days(br)
    if have is None and not text:
        die("no time-range control on the analytics page (%s). It is what sets the window every "
            "number is relative to; without it nothing here can be labelled honestly."
            % RANGE_TRIGGER)
    if have == days:
        log("time range already reads %r" % text)
        return
    br.page.locator(RANGE_TRIGGER).first.click(timeout=10000)
    time.sleep(2)

    # The dropdown is found by what it CONTAINS, and waited for. Picking "the
    # first element carrying the open class" matched an EMPTY container on one
    # run and the right one on the next (measured 2026-09-09, 17:27 and 17:32):
    # the analytics screen has more than one dropdown, and the preset list is
    # rendered a moment after the control opens. A locator that is right most of
    # the time is the shape that fails on run two of three.
    option = None
    deadline = time.time() + 25
    while time.time() < deadline and option is None:
        cand = br.page.get_by_text(PRESETS[days], exact=True)
        for i in range(cand.count()):
            if cand.nth(i).is_visible():
                option = cand.nth(i)
                break
        if option is None:
            time.sleep(1)
    if option is None:
        offered = br.page.evaluate(
            """() => [...document.querySelectorAll('*')]
                 .filter(e => e.children.length === 0 && /^Last .+ (days|weeks|months)$/.test((e.innerText||'').trim()))
                 .map(e => e.innerText.trim())""")
        die("the time-range dropdown never offered %r in 25s after the control was opened. "
            "What it did offer was %s." % (PRESETS[days], ", ".join(offered) or "(nothing)"))
    option.click(timeout=8000)
    time.sleep(1.5)

    # MEASURED 2026-09-09: picking a preset applies it on the spot and closes the
    # dropdown. The Update button belongs to the Custom calendar underneath and
    # is only needed when the preset did not take.
    pressed = False
    deadline = time.time() + 40
    while time.time() < deadline:
        have, text = _stated_days(br)
        if have == days:
            log("time range now reads %r" % text)
            return
        if not pressed and time.time() > deadline - 28:
            pressed = True
            try:
                update = br.page.get_by_role("button", name=re.compile(r"^\s*Update\s*$")).first
                if update.count() and update.is_visible():
                    br.press(update, "Update (time range)")
            except Exception:
                pass
        time.sleep(1.5)
    die("the time range reads %r after choosing %r, which is %s days, not %d. The window every "
        "number is relative to was not set, so nothing here can be labelled honestly."
        % (text, PRESETS[days], have, days))


def stats(a):
    days = int(a.days if a.days is not None else 30)
    pace = Pace()
    with Browser(a.port) as br:
        # F2, 2026-09-10, and the branch matters here in a way it does not in
        # notifications. --page is an ARGUMENT: whatever it names, this is about
        # to open that Page's admin URL in the signed-in browser. So view_self
        # is taken only where the Page is positively one of the owner's, exactly
        # as read_company does it, and anything else is charged to the safety
        # number. A Page we do not administer fails the landing assertions a few
        # lines below - but the page has been opened by then, and the counter has
        # to have seen it.
        if is_own_page(a.page):
            pace.before_self_view("the analytics for Page %s (one the owner administers)" % a.page)
        else:
            pace.before_view("the analytics for Page %s" % a.page)
        final = br.read(ANALYTICS_URL % a.page, "the analytics for Page %s" % a.page, settle=10)
        pace.after_view()
        if "/admin/analytics" not in final:
            die("could not open the analytics for Page %s as this identity; landed on %s. "
                "That is a failed read, not a Page with no numbers." % (a.page, final))
        # RULING R4: prove this is the Page that was ASKED FOR before reading a
        # number off it. The only check here used to be for the generic
        # /admin/analytics path, so a bad or unauthorised --page redirected to
        # another administered Page produced that Page's numbers labelled with
        # the requested id - precise, plausible and wrong, on every run.
        landed, wanted = page_key(final), str(a.page).lower()
        if landed != wanted:
            die("asked for Page %r and the analytics screen that opened belongs to Page %r "
                "(%s). Refusing to report one Page's numbers under another Page's name - a "
                "redirect is not a permission." % (wanted, landed, final))

        if days:
            _set_window(br, days)
            time.sleep(2)

        d = br.page.evaluate(STATS_JS)
        if not d["pageName"]:
            die("no Page name on %s; a changed layout, not a Page without a name" % final)
        if a.page_name and d["pageName"] != a.page_name:
            die("the analytics page names %r and --page-name says %r; refusing to report one "
                "Page's numbers under another Page's name" % (d["pageName"], a.page_name))
        if not d["hasSection"]:
            die("no 'Content engagement' section on %s. Every Page number this verb reports comes "
                "from that table; the only other four-number card on this screen is the member's "
                "own profile-view widget and it is NOT the Page's data." % final)
        if d["header"] is None:
            die("the 'Content engagement' section has no table in it")

        header = d["header"]
        # RULING R4: an unreadable table body is a FAIL, not a set of zeroes. The
        # header assertion below proves the SCHEMA is the one this was written
        # against; it says nothing about whether a single number is present, and
        # a correct table whose tbody is empty after the range refresh used to
        # exit successfully with posts: [] and RESULT ... impressions=0.
        if not d["rows"]:
            die("the Content engagement table on %s has no rows in it. A Page with no posts "
                "in the window is a real answer and would still render its table - an empty "
                "tbody is a table read before it filled, and reporting zeroes off it is the "
                "quiet version of an empty read." % final)
        missing = [c for c in REQUIRED_COLUMNS if c not in header]
        if missing:
            die("the Content engagement table is not the table this was written against: it is "
                "missing the columns %s. Its header reads %s. Refusing to read cells out of a "
                "table whose columns are not the ones expected."
                % (", ".join(missing), ", ".join(header) or "(nothing)"))

        start, end, window_days = _window(d["range"])
        if days and window_days != days:
            die("asked for a %d-day window and the page states %s to %s, which is %d days. "
                "Refusing to report %d days of numbers under a %d-day name."
                % (days, start, end, window_days, window_days, days))

        followers_raw = d["followers"]
        if not followers_raw:
            die("no follower count in the admin header next to %r. Zero followers is a valid "
                "answer and would read '0 followers'; nothing at all is a changed layout."
                % d["pageName"])
        followers = to_int(re.match(r"^\s*([\d,]+)", followers_raw).group(1), "the follower count")

        posts = rows_to_posts(header, d["rows"], SUM_COLUMNS, to_int)

        # The sum is called what it is. A Page's real impressions are NOT the sum
        # of its posts' impressions - they include arrivals the table never lists -
        # so a field called `totals` would be read as LinkedIn's own aggregate by
        # every caller who skipped the provenance string. The name carries the
        # meaning because the name is what gets used.
        sums = sum_of_posts(posts, SUM_COLUMNS, SUM_SOURCE)

        rec = {
            "kind": "page_stats", "page": str(a.page), "name": d["pageName"],
            "window_start": start.isoformat(), "window_end": end.isoformat(),
            "window_days": window_days, "window_raw": d["range"],
            "window_driven": bool(days),
            "followers": followers, "followers_raw": followers_raw,
            "posts": posts, "sum_of_posts": sums,
            "rendering": "ember",
        }
        print(json.dumps(rec, ensure_ascii=True))
        # Never `.get("value", 0)`: an absent aggregate printed as 0 is a number
        # that was never read, wearing the clothes of one that was (ruling R4).
        impressions = sums.get("impressions", {}).get("value")
        print("RESULT stats page=%s name=%r followers=%d window=%dd (%s..%s) posts=%d "
              "impressions=%s"
              % (a.page, d["pageName"], followers, window_days, start, end, len(posts),
                 impressions if impressions is not None else "not-stated"))
