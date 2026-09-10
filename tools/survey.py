# -*- coding: utf-8 -*-
"""Read-only DOM survey. Run this BEFORE writing a selector, never after.

    py -3.11 tools/survey.py <label> <url> [--out FILE] [--full-out FILE]
                             [--probe SELECTOR ...] [--depth N] [--settle N]

It opens the URL through kit.browser.Browser - so it takes the same lock and the
same background tab every verb takes - and dumps what is actually there:

  * the final URL after any redirect (an authwall shows up here first);
  * which rendering was served, by the same test Phase 1 uses ([data-urn]);
  * whether the global navigation's own identity control is present, which is
    the PRESENCE test the read verbs assert on;
  * every actionable role and accessible name from the accessibility tree;
  * the count for each --probe selector, so a candidate can be tested before it
    is trusted;
  * an outline of `main`: tag, id, classes, data-* attributes, role, aria-label
    and the first 120 characters of each node's own text.

TWO DUMPS, ON PURPOSE. This repository is PUBLIC.
  * --out writes the REDACTED dump, and it is the one that is committed. Every
    piece of page text and every accessible name is emitted only if it matches
    the generic user-interface vocabulary below; anything else becomes
    "<redacted len=N>". The length is what a selector needs; the words are
    somebody's name. Identifiers inside hrefs and labels are replaced by their
    shape - see IDENTIFIERS below for exactly which forms.
  * --full-out writes everything, unredacted, for the person writing the
    selectors to read. It goes to a scratch directory and is NEVER committed.

  IT IS NOT CALLED THE SAFE DUMP, AND THAT IS DELIBERATE (ruling R13.4,
  2026-09-09). It used to be. The fourth inspection pass then found that the
  redactor knew three forms - /in/ slugs, ACoA member ids, and a fixed list of
  query parameters - and nothing else, so organisation slugs and numeric ids,
  post and event urns, a job id, article paths, three shortened post links and a
  precise postal-code map URL were all sitting in the committed dumps. The word
  "safe" was true of the three forms it knew and false of the artefact, and a
  name that overstates what a thing does is how the next person stops checking.
  What it does now is REDACT THE FORMS LISTED BELOW. Anything not on that list
  is not covered, and a new surface deserves a fresh look before its dump is
  committed.

NOTHING HERE TYPES OR SUBMITS. It clicks in exactly two bounded ways, and both
are about REVEALING something that no URL reaches:

  * --expand clicks one "see more", because a collapsed About section cannot be
    measured;
  * --click NAME opens a menu, a composer or a dialog, and ONLY for a name on the
    REVEAL_ONLY allowlist below. Any other name is refused before the browser is
    touched. See that list for why an allowlist rather than a denylist, and for
    the rule that keeps a submitting control off it forever.

After a --click the survey presses Escape, so the page is left as it was found.

A SURVEY IS STILL A VIEW - F1, 2026-09-10. It opens a real page in the real
signed-in browser, and from LinkedIn's side it is indistinguishable from
`read-profile`. So it registers on the same counters and obeys the same daily
cap: somebody else's surface on `view` (cap 80), one of the owner's own on
`view_self` (counted, uncapped). Over the cap it refuses before opening
anything. It did none of this until F1, and two profile views went unrecorded
through here on 2026-09-09 while the counter sat at eighty.
"""
import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kit.browser import Browser, Pace, log, surface_kind, _URL_PROFILE

# Words that are LinkedIn's own furniture rather than anybody's data. A name or
# a run of text is printed as-is only when EVERY word in it is one of these.
GENERIC = re.compile(
    r"^(?:[\s\-,.:;()\[\]/|+&'\"!?%#*]+|\d[\d,.]*|"
    r"1st|2nd|3rd|3rd\+|degree|connection|connections?|follower|followers?|following|follow|"
    r"connect|pending|message|more|less|see|show|all|view|open|close|edit|save|cancel|delete|"
    r"about|experience|education|skills|interests|activity|posts?|comments?|reactions?|"
    r"featured|recommendations?|licenses|certifications|volunteering|courses|projects|"
    r"honors|awards|languages|publications|patents|organizations|causes|"
    r"home|network|jobs|messaging|notifications|me|premium|free|try|"
    r"search|results|people|companies|content|groups|events|schools|filters?|"
    r"reset|apply|current|past|talks|title|location|industry|company|school|keywords?|"
    r"sort|by|relevance|date|posted|top|latest|new|newest|oldest|page|next|previous|"
    r"overview|analytics|updates|visitors|competitors|leads|admin|dashboard|"
    r"impressions|engagements?|engagement|rate|clicks?|likes?|shares?|reposts?|"
    r"days?|day|week|weeks?|month|months?|year|years?|hour|hours?|minute|minutes?|"
    r"ago|now|today|yesterday|tomorrow|and|or|the|a|an|of|to|in|at|on|for|with|from|"
    r"button|link|image|photo|logo|banner|icon|menu|list|dialog|tab|graph|chart|"
    r"employees?|size|website|tagline|headquarters|founded|specialties|type|"
    r"unread|read|mark|dismiss|settings?|help|report|copy|share|send|invite|withdraw|"
    r"react|like|celebrate|support|love|insightful|funny|unreact|reply|"
    r"k|m|b|no|yes|ok|done|loading|skip|main|navigation|footer|header|"
    r"linkedin|corporation|inc|llc|ltd|status|is|was|are|were|has|have|your|you|"
    r"profile|pages?|feed|grow|start|end|total|last|first|"
    r"sign|log|out|verified|verify|hiring|providing|services|"
    # ARIA roles and HTML tag names. A probe that reports role and tag is
    # reporting STRUCTURE, and structure is not anybody's data - without these
    # a probe result reads as a column of "<redacted len=8>". Added 2026-09-10.
    r"menuitem|menuitemcheckbox|menuitemradio|textbox|combobox|listitem|presentation|"
    r"generic|listbox|option|slider|toolbar|tooltip|separator|banner|contentinfo|"
    r"complementary|figure|div|span|ul|ol|li|input|p|h1|h2|h3|h4|section|nav|"
    r"aside|label|select|textarea|svg|use|path|body|html|iframe|true|false|null)$",
    re.I)

