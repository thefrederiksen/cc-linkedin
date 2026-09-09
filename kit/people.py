# -*- coding: utf-8 -*-
"""Phase 2 entity reads: one person, one company. Read-only, JSON out.

THE RULE THIS WHOLE MODULE HANGS ON: a read that comes back empty is a FAILURE,
never a result. The natural shape of a read verb is "no exception was raised, so
print what we found", and handed a login wall, a changed layout or a throttled
page that shape prints an empty record and exits 0, and every caller downstream
believes it. So every verb here names its REQUIRED fields, asserts the identity
control is PRESENT before it reads anything, and asserts the entity it landed on
is the one it was asked for.

MEASURED ON THE LIVE PAGE, 2026-09-09. Dumps in docs/surveys/.

  * A profile is served ONLY in the new server-driven React rendering. Four
    loads, minutes apart: [data-urn] 0 every time, and every classic selector
    the open-source LinkedIn tools are written against returns 0 - .pv-top-card,
    h1, .text-body-medium, .artdeco-card, .pv-text-details__left-panel. There is
    no classic rendering of a profile to fall back to.
  * What IS stable there is the element ID, generated from the server-driven
    component name: the top card's id ends "Topcard" and the about card's ends
    "About". The class names are hashed and meaningless.
  * The name is the top card's only h2. The headline, the current company and
    school, and the location are <p> elements in that card, in that order.
  * THE DEGREE BADGE IS RENDERED TWICE AND THE TWO CAN DISAGREE. On a
    1st-degree profile the top card held a <p> reading "- 1st" and, inside a
    div[data-display-contents], a second <p> reading "- 2nd". Only one is
    visible. Taking the first in document order would have been a coin flip, so
    this reads the visible ones and FAILS if two visible badges disagree.
  * The current company and school are ALSO rendered twice - once as a
    "-"-joined paragraph, once as a row of pills - and only one is visible.
  * On the owner's OWN profile there is no Connect, Pending, Message or Follow
    control at all: the top card's controls read Open to / Add section / Add
    custom button / Resources / More. So degree is "self" and connection_state
    is null there, and that is why this verb cannot be proven on his profile
    alone. Acceptance row P2-2 is the one that exercises the other half.
  * A Page ADMIN is redirected. /company/107519091/ and
    /company/centerconsulting-inc/about/ both ended on /admin/dashboard/.
    ?viewAsMember=true served the ordinary member page with no redirect, so that
    is the URL read-company uses - and it asserts the final URL still carries
    it, because a redirect that is absorbed silently is a read of the wrong
    page.
  * The company page is the CLASSIC rendering: .org-top-card-summary__title,
    .org-top-card-summary__tagline, .org-top-card-summary-info-list__info-item
    for industry / location / followers / size, and a dl of Website, Industry,
    Company size, Headquarters.
"""
import json
import re
import time

from . import selectors as S
from .browser import Browser, Pace, log, die

SLUG = re.compile(r"/in/([^/?#]+)")
COMPANY_SLUG = re.compile(r"/company/([^/?#]+)")

# LinkedIn separates the entries of a line with a middle dot and marks a
# truncated block with a horizontal ellipsis. Both are written as chr() so this
# source file stays plain ASCII and no editor, patch or shell can mangle them.
MIDDOT = chr(0x00B7)
BULLET = chr(0x2022)
ELLIPSIS = chr(0x2026)


# ---------------------------------------------------------------- numbers

def to_int(raw, what):
    """'1,234' and '1.2K' both become an integer. A value that will not parse is
    a FAIL - never a null, and never the raw string smuggled into a number."""
    if raw is None:
        die("no %s on the page at all; refusing to report a number that was never read" % what)
    t = str(raw).strip().replace(",", "").replace("+", "")
    m = re.match(r"^(\d+(?:\.\d+)?)\s*([KMB])?$", t, re.I)
    if not m:
        die("%s reads %r, which is not a number" % (what, str(raw)[:40]))
    n = float(m.group(1))
    if m.group(2):
        n *= {"K": 1e3, "M": 1e6, "B": 1e9}[m.group(2).upper()]
    return int(round(n))


# ---------------------------------------------------------------- read-profile

TOPCARD_JS = r"""
(sel) => {
  const card = document.querySelector(sel);
  if (!card) return null;
  const vis = e => !!(e.offsetParent || e.getClientRects().length);
  const h2 = card.querySelector('h2');
  const ps = [...card.querySelectorAll('p')].map(p => ({
      text: (p.innerText || '').replace(/\s+/g, ' ').trim(),
      visible: vis(p),
      contact: !!p.querySelector('a[href*="/overlay/contact-info/"]')}))
    .filter(p => p.text);
  const actions = [...card.querySelectorAll('button, a, [role=button]')]
    .filter(vis)
    .map(e => (e.innerText || e.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim())
    .filter(Boolean);
  const contactBox = card.querySelector('a[href*="/overlay/contact-info/"]');
  const location = contactBox
      ? (() => { const p = contactBox.closest('p');
                 const box = p ? p.parentElement : null;
                 if (!box) return '';
                 const first = [...box.querySelectorAll(':scope > p')][0];
                 return first ? (first.innerText || '').replace(/\s+/g, ' ').trim() : ''; })()
      : '';
  return {name: h2 ? (h2.innerText || '').replace(/\s+/g, ' ').trim() : '',
          ps: ps, actions: actions, location: location};
}
"""


