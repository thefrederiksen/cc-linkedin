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
  * The name is the top card's only h2.
  * NOTHING ELSE ON THE TOP CARD IS FOUND BY POSITION, and the reason is a
    defect this module shipped with. The headline and the employer used to be
    "the first and second surviving paragraph of the card". Re-measured
    2026-09-09 on six profiles, three paragraphs the filter did not recognise
    turn up in that run and shift everything after them: a pronoun ("He/Him",
    FIRST on profiles C and E below), the two halves of a connections count that
    three of the six split into separate paragraphs ("500+", then
    "connections"), and a mutual-connections sentence. On one real profile
    that reported "500+" - a connections count - as the employer. Every field
    below is now identified by something that says what it IS:
      - headline and the "Company - School" line: the direct <p> children of the
        identity block, which is found from the "Contact info" link. Pronouns
        and degree badges live in a different box and cannot reach it.
      - the current employer: the pill carrying svg[id^="company-"]. No company
        pill means no employer is stated, and the field says so.
      - the primary action: the one control painted rgb(10, 102, 194). It is not
        always the leftmost.
      - the connections count: matched against the whole card's normalised text,
        so a count split across two paragraphs is still one count.
  * THE DEGREE BADGE IS RENDERED TWICE AND THE TWO CAN DISAGREE. On a
    1st-degree profile the top card held a <p> reading "- 1st" and, inside a
    div[data-display-contents], a second <p> reading "- 2nd". Only one is
    visible. Taking the first in document order would have been a coin flip, so
    this reads the visible ones and FAILS if two visible badges disagree.
  * The current company and school are ALSO rendered twice - once as a
    "-"-joined paragraph, once as a row of pills - and only one is visible.
  * On the owner's OWN profile there is no Connect, Pending, Message or Follow
    control at all: the top card's row reads Open to / Add section / Add custom
    button / Resources, with the primary fill on "Open to". So degree is "self"
    and can_connect is null there, and that is why this verb cannot be proven on
    his profile alone. Acceptance rows P2-2 and P2-10 exercise the other half.
  * WHERE THE INVITATION LIVES CHANGES FROM PROFILE TO PROFILE, and the primary
    button does not tell you which. Measured 2026-09-09:
      - profile B (2nd degree): row "Connect Message More", Connect filled
        and on the card, href /preload/custom-invite/?vanityName=<slug>.
      - profile E (3rd, a very large following): row "Follow Connect Visit my
        website More" - Connect on the card but NOT the primary.
      - profiles D and F (3rd): row "Message Follow More" - no Connect on the
        card at all, the invitation is a More-menu item, and the FILLED control
        is Message.
      - profile A (a connection already): no invite control anywhere; the More
        menu offers "Remove connection" instead.
    The six are lettered rather than named because this repository is PUBLIC and
    no third party's URL, name or headline goes in it - here, in the docs, or in
    an evidence file. The letters distinguish the six measurements from each
    other and nothing more; who they were is deliberately recorded nowhere.
    So `can_connect` is answered from the invite control wherever it is, the
    More menu is opened only when the card has none, and what the primary button
    says is reported separately as `primary_button` and never conflated with it.
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
from .browser import Browser, Pace, is_own_page, is_own_profile, log, die

SLUG = re.compile(r"/in/([^/?#]+)")
COMPANY_SLUG = re.compile(r"/company/([^/?#]+)")

# LinkedIn separates the entries of a line with a middle dot and marks a
# truncated block with a horizontal ellipsis. Both are written as chr() so this
# source file stays plain ASCII and no editor, patch or shell can mangle them.
MIDDOT = chr(0x00B7)
BULLET = chr(0x2022)
ELLIPSIS = chr(0x2026)


# ---------------------------------------------------------------- numbers