ACTIONABLE = set("""
button link textbox combobox checkbox radio tab menuitem menuitemcheckbox
menuitemradio switch searchbox option listbox heading article listitem img list
region navigation main table row cell columnheader form dialog alert status
paragraph StaticText time definition term group
""".split())


# ---------------------------------------------------------------- IDENTIFIERS
#
# THE FORMS THIS REDACTOR KNOWS. Ruling R13.2, 2026-09-09: it used to know three
# and the committed dumps leaked the rest. Each rule keeps the SHAPE - the path,
# the urn kind, the parameter name - because that is what a selector is written
# against, and drops the value, because that is what identifies somebody. A
# stable lookup key to hidden content is not anonymous just because the name
# beside it was redacted.
#
# The owner's OWN Page is kept on purpose: it is public, it is in these documents
# by intent, and a dump of his own Page's analytics that cannot say which Page it
# is has lost the thing it was taken for.
OWN = ("107519091", "centerconsulting-inc")

# A profile slug. TWO THINGS THIS HAS TO SURVIVE, both measured 2026-09-10 in a
# dump that had already been through every other rule here:
#   * PERCENT-ENCODING. The More menu's "send profile in a message" href carries
#     the profile as `...%2Fin%2F<slug>` inside a query value, so a rule that
#     only knows the literal "/in/" walks straight past it.
#   * TRUNCATION. A probe that slices an href to 110 characters can cut a slug in
#     half, and half a slug is still a searchable prefix of a real person - but it
#     is no longer the literal string the subject-token pass is looking for. A
#     literal-match rule cannot see a truncated identifier; only a shape can. So
#     the tail is `*` and not `+`: this matches `/in/` with nothing after it too.
#     The (?!<) is not decoration: with a `*` tail this rule happily matches the
#     `<slug>` it wrote last time and produces `/in/<slug><slug>`, growing by one
#     placeholder per run. tools/redact_surveys.py is idempotent BY CONTRACT -
#     that is how its --check proves a dump is clean - so a rule that is not
#     idempotent silently turns that check into a permanent failure. Measured the
#     first time this rule was written, 2026-09-10.
#
# PATH_FORMS is the second shared list, for the same reason SENSITIVE_QUERY_PARAMS
# is the first: the redactor builds its rules from it and tests/test_no_leak.py
# builds ONE artefact check from it. Each entry is (the path prefix, the tail the
# identifier is made of, the placeholder that must be there instead). Adding a
# path here teaches the redactor and arms the check in one edit.
#
# The tails are `+` and not `*`, and that distinction was measured too. `*` also
# matches a bare path prefix with NOTHING after it - and a bare `/messaging/thread/`
# is not an identifier, it is what a CSS selector in a probe expression looks
# like. The first `*` version rewrote a probe's own recorded source. A TRUNCATED
# identifier still has a non-empty tail, so `+` catches the case that mattered
# and leaves the case that never carried anybody's data alone.
PATH_FORMS = {
    # Both spellings of the profile path. `%2Fin%2F` is how it arrives inside a
    # query value, and the literal-only rule walked straight past it.
    "profile": (r"(?:/|%2F)in(?:/|%2F)", r"[A-Za-z0-9._~%-]+", "<slug>"),
    # A conversation. The messaging list gives its rows no href at all, so a
    # thread id only ever appears once a thread is open - in the URL, and in
    # whatever the page writes it into. It is a stable key to a private
    # conversation between named people, which makes it the most sensitive
    # identifier this toolkit has met.
    "thread": (r"/messaging/thread/", r"[A-Za-z0-9%_=.:,-]+", "<threadid>"),
    "job": (r"/jobs/view/", r"[A-Za-z0-9._%-]+", "<jobid>"),
}