def _degree(card, name):
    """The VISIBLE degree badge. Two visible badges that disagree are a FAIL."""
    seen = []
    for p in card["ps"]:
        m = S.DEGREE_TEXT.match(p["text"])
        if m and p["visible"]:
            v = m.group(1).lower()
            if v not in seen:
                seen.append(v)
    if len(seen) > 1:
        die("the top card shows two different visible degree badges (%s) for %r; "
            "refusing to guess which one is the truth" % (", ".join(seen), name))
    return seen[0] if seen else None


def _current(lines):
    """The current company, as the top card gives it.

    The TITLE is not on the top card - it lives in the Experience card, which
    Phase 2 does not open - so it is reported as null WITH the reason, rather
    than inferred from the headline. A headline is what somebody wrote about
    themselves; it is not a job title, and putting it in a title field would be
    a guess that every caller reads as a fact.
    """
    if len(lines) < 2:
        return None
    parts = [p.strip() for p in lines[1].split(MIDDOT) if p.strip()]
    if not parts:
        return None
    return {"company": parts[0], "company_url": None, "title": None,
            "title_source": "not on the top card; it is in the Experience card, "
                            "which this verb does not open",
            "line": lines[1]}


def _about(br):
    """The About card, expanded past its own collapse control if it has one.

    MEASURED 2026-09-09: that control reads "... more", not "see more". A
    matcher for "see more" alone leaves the text truncated and the record then
    carries a shortened About that looks complete, which is the quiet version of
    an empty read.
    """
    card = br.page.locator(S.PROFILE_ABOUT_CARD).first
    if card.count() == 0:
        return None
    for _ in range(3):
        try:
            more = card.get_by_role("button", name=S.PROFILE_SEE_MORE).first
            if not more.count() or not more.is_visible():
                break
            more.click(timeout=4000)
            time.sleep(1.2)
        except Exception:
            break
    text = card.inner_text().strip()
    text = re.sub(r"^About\s*", "", text)
    text = re.sub(ELLIPSIS + r"?\s*(?:see\s+)?(?:more|less)\s*$", "", text, flags=re.I).strip()
    return text or None


def _followers(br):
    """Follower count, scoped to THIS profile's own Activity card.

    The page's right-hand rail carries OTHER people's follower counts, in the
    millions (measured on Soren's own profile: 3,451,579 and 1,368,932). Reading
    "followers" off the whole page would return one of those - precisely, and
    wrongly, on every single run.
    """
    card = br.page.locator(S.PROFILE_ACTIVITY_CARD).first
    if card.count() == 0:
        return None
    for line in card.inner_text().splitlines():
        m = S.COUNT_LINE.match(line.strip())
        if m and m.group(2).lower().startswith("follower"):
            return line.strip()
    return None