# THE NUMBER GRAMMAR - ruling R6, 2026-09-09.
#
# This used to be `.replace(",", "").replace("+", "")` and then a match. Stripping
# the separators BEFORE deciding what they meant is the whole defect: the
# European `1,2K` became `12K` and returned 12000 instead of 1200 - wrong by a
# factor of ten, silently, in a field a caller writes straight into a CRM - and
# `12+3` became `123`. So the separators are now part of the grammar and every
# ambiguous form fails loudly.
#
#   groups      1,234 and 1,234,567: a comma is a thousands separator only when
#               it is followed by EXACTLY three digits, in a well-formed group.
#   decimal     1.2K, 12.5K, 1.2M: a decimal point is only a decimal point when a
#               K, M or B follows it. A bare `1.234` is 1234 in a European
#               rendering and 1.234 in an English one and nothing on the page
#               says which, so it fails rather than picking one.
#   plus        500+ and 1,234+: a plus is stripped only when TRAILING. Anywhere
#               else it means this is not a number.
#
# NOT MEASURED, AND IT DECIDES ONE CASE. R6.1 leaves it to this pass whether
# `1,2` is accepted as a decimal comma or fails, after measuring what LinkedIn
# renders in a European locale. That measurement needs the live site in another
# locale and the daily view cap was spent, so IT WAS NOT MADE and the form FAILS
# - R6.3's default, and the only safe direction, because accepting it means
# guessing between 1200 and 12 with no evidence and the wrong guess is silent.
# Every English label this toolkit asserts on says the rendering it reads is the
# English one, where the form should not occur; if it ever does, a person finds
# out instead of a CRM.
NUMBER = re.compile(r"""
    ^\s*
    (?P<int> \d{1,3}(?:,\d{3})+ | \d+ )      # 1,234,567 or 1234 - never 1,23
    (?: \.(?P<frac> \d+) )?                  # .2, only legal with a multiplier
    \s*
    (?P<mult> [KMB] )?
    \s*
    (?P<plus> \+ )?                           # a lower-bound marker, trailing only
    \s*$
""", re.I | re.X)
MULTIPLIER = {"K": 1000, "M": 1000000, "B": 1000000000}


def to_int(raw, what):
    """'1,234' and '1.2K' become integers. Anything ambiguous is a FAIL - never a
    null, never the raw string smuggled into a number, and never a guess between
    two readings that differ by a factor of ten."""
    if raw is None:
        die("no %s on the page at all; refusing to report a number that was never read" % what)
    t = str(raw).strip()
    m = NUMBER.match(t)
    if not m:
        die("%s reads %r, which is not a number this will guess at. A comma is a thousands "
            "separator only before exactly three digits, a decimal point is only allowed with "
            "a K, M or B after it, and a plus is only allowed at the end."
            % (what, str(raw)[:40]))
    if m.group("frac") and not m.group("mult"):
        die("%s reads %r. A bare decimal point is ambiguous - that is 1234 in a European "
            "rendering and about 1 in an English one - so it is refused rather than read as "
            "one of them." % (what, str(raw)[:40]))
    n = float(m.group("int").replace(",", ""))
    if m.group("frac"):
        n = float("%s.%s" % (m.group("int").replace(",", ""), m.group("frac")))
        n *= MULTIPLIER[m.group("mult").upper()]
    elif m.group("mult"):
        n *= MULTIPLIER[m.group("mult").upper()]
    return int(round(n))


# ---------------------------------------------------------------- read-profile