def _path_rule(name):
    prefix, tail, _ = PATH_FORMS[name]
    return re.compile("(%s)(?!<)%s" % (prefix, tail), re.I)


SLUG = _path_rule("profile")
THREAD = _path_rule("thread")
JOB = _path_rule("job")
MEMBER_ID = re.compile(r"ACoA[A-Za-z0-9_-]{8,}")
# THE SHARED LISTS - RULING: the redactor and the artefact check read the SAME
# ones. 2026-09-10.
#
# When `vanityName` was added here, tests/test_no_leak.py did not learn it, and
# that is R18's gap reopening exactly: the redactor knows a form and the check
# that inspects the committed files cannot see it, so the next dump leaks and the
# suite stays green. Six assertions in the test file, one per parameter, would
# have the same defect one layer up - the seventh parameter gets taught to the
# redactor and the test keeps passing without it.
#
# So the names live HERE, once, and tests/test_no_leak.py imports them. Adding a
# parameter to this tuple teaches the redactor AND arms the check in the same
# edit, and there is no second list to forget. This is the fifth time this shape
# has appeared in this repository; the coupling is the fix, not the list.
SENSITIVE_QUERY_PARAMS = (
    "profileUrn", "recipient", "keywords", "fsd_profile", "trackingId", "urlhash",
    "mt", "url", "vanityName", "connectionOf", "facetConnectionOf", "threadId",
    "conversationId", "miniProfileUrn",
)
QUERY_PLACEHOLDER = "<value>"
QUERY_VALUE = re.compile(
    r"([?&](?:%s)=)[^&\"\s]+" % "|".join(SENSITIVE_QUERY_PARAMS), re.I)
# An organisation, by slug or by numeric id, on any of the paths that carry one.
ORG_PATH_NAMES = ("company", "school", "showcase", "organization")
ORG_PATH = re.compile(
    r"((?:/|%%2F)(?:%s)(?:/|%%2F))(?!<)([A-Za-z0-9._%%-]+)" % "|".join(ORG_PATH_NAMES), re.I)
# Any urn that names a thing: a post, a share, an event, a comment, an org, a
# profile. The KIND stays - a selector is written against urn:li:activity - and
# the id goes.
# Both spellings. A urn inside a query value arrives percent-encoded -
# `urn%3Ali%3Afsd_profile%3A<id>` - and the literal form walks past it. The id
# itself is usually also caught by MEMBER_ID or by the fifteen-digit shape rule,
# so this is the belt to those braces rather than the only guard; measured
# 2026-09-10 on a profile href that a probe had truncated before the id.
# The third shared list. Both spellings: a urn inside a query value arrives
# percent-encoded, `urn%3Ali%3Afsd_profile%3A<id>`, and the literal form walks
# past it. tests/test_no_leak.py loops over this.
URN_FORMS = (
    (r"urn:li:[A-Za-z_]+:", r"\(?[A-Za-z0-9%_,:.()-]+\)?", "<id>"),
    (r"urn%3Ali%3A[A-Za-z_]+%3A", r"[A-Za-z0-9%_,.()-]+", "<id>"),
)
URN = re.compile("(%s)(?!<)%s" % (URN_FORMS[0][0], URN_FORMS[0][1]))
URN_ENC = re.compile("(%s)(?!<)%s" % (URN_FORMS[1][0], URN_FORMS[1][1]), re.I)
ARTICLE = re.compile(r"(/pulse/|/newsletters/|/events/|/groups/|/posts/)[^\"\s?&]+", re.I)
# A shortened post link, plain or percent-encoded inside another URL. Following
# one recovers the post and its author, which is exactly what a short link is
# for and exactly why three of them had no business in a public docstring.
SHORT_LINK = re.compile(r"lnkd(?:\.|%2E)in(?:/|%2F)[A-Za-z0-9_/%-]+", re.I)
# A map or address URL. The one that was committed carried a postal code.
MAP_URL = re.compile(r"https?://[^\"\s]*(?:maps|/maps/|geo/)[^\"\s]*", re.I)

# RULING R17, 2026-09-09, and it is the rule that matters most here.
#
# Everything above is an ENUMERATION OF FORMS, and an enumeration always loses to
# the next form. The rules above were written to take out `urn:li:share:<id>`, and
# the Architect then found the same id still in a committed dump as
# `shareId=<id>` inside a DOM element id - the identical defect, one level down.
# Running the check that R18 asked for found seven more of the same shape that
# nobody had looked for: the whole urn percent-encoded inside a notification
# href, `li%3Aactivity%3A<id>`.
#
# So for identifiers of this class the rule is not a syntax, it is a SHAPE: every
# run of fifteen or more consecutive digits, wherever it appears and whatever
# surrounds it. A LinkedIn content id is nineteen digits, so this catches every
# one of them in every wrapper there will ever be. The owner's Page id is nine
# digits and his organisation ids are shorter, so they pass through - which is
# exactly what ruling R13.3 asks for, and it is why the threshold is fifteen and
# not ten.
#
# This runs LAST, deliberately. The named rules above carry meaning a selector
# needs - which path, which urn kind, which parameter - and doing them first
# keeps that shape in the dump. This one is the net underneath them.
LONG_NUMBER = re.compile(r"\d{15,}")