def read_profile(a):
    url = a.url if a.url.startswith("http") else "https://www.linkedin.com/in/%s/" % a.url.strip("/")
    m = SLUG.search(url)
    if not m:
        die("not a profile URL (no /in/ in it): %s" % a.url)
    want = m.group(1).lower()
    pace = Pace()
    with Browser(a.port) as br:
        pace.before_view("profile %s" % want)
        final = br.read(url, "the profile %s" % want, settle=7)
        pace.after_view()

        got = SLUG.search(final)
        if not got or got.group(1).lower() != want:
            die("asked for the profile %r and landed on %r (%s)"
                % (want, got.group(1) if got else "(no /in/)", final))

        card = br.page.evaluate(TOPCARD_JS, S.PROFILE_TOPCARD)
        if card is None:
            die("no profile top card on %s (selector %s). LinkedIn has changed the profile "
                "layout, or this is not a profile page." % (final, S.PROFILE_TOPCARD))

        name = card["name"]
        if not name:
            die("the top card on %s has no name in it; that is not a read, it is a blank page" % final)

        degree = _degree(card, name)
        state = next((s for s in S.CONNECTION_STATES
                      if any(t == s or t.startswith(s + " ") for t in card["actions"])), None)
        if degree is None and state is None:
            degree = "self"          # no badge and no primary action: this profile is ours
        reason = None
        if degree is None:
            reason = "no visible degree badge on the top card; the primary action reads %r" % state
            log(reason)

        # The lines that are not a degree badge, not the separator dot, not a
        # count and not the contact-info link, in document order: the headline
        # first, then the current company and school.
        lines = [p["text"] for p in card["ps"]
                 if p["visible"] and not p["contact"]
                 and not S.DEGREE_TEXT.match(p["text"])
                 and not S.COUNT_LINE.match(p["text"])
                 and p["text"] not in (MIDDOT, BULLET, "Contact info")
                 and p["text"] != card["location"]]
        headline = lines[0] if lines else ""
        if not headline:
            die("the top card for %r has a name but no headline. Every profile has one, so this "
                "is a changed layout, not a person who left it blank." % name)

        if a.expect:
            hay = " ".join([name, headline] + lines).lower()
            if a.expect.lower() not in hay:
                die("the profile does not mention %r; refusing to report it. It reads %r / %r"
                    % (a.expect, name, headline[:60]))
            log("profile verified: contains %r" % a.expect)

        connections = None
        for p in card["ps"]:
            cm = S.COUNT_LINE.match(p["text"])
            if p["visible"] and cm and cm.group(2).lower().startswith("connection"):
                connections = p["text"]
                break

        rec = {
            "kind": "profile", "url": final.split("?")[0], "slug": want, "name": name,
            "headline": headline,
            "location": card["location"] or None,
            "about": _about(br),
            "current": _current(lines),
            "degree": degree,
            "degree_reason": reason,
            "connection_state": state,
            "connections": connections,
            "followers": _followers(br),
            "rendering": "react",
        }
        print(json.dumps(rec, ensure_ascii=True))
        print("RESULT read-profile slug=%s name=%r degree=%s state=%s about=%d chars"
              % (want, name, degree, state, len(rec["about"] or "")))


# ---------------------------------------------------------------- read-company

COMPANY_JS = r"""
(sel) => {
  const one = s => { const e = document.querySelector(s); return e ? (e.innerText || '').replace(/\s+/g,' ').trim() : ''; };
  const details = {};
  for (const dl of document.querySelectorAll('dl')) {
    let term = null;
    for (const kid of dl.children) {
      const t = (kid.innerText || '').replace(/\s+/g, ' ').trim();
      if (kid.tagName === 'DT') { term = t; }
      else if (kid.tagName === 'DD' && term) {
        if (!details[term]) details[term] = t;
        const link = kid.querySelector('a[href]');
        if (link && !details[term + ' href']) details[term + ' href'] = link.getAttribute('href');
      }
    }
  }
  return {
    name: one(sel.name), tagline: one(sel.tagline),
    info: [...document.querySelectorAll(sel.info_item)].map(e => (e.innerText||'').replace(/\s+/g,' ').trim()).filter(Boolean),
    about: one(sel.about),
    details: details
  };
}
"""


def read_company(a):
    key = a.url.strip("/")
    m = COMPANY_SLUG.search(a.url)
    if m:
        key = m.group(1)
    url = S.COMPANY_MEMBER_VIEW % key
    pace = Pace()
    with Browser(a.port) as br:
        pace.before_view("company %s" % key)
        final = br.read(url, "the company page %s" % key, settle=7)
        pace.after_view()

        if "viewAsMember=true" not in final:
            die("asked for the member view of %r and was sent to %s instead. A Page admin is "
                "redirected to the admin dashboard; the member view is what read-company reports, "
                "so this is a failed read and not a different page worth reporting." % (key, final))
        got = COMPANY_SLUG.search(final)
        if not got or got.group(1).lower() != key.lower():
            die("asked for the company %r and landed on %r (%s)"
                % (key, got.group(1) if got else "(no /company/)", final))

        c = br.page.evaluate(COMPANY_JS, S.COMPANY)
        if not c["name"]:
            die("no company name on %s (selector %s); a changed layout, not an empty page"
                % (final, S.COMPANY["name"]))

        raw = next((i for i in c["info"] if S.FOLLOWERS_ITEM.match(i)), None)
        if raw is None:
            die("no follower count on the company page for %r. It is one of the items in the top "
                "card summary and it was there when this was measured, so its absence is a changed "
                "layout - not a company with no followers." % c["name"])
        followers = to_int(S.FOLLOWERS_ITEM.match(raw).group(1), "the follower count")

        d = c["details"]
        rec = {
            "kind": "company", "url": final.split("?")[0], "slug": key, "name": c["name"],
            "tagline": c["tagline"] or None,
            "industry": d.get("Industry") or None,
            "followers": followers, "followers_raw": raw,
            "size": d.get("Company size") or None,
            "website": d.get("Website href") or d.get("Website") or None,
            "location": d.get("Headquarters") or None,
            "about": c["about"] or None,
            "rendering": "ember",
        }
        print(json.dumps(rec, ensure_ascii=True))
        print("RESULT read-company slug=%s name=%r followers=%d about=%d chars"
              % (key, c["name"], followers, len(rec["about"] or "")))