TOPCARD_JS = r"""
([sel, cfg]) => {
  const card = document.querySelector(sel);
  if (!card) return null;
  const vis = e => !!(e.offsetParent || e.getClientRects().length);
  const clean = t => (t || '').replace(/\s+/g, ' ').trim();
  const h2 = card.querySelector('h2');

  // THE IDENTITY BLOCK, found from the "Contact info" link rather than by
  // counting paragraphs. That link sits in the location box, and the location
  // box's parent is the block whose own direct <p> children are the headline
  // and (when there is one) the "Company - School" line. Everything that used
  // to shift the paragraph order - a pronoun, a degree badge, a bare "500+" -
  // lives in a DIFFERENT box, so none of it can move these two.
  const contact = card.querySelector('a[href*="/overlay/contact-info/"]');
  const locBox = contact ? (contact.closest('p') || {}).parentElement || null : null;
  const block = locBox ? locBox.parentElement : null;
  const blockPs = block
      ? [...block.children].filter(c => c.tagName === 'P')
          .map(p => ({text: clean(p.innerText), visible: vis(p)})).filter(p => p.text)
      : [];
  const location = locBox
      ? (() => { const first = [...locBox.children].find(c => c.tagName === 'P');
                 return first ? clean(first.innerText) : ''; })()
      : '';

  // THE CURRENT EMPLOYER, identified by the icon on its own pill. A company
  // pill carries svg[id^="company-"], a school pill svg[id^="school-"]. This is
  // a positive identification of the thing itself, which no count and no line
  // of text can impersonate.
  const pill = prefix => [...card.querySelectorAll('svg[id^="' + prefix + '"]')].map(s => {
      const box = s.closest('[role=button]') || s.parentElement;
      return {text: clean(box ? box.innerText : ''), visible: vis(box),
              href: (box && box.getAttribute) ? (box.getAttribute('href') || '') : ''};
    }).filter(p => p.text);

  // THE ACTION ROW. Every visible control, with the fill LinkedIn paints on the
  // one primary action (on an inner span, never on the control itself) and the
  // geometry needed to group the row. Which one is primary, and which of them
  // sit on the same line, is decided in Python.
  const controls = [...card.querySelectorAll('a, button')].filter(vis).map(e => {
      const r = e.getBoundingClientRect();
      return {tag: e.tagName, text: clean(e.innerText),
              aria: e.getAttribute('aria-label') || '',
              href: e.getAttribute('href') || '',
              // Ruling R5: a control that cannot be pressed must not be read as
              // one that can. Never checked before.
              disabled: e.disabled === true
                        || e.getAttribute('aria-disabled') === 'true'
                        || e.getAttribute('disabled') !== null,
              filled: [e, ...e.querySelectorAll('*')]
                  .some(n => getComputedStyle(n).backgroundColor === cfg.fill),
              x: Math.round(r.left), y: Math.round(r.top)};
    }).filter(c => c.text || c.aria);

  return {name: h2 ? clean(h2.innerText) : '',
          blockPs: blockPs, location: location,
          companies: pill('company-'), schools: pill('school-'),
          controls: controls,
          degrees: [...card.querySelectorAll('p')]
              .filter(p => vis(p)).map(p => clean(p.innerText)).filter(Boolean),
          text: clean(card.innerText)};
}
"""

# RULING R5. This used to query the WHOLE DOCUMENT for [role=menuitem], so an
# unrelated open menu elsewhere on the page could supply the item that proves
# "the menu rendered" while the menu we actually opened was still empty - and
# the verb would then report can_connect: false from a menu it never read. It
# now finds the visible menus, requires there to be exactly ONE, and reads only
# inside it. Two visible menus is a page state this was not written against and
# is reported as such rather than guessed through.
MENU_JS = r"""
(sel) => {
  const vis = e => !!(e.offsetParent || e.getClientRects().length);
  const clean = t => (t || '').replace(/\s+/g, ' ').trim();
  const menus = [...document.querySelectorAll('[role=menu]')].filter(vis);
  const scope = menus.length === 1 ? menus[0] : null;
  const items = scope ? [...scope.querySelectorAll(sel)].filter(vis) : [];
  return {menus: menus.length,
          items: items.map(e => ({
              text: clean(e.innerText), aria: e.getAttribute('aria-label') || '',
              href: e.getAttribute('href') || '',
              disabled: e.getAttribute('aria-disabled') === 'true'
                        || e.getAttribute('disabled') !== null}))};
}
"""