# ---------------------------------------------------- THE SUBJECT'S OWN TOKENS
#
# 2026-09-10, Phase 3 survey. The R17 defect again, one level down and in a place
# nobody had outlined before. Every rule above is written against a URL SHAPE -
# `/in/<slug>`, `urn:li:...`, `/company/<key>` - and the profile rendering also
# writes the slug into DOM ELEMENT IDS, with no path and no urn around it:
#
#     div#ProfilePostConnectDrawer_<slug>
#     div#profileCardsAboveActivityTopcardOnly<slug>
#     div#com.linkedin.sdui.profile.card.ref<slug>Activity
#
# The first committed Phase 3 dump carried four of those. No shape separates a
# slug in an element id from an ordinary identifier - it is arbitrary text - so
# a syntax rule cannot ever catch this class, and enumerating the SDUI prefixes
# is the same losing game R17 is about.
#
# So this is not a shape rule. It is a rule about the SUBJECT: whatever slugs and
# organisation keys this page actually names, redact those literal strings
# WHEREVER they appear in the dump. They are collected from two places - the URL
# the survey was pointed at, and every /in/ and /company/ href in the live DOM,
# which is how a "people also viewed" card's slug gets covered as well as the
# subject's own. The owner's own slug and Page keys are deliberately left alone,
# for the reason ruling R13.3 gives.
#
# WHAT THIS DOES NOT COVER, said plainly: a third party whose slug is in an
# element id but who is named by NO link anywhere on the page. Nothing here would
# see that, tests/test_no_leak.py has no shape to test it by, and the only
# remaining guard is a person reading the dump before committing it.
SUBJECT_TOKENS = {}


def note_subject_tokens(pairs):
    """Record (token, replacement) for literal redaction. Call before dumping."""
    for token, repl in pairs:
        t = (token or "").strip()
        if len(t) >= 4 and t.lower() not in OWN and t.lower() not in OWN_SLUGS:
            SUBJECT_TOKENS[t] = repl


def _subject(value):
    for token in sorted(SUBJECT_TOKENS, key=len, reverse=True):
        if token in value:
            value = value.replace(token, SUBJECT_TOKENS[token])
    return value


# The owner's own profile slug, kept for the same reason his Page id is kept.
OWN_SLUGS = ("sorenfrederiksen",)

COLLECT_TOKENS_JS = r"""
() => {
  const out = {slugs: [], orgs: []};
  for (const a of document.querySelectorAll('a[href]')) {
    const h = a.getAttribute('href') || '';
    let m = h.match(/\/in\/([^\/?#"]+)/);
    if (m) out.slugs.push(decodeURIComponent(m[1]));
    m = h.match(/\/(?:company|school|showcase|organization)\/([^\/?#"]+)/);
    if (m) out.orgs.push(decodeURIComponent(m[1]));
  }
  out.slugs = [...new Set(out.slugs)];
  out.orgs = [...new Set(out.orgs)];
  return out;
}
"""


def _org(m):
    return m.group(1) + (m.group(2) if m.group(2).lower() in OWN else "<company>")


def redact_identifiers(value):
    """Keep the SHAPE of every identifier in this string, drop the value.

    Applied to hrefs and accessible names as a survey is written, and applied to
    the already-committed dumps in place by tools/redact_surveys.py - one
    definition, so the dumps and any future survey are redacted by the same
    rules rather than by two lists that drift apart.
    """
    if not value:
        return value
    v = _subject(value)
    v = MAP_URL.sub("<map url>", v)
    # BEFORE the short-link rule, so a short link nested inside a url= parameter
    # is taken out with the parameter rather than half-redacted inside it.
    v = QUERY_VALUE.sub(lambda m: m.group(1) + QUERY_PLACEHOLDER, v)
    v = SHORT_LINK.sub("lnkd.in/<shortlink>", v)
    v = SLUG.sub(lambda m: m.group(1) + PATH_FORMS["profile"][2], v)
    v = MEMBER_ID.sub("<memberid>", v)
    v = ORG_PATH.sub(_org, v)
    v = URN.sub(lambda m: m.group(1) + URN_FORMS[0][2], v)
    v = URN_ENC.sub(lambda m: m.group(1) + URN_FORMS[1][2], v)
    v = JOB.sub(lambda m: m.group(1) + PATH_FORMS["job"][2], v)
    v = THREAD.sub(lambda m: m.group(1) + PATH_FORMS["thread"][2], v)
    v = ARTICLE.sub(lambda m: m.group(1) + "<article>", v)
    v = QUERY_VALUE.sub(lambda m: m.group(1) + QUERY_PLACEHOLDER, v)
    v = LONG_NUMBER.sub("<id>", v)          # R17: the shape rule, under all of them
    return v