def _degree(card, name):
    """The VISIBLE degree badge. Two visible badges that disagree are a FAIL."""
    seen = []
    for text in card["degrees"]:
        m = S.DEGREE_TEXT.match(text)
        if m:
            v = m.group(1).lower()
            if v not in seen:
                seen.append(v)
    if len(seen) > 1:
        die("the top card shows two different visible degree badges (%s) for %r; "
            "refusing to guess which one is the truth" % (", ".join(seen), name))
    return seen[0] if seen else None


def _headline(card, name):
    """The headline: the first visible <p> that is a DIRECT child of the identity
    block, which is found from the "Contact info" link and not by counting.

    WHY IT IS NOT lines[0] ANY MORE (measured 2026-09-09). The old code took
    every visible paragraph in the whole top card, dropped the ones it
    recognised, and then trusted document order: [0] was the headline and [1]
    the employer. Three separate paragraphs it did not recognise sit in that
    run on real profiles - a pronoun ("He/Him", FIRST, on two of the six
    profiles measured), the two halves of a split connections count ("500+" then
    "connections"), and a mutual-connections sentence - so the position of a
    field was a property of who the person was. On one profile that put "500+"
    in the employer field; on another it would have put "He/Him" in the
    headline. Position is not identification.
    """
    for p in card["blockPs"]:
        if not p["visible"]:
            continue
        t = p["text"]
        if S.DEGREE_TEXT.match(t) or S.COUNT_LINE.match(t) or S.BARE_COUNT.match(t):
            continue
        if t in (MIDDOT, BULLET):
            continue
        return t
    die("no headline on the top card for %r. It is the first visible paragraph of the "
        "identity block and every profile has one, so this is a changed layout, not a "
        "person who left it blank." % name)


def _current(card, name, headline):
    """The current employer, read from the pill that carries the COMPANY icon.

    THE DEFECT THIS REPLACES (measured 2026-09-09). This used to be the second
    surviving paragraph of the top card, and on a real 2nd-degree profile that
    paragraph was "500+" - the connections count - which the verb then reported
    as the employer, in a field a caller would write straight into a CRM. The
    fix is not a better filter on that paragraph. It is to stop reading a
    position and start reading the thing itself: LinkedIn draws a company pill
    with a company icon and a school pill with a school icon, and a count has
    neither. No company pill means NO COMPANY IS SHOWN, and this says so.

    The "Company - School" paragraph is still read, but only as a CHECK: when
    both are present and they disagree, the top card is not saying one thing and
    we do not get to pick.

    The TITLE is not on the top card at all - it lives in the Experience card,
    which Phase 2 does not open - so it stays null WITH the reason. A headline
    is what somebody wrote about themselves; it is not a job title.
    """
    line = None
    for p in card["blockPs"]:
        t = p["text"]
        if S.DEGREE_TEXT.match(t) or S.COUNT_LINE.match(t) or S.BARE_COUNT.match(t):
            continue
        if t in (MIDDOT, BULLET) or t == headline:
            continue
        line = t
        break

    if not card["companies"]:
        return {"company": None,
                "company_reason": "the top card shows no company pill, so no current employer "
                                  "is stated on it" + (
                                      "; the line %r is there but its first entry cannot be told "
                                      "apart from a school without the pill" % line[:60]
                                      if line else ""),
                "company_url": None, "title": None, "title_source": TITLE_SOURCE, "line": line}

    company = card["companies"][0]["text"]
    if S.BARE_COUNT.match(company) or S.COUNT_LINE.match(company):
        die("the company pill on %r reads %r, which is a count and not an employer; "
            "refusing to report it" % (name, company))
    if line:
        first = [p.strip() for p in line.split(MIDDOT) if p.strip()]
        first = first[0] if first else ""
        a = first.rstrip(ELLIPSIS + " .").lower()
        b = company.rstrip(ELLIPSIS + " .").lower()
        if a and b and not (a.startswith(b) or b.startswith(a)):
            die("the top card for %r disagrees with itself about the current employer: the "
                "company pill reads %r and the position line reads %r. Refusing to pick one."
                % (name, company[:60], line[:60]))
    return {"company": company, "company_url": card["companies"][0]["href"] or None,
            "company_url_source": "the company pill is a button, not a link; the top card "
                                  "carries no company URL",
            "title": None, "title_source": TITLE_SOURCE, "line": line}


TITLE_SOURCE = ("not on the top card; it is in the Experience card, which this verb "
                "does not open")


def _primary(card, name):
    """The primary control and the row it sits on.

    Returns (primary_label, [row labels in left-to-right order]). The primary is
    the ONE control the page paints in its primary fill - not the leftmost, and
    not whichever word a hard-coded list happens to look for first. Zero filled
    controls, or more than one, is a FAIL naming the colour: it means LinkedIn
    has restyled the card and no answer here would be a reading.
    """
    filled = [c for c in card["controls"] if c["filled"]]
    if len(filled) != 1:
        die("expected exactly one control painted %s on %r's top card and found %d (%s). "
            "That colour is how the primary action is identified; LinkedIn has restyled the "
            "card, and guessing which control is primary is what this verb refuses to do."
            % (S.PROFILE_PRIMARY_FILL, name, len(filled),
               ", ".join(_label(c) for c in filled) or "none"))
    p = filled[0]
    row = sorted([c for c in card["controls"]
                  if abs(c["y"] - p["y"]) <= S.PROFILE_ROW_TOLERANCE],
                 key=lambda c: c["x"])
    return _label(p), [_label(c) for c in row]


def _label(c):
    return c["text"] or c["aria"]


def _invite(controls):
    """The invite control among these, or None. Matched on the custom-invite href
    and the "Invite <name> to connect" label - never on the bare word Connect,
    which is all over a profile page."""
    for c in controls:
        if S.INVITE_HREF in (c.get("href") or "") or S.INVITE_ARIA.match(c.get("aria") or ""):
            return c
    return None


def _pending(controls):
    """The control saying an invitation to this person is ALREADY OUTSTANDING, or
    None - F3, 2026-09-10.

    Matched on the accessible label measured on the live card, never on the bare
    word "Pending", which is the same rule `_invite` applies to the bare word
    "Connect" and it is chosen the same way: precision over recall. A false
    positive here tells Phase 3's `withdraw` there is an invitation to take back
    when there is not. A false negative gives back the answer this replaces -
    can_connect false with a true but uninformative reason - which is a worse
    report and not a wrong one.

    WHAT THAT COSTS, SAID OUT LOUD: this was measured on ONE profile. A Pending
    control rendered without that label - another locale, another layout - is
    not detected, and `invitation_pending` is then false on a profile where an
    invitation really is outstanding. The live row P2-11 is what makes that
    visible: it asserts true on a profile we know is pending, so the day
    LinkedIn changes the label the run goes red instead of the field going
    quiet.
    """
    for c in controls:
        if S.INVITE_PENDING_ARIA.match((c.get("aria") or "").strip()):
            return c
    return None


def _decide(item, where, via):
    """(can_connect, reason, via, url) from the invite control that was found.

    RULING R5, and both directions of it. "You can invite this person" must never
    come from a path that did not positively see an invite control - it is only
    ever returned here, with the control in hand. And a control that is DISABLED
    is not a yes and not a no: the page is saying the invitation cannot be sent
    right now and not why. That is a value this verb cannot decide, so it is null
    WITH a reason naming what it could not read, rather than a false that a
    caller would act on.

    The enabled state was never checked at all before. A busy or disabled Connect
    control that kept its href was reported as can_connect: true.
    """
    if item is None:
        return None
    if item.get("disabled"):
        return (None,
                "an invite control is %s but the page has it disabled, so whether this person "
                "can be invited right now cannot be read off it - and a disabled control is "
                "not the same answer as no invite control" % where,
                None, None)
    return True, "an invite control is %s" % where, via, _abs(item.get("href"))