def redact_attr(value):
    """An href or an aria-label from the redacted dump: keep the SHAPE, drop the
    person. See redact_identifiers for the forms this covers - and for the ones
    it does not, which is the part worth reading."""
    return redact_identifiers(value)


def redact(text):
    """Keep LinkedIn's own words; replace anybody's data with its length."""
    if text is None:
        return None
    t = " ".join(text.split())
    if not t:
        return ""
    words = [w for w in re.split(r"\s+", t) if w]
    if words and all(GENERIC.match(w) for w in words):
        return t
    return "<redacted len=%d>" % len(t)


# ------------------------------------------------------------- REVEAL-ONLY
#
# 2026-09-10, Phase 3 survey. Three of the surfaces Phase 3 must measure are not
# reachable by a URL: the invitation behind the More menu, the message composer,
# and the Page's Invite-connections dialog. They have to be OPENED to be seen.
#
# This is an ALLOWLIST and not a denylist, deliberately, and it is the same
# reasoning as everywhere else in this repository: a denylist of dangerous names
# certifies every name it has not met, and the one it has not met is the one that
# sends something to a real person. So a survey may click ONLY a name written
# here, each with the reason it commits nothing, and every other name is refused
# before the browser is touched.
#
# NONE of these submits, spends, or notifies. Opening a composer does not send;
# opening the invite dialog does not spend a credit; opening a menu does not
# accept an invitation. Anything that DOES is not eligible for this list at any
# point in the future - if a verb needs to press it, that is the verb's job and
# the verb carries the --submit gate for it.
REVEAL_ONLY = {
    "more": "opens the profile's overflow menu so its items can be read",
    "message": "opens the message composer. Typing and sending are separate acts "
               "and this survey does neither",
    "invite connections": "opens the Page's invite dialog so the credit count can "
                          "be read. A credit is spent by Invite, not by opening",
    "sent": "the invitation manager's Sent tab - a tab, not an action",
    "received": "the invitation manager's Received tab - a tab, not an action",
    "write a message": "the messaging list's compose control; opens an empty draft",
    "compose": "as above, the other name the same control has worn",
}


# ------------------------------------------------- OPENING AN ALREADY-READ THREAD
#
# 2026-09-10, Phase 3 survey. OPENING A THREAD MARKS IT READ, and that cannot be
# undone invisibly - it is a write wearing a read's clothes. The messaging list
# does not give its rows hrefs, so a thread cannot be reached by URL and cannot be
# surveyed without clicking a row.
#
# So this step does not take a row number, a name, or a selector: a caller cannot
# aim it. It finds the conversation cards, keeps only the ones it can POSITIVELY
# PROVE are already read, and clicks the first of those. The proof is the row's
# own unread marker being absent AND the list containing at least one row that
# HAS that marker - because a marker that is absent from every row is a marker
# that has been renamed, and "no row looks unread" would then be a broken
# instrument reading as a clean result. With no positive control it refuses.
UNREAD_MARK = "msg-conversation-card__convo-item-container--unread"

OPEN_READ_THREAD_JS = """
(mark) => {
  const cards = [...document.querySelectorAll('.msg-conversation-card')];
  const unread = cards.filter(c => c.className.includes(mark));
  const read = cards.filter(c => !c.className.includes(mark));
  return {cards: cards.length, unread: unread.length, read: read.length};
}
"""


HREF_KEYS = ("href", "url", "link", "action", "src")
# Keys whose value is STRUCTURE, not content: a role, a tag, a hashed class, a
# data-view-name. These carry the whole engineering value of a probe and none of
# anybody's data, so they get the identifier rules and not the vocabulary rule -
# which would otherwise print "profile_topcard_connect" as "<redacted len=23>".
# `name` is deliberately NOT here: an accessible name is usually a person's.
STRUCT_KEYS = ("role", "tag", "dv", "data-view-name", "testid", "data-testid",
               "cls", "class", "id", "type", "component", "kind", "state")