def _connect(br, card, name, degree):
    """Can we send this person an invitation, where does the control live, and is
    one already outstanding?

    FIVE values: (can_connect, reason, via, url, invitation_pending). The first
    four because the caller's question ("can I connect with this person") is not
    the question the old `connection_state` answered ("what does a button here
    say"). Measured 2026-09-09: the invite control is on the top card on some
    profiles and behind the More menu on others, and the primary button is
    unrelated to which - one of the six profiles measured has Message filled,
    Follow beside it, and the invitation in the menu.

    The fifth is F3, 2026-09-10. `invitation_pending` is true only where a
    pending control was POSITIVELY SEEN; false means this run read the card (and
    the menu, where it got that far) and no pending control was on it. That is
    a reading of a card we did read, not an absence noticed by an instrument
    that never looked - but it is still narrower than "no invitation is
    outstanding", and no caller should read it as that. See `_pending` for the
    one profile it was measured on.

    The menu is opened ONLY when the top card has no invite control and no
    pending control, and its contents are believed only when the item every menu
    carries is in them. An empty menu read looks exactly like a menu with no
    invite in it, and that reading would report can_connect=false forever
    without ever being wrong out loud.
    """
    if degree == "self":
        return None, "this is the signed-in member's own profile", None, None, False

    # BEFORE the invite control and before the menu. The card cannot carry both
    # Connect and Pending - LinkedIn paints one or the other - but if one ever
    # does, the answer that acts on nobody is the one to keep. And answering
    # from the card here is what stops this path opening a menu to go looking
    # for something it has already found: until F3 a pending profile cost a
    # click, a settle loop and several seconds to arrive at a worse sentence.
    pending = _pending(card["controls"])
    if pending is not None:
        return (False,
                "an invitation to %s is already PENDING - the top card carries the control "
                "labelled %r, which is LinkedIn saying an invitation has been sent and not "
                "yet answered. Sending another is not possible until this one is withdrawn "
                "or expires." % (name, (pending.get("aria") or pending.get("text") or "")[:80]),
                None, None, True)

    top = _invite(card["controls"])
    decided = _decide(top, "on the top card", "topcard")
    if decided:
        # No pending control on the card this was read from, three lines above.
        return decided + (False,)

    more = br.page.locator(S.PROFILE_TOPCARD).first.get_by_role(
        "button", name=S.PROFILE_MORE_NAME)
    opened = False
    for i in range(more.count()):
        b = more.nth(i)
        if b.is_visible():
            b.click(timeout=6000)
            opened = True
            break
    if not opened:
        die("%r's top card offers no invite control and no More button to look behind. "
            "can_connect cannot be answered from this page, and answering it false would be "
            "a guess dressed as a reading." % name)
    # RULING R5. This used to be a flat 1.5-second sleep and one read. A menu
    # that renders "About this member" at 1.5 seconds and its Connect item at
    # 1.8 passed the proof, and the verb then believed an absence it had read
    # too early - reporting can_connect: false about somebody it could in fact
    # invite. So the menu is now read until it STOPS CHANGING: two consecutive
    # identical reads, and the proof item present, before anything is concluded
    # from what is or is not in it. A menu still changing at the deadline is a
    # page this cannot read, and it says so.
    menus, items, stable = _settled_menu(br)
    br.page.keyboard.press("Escape")
    time.sleep(0.8)
    if menus != 1:
        die("opening More on %r's profile left %d visible menus on the page, not one. "
            "Reading menu items across two menus is how an unrelated menu's contents come "
            "to answer a question about this one." % (name, menus))
    if not stable:
        die("the More menu on %r's profile was still changing after %.1f seconds (%d items at "
            "the last read). An absence read out of a menu that is still rendering is the "
            "reading that reports can_connect false forever without ever being wrong out loud."
            % (name, MENU_SETTLE_SECONDS, len(items)))
    proof = any(S.PROFILE_MENU_PROOF.lower() in (i["text"] or "").lower() for i in items)
    if not proof:
        die("the More menu on %r's profile did not come back with %r in it (%d items read). "
            "An empty or half-rendered menu is a broken instrument, not a menu with no invite "
            "in it." % (name, S.PROFILE_MENU_PROOF, len(items)))
    # The same label, in the menu. NOT MEASURED THERE - the pending control was
    # measured on the top card and nowhere else, and this is here because the
    # menu is the other place an invite control lives, so it is the other place
    # this one might. It fires only on the exact string that was measured, so it
    # cannot invent a pending state; if LinkedIn renders one here in some other
    # form, this reports what it does today and says so below.
    menu_pending = _pending(items)
    if menu_pending is not None:
        return (False,
                "an invitation to %s is already PENDING - the More menu carries the item "
                "labelled %r." % (name, (menu_pending.get("aria")
                                         or menu_pending.get("text") or "")[:80]),
                None, None, True)

    decided = _decide(_invite(items), "in the More menu", "more-menu")
    if decided:
        return decided + (False,)
    return (False,
            "no invite control on the top card and none in the More menu, which settled and "
            "read: %s"
            % ", ".join(sorted((i["text"] or i["aria"] or "?")[:40] for i in items)),
            None, None, False)


# How long the More menu is given to stop changing, and how often it is read.
# Two consecutive identical reads is the test; the deadline is when this gives up
# and fails rather than concluding anything from a moving target.
MENU_SETTLE_SECONDS = 8.0
MENU_READ_GAP = 0.4


def _settled_menu(br):
    """(visible menus, items, did it settle). Reads the open menu until two
    consecutive reads agree, or the deadline passes."""
    deadline = time.time() + MENU_SETTLE_SECONDS
    last = None
    menus, items = 0, []
    while time.time() < deadline:
        time.sleep(MENU_READ_GAP)
        got = br.page.evaluate(MENU_JS, S.PROFILE_MENU_ITEM)
        menus, items = got["menus"], got["items"]
        now = [(i["text"], i["href"], i["disabled"]) for i in items]
        if last is not None and now == last and items:
            return menus, items, True
        last = now
    return menus, items, False


def _abs(href):
    if not href:
        return None
    if href.startswith("http"):
        return href
    return "https://www.linkedin.com" + ("" if href.startswith("/") else "/") + href


def _connections(card):
    """The connections count, read from the whole card's text.

    It is rendered as one paragraph on some profiles and as two adjacent ones on
    others, and the two-paragraph shape is what left a bare "500+" loose in the
    paragraph run. Normalising the card's text puts the number back next to its
    word wherever it was split.
    """
    m = S.CONNECTIONS_IN_CARD.search(card["text"])
    if not m:
        return None, None, "the top card states no connections count"
    raw = m.group(0)
    return to_int(m.group(1), "the connections count"), raw, None


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
        return None, None, "this profile has no Activity card, which is where the follower " \
                           "count is read from"
    for line in card.inner_text().splitlines():
        m = S.COUNT_LINE.match(line.strip())
        if m and m.group(2).lower().startswith("follower"):
            return to_int(m.group(1), "the follower count"), line.strip(), None
    return None, None, "the Activity card states no follower count"