def redact_json(value, key=""):
    """Redact a JS-probe RESULT structurally, not line by line.

    2026-09-10. `dump.text` redacts a whole line unless every word in it is
    LinkedIn's own vocabulary, and a line of JSON never is - so the first Phase 3
    dump recorded a menu of seven items as seven runs of "<redacted len=N>" and
    the committed artefact said nothing at all. The engineering content of a probe
    is the KEYS and the SHAPE; only the values are anybody's data. So each string
    is redacted on its own, hrefs by the identifier rules and everything else by
    the generic-vocabulary rule, and the structure around them survives.
    """
    if isinstance(value, dict):
        return {k: redact_json(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_json(v, key) for v in value]
    if isinstance(value, str):
        if key.lower() in HREF_KEYS or key.lower() in STRUCT_KEYS                 or "/" in value or value.startswith("urn:"):
            return redact_attr(value)
        return redact(value)
    return value


class Dump(object):
    """Two files written in step: one redacted, one whole."""

    def __init__(self, safe_path, full_path):
        self.safe = open(safe_path, "w", encoding="ascii", errors="backslashreplace") if safe_path else None
        self.full = open(full_path, "w", encoding="ascii", errors="backslashreplace") if full_path else None

    def both(self, line):
        for f in (self.safe, self.full):
            if f:
                f.write(line + "\n")

    def text(self, prefix, text, suffix=""):
        if self.safe:
            self.safe.write("%s%s%s\n" % (prefix, json.dumps(redact(text))[:220], suffix))
        if self.full:
            self.full.write("%s%s%s\n" % (prefix, json.dumps(" ".join((text or "").split()))[:400], suffix))

    def close(self):
        for f in (self.safe, self.full):
            if f:
                f.close()


OUTLINE_JS = r"""
([maxDepth, scope]) => {
  const out = [];
  const root = (scope ? document.querySelector(scope) : null)
               || document.querySelector('main') || document.body;
  const walk = (el, depth) => {
    if (depth > maxDepth || out.length > 2500) return;
    const cls = (el.getAttribute('class') || '').trim();
    const data = [...el.attributes].filter(a => a.name.startsWith('data-'))
                  .map(a => a.name + '=' + (a.value || '').slice(0, 60));
    const role = el.getAttribute('role') || '';
    const label = el.getAttribute('aria-label') || '';
    let own = '';
    for (const n of el.childNodes) if (n.nodeType === 3) own += n.nodeValue;
    own = own.replace(/\s+/g, ' ').trim();
    if (!own && el.children.length === 0) own = (el.innerText || '').replace(/\s+/g, ' ').trim();
    const interesting = cls || data.length || role || label || own;
    if (interesting) {
      out.push({depth: depth, tag: el.tagName.toLowerCase(),
                id: el.id || '', cls: cls.slice(0, 200), data: data, role: role,
                label: label, href: el.getAttribute('href') || '', text: own.slice(0, 120)});
    }
    for (const c of el.children) walk(c, depth + 1);
  };
  walk(root, 0);
  return out;
}
"""

IDENTITY_JS = r"""
() => {
  const probes = ['.global-nav__me', 'button.global-nav__primary-link-me-menu-trigger',
                  'img.global-nav__me-photo', '[data-test-global-nav-me]',
                  'nav.global-nav', '.global-nav__nav', '#global-nav',
                  'header.global-nav', '[data-view-name="navigation-me"]'];
  const found = {};
  for (const p of probes) found[p] = document.querySelectorAll(p).length;
  const me = [...document.querySelectorAll('button, a, img')]
    .map(e => (e.getAttribute('aria-label') || e.getAttribute('alt') || '').trim())
    .filter(s => /^Me\b|^Me$/.test(s));
  return {probes: found, me: me.slice(0, 6), title: document.title.slice(0, 140),
          bodyStart: (document.body.innerText || '').replace(/\s+/g, ' ').slice(0, 300)};
}
"""


def both_redacted(dump, line):
    """A header line: whole in the full dump, slug-free in the safe one."""
    if dump.safe:
        dump.safe.write(redact_attr(line) + chr(10))
    if dump.full:
        dump.full.write(line + chr(10))


def survey(br, label, url, dump, probes, depth, settle, expand, scope=None, js_exprs=(),
           clicks=(), open_read_thread=False):
    dump.both("# survey %s" % label)
    dump.both("# taken   %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    both_redacted(dump, "# request %s" % url)

    # F1, 2026-09-10. A SURVEY IS A VIEW. This tool opens a real profile in the
    # signed-in browser, against the owner's account, and LinkedIn cannot tell it
    # from a read verb - so neither may the counter. It registered nothing until
    # today, and two profile views were taken through it on 2026-09-09 while
    # pace.json sat at the cap. There is no exemption for "just looking".
    #
    # The branch is written out here rather than hidden in a helper, and it is the
    # third copy of the same four lines (read_profile, read_company, this). That
    # is deliberate: `before_self_view` is the uncapped path, so reaching it is a
    # positive act by name at a call site somebody can read, never something a
    # wrapper does on a caller's behalf.
    pace = Pace()
    kind = surface_kind(url)
    what = "survey %s of %s" % (label, url)
    if kind == "view_self":
        pace.before_self_view(what + " (a surface the owner owns)")
    else:
        pace.before_view(what)

    br.goto(url, settle=settle)
    pace.after_view()

    # Collect the identifiers this page actually names, BEFORE anything is
    # written, so the literal-token pass above can take them out of element ids
    # as well as out of hrefs. See SUBJECT_TOKENS for why a shape rule cannot.
    try:
        found = br.page.evaluate(COLLECT_TOKENS_JS)
    except Exception as exc:
        found = {"slugs": [], "orgs": []}
        dump.both("# NOTE could not collect subject tokens: %s" % str(exc).splitlines()[0][:80])
    m = _URL_PROFILE.search(url)
    if m:
        found["slugs"].append(m.group(1))
    note_subject_tokens([(t, "<slug>") for t in found["slugs"]]
                        + [(t, "<company>") for t in found["orgs"]])
    dump.both("# subject tokens redacted literally: %d" % len(SUBJECT_TOKENS))
    for name in clicks:
        allowed = REVEAL_ONLY.get(name.lower())
        if not allowed:
            raise SystemExit("FAIL --click %r is not on the reveal-only list in tools/survey.py. "
                             "A survey opens things to LOOK at them; it never presses a control "
                             "that could commit an action." % name)
        b = br.page.get_by_role("button", name=re.compile(r"^%s$" % re.escape(name), re.I)).first
        if not b.count():
            b = br.page.get_by_role("link", name=re.compile(r"^%s$" % re.escape(name), re.I)).first
        if not b.count():
            dump.both("# CLICK %r NOT FOUND - nothing was revealed and the dump below is the "
                      "page without it" % name)
            continue
        b.click(timeout=8000)
        time.sleep(3)
        dump.both("# clicked %r (reveal-only: %s)" % (name, allowed))
    if open_read_thread:
        counts = br.page.evaluate(OPEN_READ_THREAD_JS, UNREAD_MARK)
        dump.both("# conversation cards: %d, of which unread %d, read %d"
                  % (counts["cards"], counts["unread"], counts["read"]))
        if not counts["cards"]:
            raise SystemExit("FAIL --open-read-thread found no .msg-conversation-card. The class "
                             "has moved and nothing here can tell a read row from an unread one.")
        if not counts["unread"]:
            raise SystemExit("FAIL --open-read-thread found %d cards and NOT ONE carrying %r. "
                             "That is the positive control missing: either every conversation is "
                             "read, or the marker has been renamed and 'this row is read' is "
                             "being read off an instrument that can no longer say otherwise. It "
                             "refuses rather than guess." % (counts["cards"], UNREAD_MARK))
        if not counts["read"]:
            raise SystemExit("FAIL --open-read-thread found no already-read conversation to open. "
                             "Opening an unread one marks it read and cannot be undone.")
        card = br.page.locator(".msg-conversation-card:not(.%s)" % UNREAD_MARK).first
        card.click(timeout=8000)
        time.sleep(4)
        dump.both("# opened an already-read conversation (proved read: it lacks %r, and %d row(s) "
                  "on the same list carry it)" % (UNREAD_MARK, counts["unread"]))
    if expand:
        for name in (r"^see more$", r"^…see more$", r"^Show all", r"^more$"):
            try:
                b = br.page.get_by_role("button", name=re.compile(name, re.I)).first
                if b.count() and b.is_visible():
                    b.click(timeout=3000)
                    time.sleep(1.5)
                    dump.both("# expanded via a button matching %r" % name)
                    break
            except Exception:
                pass
    final = br.page.url
    both_redacted(dump, "# final   %s" % final)
    if final.rstrip("/") != url.rstrip("/"):
        dump.both("# NOTE the URL changed - a redirect, or an authwall")

    urns = br.page.locator("[data-urn]").count()
    dump.both("# rendering %s ([data-urn] count=%d)" % ("ember" if urns else "react", urns))

    ident = br.page.evaluate(IDENTITY_JS)
    dump.both("# signed-in probes %s" % json.dumps(ident["probes"]))
    dump.both("# 'Me' controls    %s" % json.dumps(ident["me"]))
    dump.text("# title   ", ident["title"])
    dump.text("# body    ", ident["bodyStart"])
    dump.both("")

    cdp = br.page.context.new_cdp_session(br.page)
    cdp.send("Accessibility.enable")
    nodes = cdp.send("Accessibility.getFullAXTree").get("nodes", [])
    dump.both("== ACCESSIBILITY (%d nodes in the tree) ==" % len(nodes))
    seen = 0
    for n in nodes:
        role = (n.get("role") or {}).get("value") or ""
        if role not in ACTIONABLE:
            continue
        name = (n.get("name") or {}).get("value") or ""
        if not name.strip():
            continue
        seen += 1
        if seen > 1200:
            dump.both("  ... truncated at 1200 named nodes")
            break
        dump.text("  %-14s " % role, name)
    dump.both("")

    if probes:
        dump.both("== PROBES ==")
        for sel in probes:
            try:
                n = br.page.evaluate("s => document.querySelectorAll(s).length", sel)
            except Exception as exc:
                n = "ERR %s" % str(exc).splitlines()[0][:60]
            dump.both("  [%s] %s" % (n, sel))
        dump.both("")

    if js_exprs:
        dump.both("== JS PROBES ==")
        for expr in js_exprs:
            try:
                val = br.page.evaluate(expr)
            except Exception as exc:
                val = "ERR " + str(exc).splitlines()[0][:120]
            dump.both("  " + redact_attr(expr))
            if dump.safe:
                for line in json.dumps(redact_json(val), indent=1, ensure_ascii=True).splitlines():
                    dump.safe.write("    " + line + chr(10))
            if dump.full:
                for line in json.dumps(val, indent=1, ensure_ascii=True).splitlines():
                    dump.full.write("    " + line + chr(10))
        dump.both("")

    outline = br.page.evaluate(OUTLINE_JS, [depth, scope])
    dump.both("== DOM OUTLINE of %s (%d nodes, depth<=%d) ==" % (scope or "main", len(outline), depth))
    for o in outline:
        head = "  %s%s%s%s" % ("  " * o["depth"], o["tag"],
                               "#" + o["id"] if o["id"] else "",
                               "." + ".".join(o["cls"].split()[:6]) if o["cls"] else "")
        def bits_for(safe):
            bits = []
            if o["role"]:
                bits.append("role=%s" % o["role"])
            if o["label"]:
                lab = redact(o["label"]) if safe else o["label"]
                bits.append("aria-label=" + json.dumps(lab)[:90])
            if o["href"]:
                href = redact_attr(o["href"]) if safe else o["href"]
                bits.append("href=" + href[:110])
            for d in o["data"]:
                bits.append(redact_attr(d) if safe else d)
            return bits

        head_safe = redact_attr(head) if dump.safe else head
        line_safe = head_safe + ("  " + " ".join(bits_for(True)) if bits_for(True) else "")
        line_full = head + ("  " + " ".join(bits_for(False)) if bits_for(False) else "")
        if o["text"]:
            if dump.safe:
                dump.safe.write("%s  %s\n" % (line_safe, json.dumps(redact(o["text"]))[:220]))
            if dump.full:
                dump.full.write("%s  %s\n" % (line_full, json.dumps(" ".join(o["text"].split()))[:400]))
        else:
            if dump.safe:
                dump.safe.write(line_safe + "\n")
            if dump.full:
                dump.full.write(line_full + "\n")
    if clicks:
        # Leave the page as it was found. A revealed menu or dialog holds focus
        # and a stray keystroke inside one is the thing this whole survey is
        # being careful about.
        try:
            br.page.keyboard.press("Escape")
        except Exception:
            pass
    dump.both("")
    return final


def main():
    ap = argparse.ArgumentParser(prog="survey.py", description=__doc__.split("\n")[0])
    ap.add_argument("label")
    ap.add_argument("url")
    ap.add_argument("--out", help="the REDACTED dump - the one that is committed. It redacts the identifier forms listed in this file and no others; read them before committing a dump of a new surface.")
    ap.add_argument("--full-out", help="the whole dump, unredacted. Scratch only, never committed.")
    ap.add_argument("--probe", action="append", default=[], help="a candidate selector to count")
    ap.add_argument("--depth", type=int, default=14)
    ap.add_argument("--settle", type=int, default=7)
    ap.add_argument("--expand", action="store_true", help="click one 'see more' before measuring")
    ap.add_argument("--scope", help="outline this subtree instead of main, so a deeper depth stays readable")
    ap.add_argument("--js", action="append", default=[], help="a read-only JS expression; its JSON result is dumped")
    ap.add_argument("--click", action="append", default=[],
                    help="an accessible name to click BEFORE measuring, to reveal a menu, a "
                         "composer or a dialog. Only the names on REVEAL_ONLY are permitted and "
                         "anything else is refused - the list is an ALLOWLIST on purpose.")
    ap.add_argument("--open-read-thread", action="store_true",
                    help="on the messaging list, open a conversation this can PROVE is already "
                         "read. It cannot be aimed at a particular row and it refuses unless the "
                         "list also contains an unread one to prove the marker still works.")
    ap.add_argument("--port", type=int, default=9224)
    a = ap.parse_args()

    for p in (a.out, a.full_out):
        if p:
            os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    dump = Dump(a.out, a.full_out)
    final = "(not reached)"
    try:
        with Browser(a.port) as br:
            final = survey(br, a.label, a.url, dump, a.probe, a.depth, a.settle, a.expand,
                           a.scope, a.js, a.click, a.open_read_thread)
    finally:
        dump.close()
    # The counter this survey was charged to is on the RESULT line, so a run that
    # took a view says so where anybody reading the output can see it.
    print("RESULT survey label=%s final=%s counted=%s safe=%s full=%s"
          % (a.label, final, surface_kind(a.url), a.out, a.full_out))


if __name__ == "__main__":
    main()