def read_profile(a):
    url = a.url if a.url.startswith("http") else "https://www.linkedin.com/in/%s/" % a.url.strip("/")
    m = SLUG.search(url)
    if not m:
        die("not a profile URL (no /in/ in it): %s" % a.url)
    want = m.group(1).lower()
    pace = Pace()
    with Browser(a.port) as br:
        # The view/view_self split, 2026-09-10. `want` is the slug this verb is
        # about to demand, and the assertion four lines down refuses to go on
        # unless the page it LANDED on carries that same slug - so the value the
        # counter was chosen from is the value the read is then held to. Asking
        # for our own profile and being sent to somebody else's is a hard
        # failure, not a mis-counted view.
        if is_own_profile(want):
            pace.before_self_view("profile %s (the owner's own)" % want)
        else:
            pace.before_view("profile %s" % want)
        final = br.read(url, "the profile %s" % want, settle=7)
        pace.after_view()

        got = SLUG.search(final)
        if not got or got.group(1).lower() != want:
            die("asked for the profile %r and landed on %r (%s)"
                % (want, got.group(1) if got else "(no /in/)", final))

        card = br.page.evaluate(TOPCARD_JS, [S.PROFILE_TOPCARD, {"fill": S.PROFILE_PRIMARY_FILL}])
        if card is None:
            die("no profile top card on %s (selector %s). LinkedIn has changed the profile "
                "layout, or this is not a profile page." % (final, S.PROFILE_TOPCARD))

        name = card["name"]
        if not name:
            die("the top card on %s has no name in it; that is not a read, it is a blank page" % final)

        if not card["blockPs"]:
            die("no identity block on the top card for %r: it has no 'Contact info' link, which "
                "is the anchor the headline and the location are found from. Refusing to fall "
                "back to counting paragraphs - that is the guess this verb was built to stop."
                % name)

        primary, actions = _primary(card, name)
        degree = _degree(card, name)
        reason = None
        if degree is None:
            # No degree badge AND nothing to connect to or message: our own card,
            # whose row reads Open to / Add section / Add custom button / Resources.
            if _invite(card["controls"]) is None and not any(
                    l == "Message" or l.startswith("Follow") for l in actions):
                degree = "self"
            else:
                reason = ("no visible degree badge on the top card; its actions read %s"
                          % ", ".join(actions))
                log(reason)

        headline = _headline(card, name)
        current = _current(card, name, headline)

        if a.expect:
            hay = " ".join([name, headline, card["location"] or "",
                            (current.get("company") or ""), (current.get("line") or "")]).lower()
            if a.expect.lower() not in hay:
                die("the profile does not mention %r; refusing to report it. It reads %r / %r"
                    % (a.expect, name, headline[:60]))
            log("profile verified: contains %r" % a.expect)

        (can_connect, connect_reason, connect_via, connect_url,
         invitation_pending) = _connect(br, card, name, degree)
        connections, connections_raw, connections_reason = _connections(card)
        followers, followers_raw, followers_reason = _followers(br)

        rec = {
            "kind": "profile", "url": final.split("?")[0], "slug": want, "name": name,
            "headline": headline,
            "location": card["location"] or None,
            "about": _about(br),
            "current": current,
            "degree": degree,
            "degree_reason": reason,
            "primary_button": primary,
            "actions": actions,
            "can_connect": can_connect,
            "can_connect_reason": connect_reason,
            "connect_via": connect_via,
            "connect_url": connect_url,
            # F3. True only where a pending-invitation control was positively
            # seen; false means this run read the card and no such control was
            # on it, which is narrower than "no invitation is outstanding". The
            # reason field says which of the two it is, in words.
            "invitation_pending": invitation_pending,
            "connections": connections,
            "connections_raw": connections_raw,
            "connections_reason": connections_reason,
            "followers": followers,
            "followers_raw": followers_raw,
            "followers_reason": followers_reason,
            "rendering": "react",
        }
        print(json.dumps(rec, ensure_ascii=True))
        print("RESULT read-profile slug=%s name=%r degree=%s primary=%r can_connect=%s "
              "via=%s pending=%s about=%d chars"
              % (want, name, degree, primary, can_connect, connect_via,
                 invitation_pending, len(rec["about"] or "")))


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
        # The view/view_self split, 2026-09-10 - and see read_profile for why
        # counting on the REQUESTED key is safe: the two assertions below refuse
        # any landing that is not the member view of that same key.
        if is_own_page(key):
            pace.before_self_view("company %s (a Page the owner administers)" % key)
        else:
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
