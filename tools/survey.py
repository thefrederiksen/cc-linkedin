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

Nothing here clicks, types, or submits. The only interaction is expanding a
"see more" control when --expand is given, because a collapsed About section
cannot be measured.
"""
import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kit.browser import Browser, log

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
    r"sign|log|out|verified|verify|hiring|providing|services)$",
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

SLUG = re.compile(r"(/in/)[^/?\"\s]+")
MEMBER_ID = re.compile(r"ACoA[A-Za-z0-9_-]{8,}")
QUERY_VALUE = re.compile(
    r"([?&](?:profileUrn|recipient|keywords|fsd_profile|trackingId|urlhash|mt|url)=)[^&\"\s]+",
    re.I)
# An organisation, by slug or by numeric id, on any of the paths that carry one.
ORG_PATH = re.compile(r"(/(?:company|school|showcase|organization)/)([A-Za-z0-9._%-]+)", re.I)
# Any urn that names a thing: a post, a share, an event, a comment, an org, a
# profile. The KIND stays - a selector is written against urn:li:activity - and
# the id goes.
URN = re.compile(r"(urn:li:[A-Za-z_]+:)\(?[A-Za-z0-9%_,:.()-]+\)?")
JOB = re.compile(r"(/jobs/view/)[A-Za-z0-9._%-]+", re.I)
ARTICLE = re.compile(r"(/pulse/|/newsletters/|/events/|/groups/|/posts/)[^\"\s?&]+", re.I)
# A shortened post link, plain or percent-encoded inside another URL. Following
# one recovers the post and its author, which is exactly what a short link is
# for and exactly why three of them had no business in a public docstring.
SHORT_LINK = re.compile(r"lnkd(?:\.|%2E)in(?:/|%2F)[A-Za-z0-9_/%-]+", re.I)
# A map or address URL. The one that was committed carried a postal code.
MAP_URL = re.compile(r"https?://[^\"\s]*(?:maps|/maps/|geo/)[^\"\s]*", re.I)


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
    v = MAP_URL.sub("<map url>", value)
    # BEFORE the short-link rule, so a short link nested inside a url= parameter
    # is taken out with the parameter rather than half-redacted inside it.
    v = QUERY_VALUE.sub(lambda m: m.group(1) + "<value>", v)
    v = SHORT_LINK.sub("lnkd.in/<shortlink>", v)
    v = SLUG.sub(lambda m: m.group(1) + "<slug>", v)
    v = MEMBER_ID.sub("<memberid>", v)
    v = ORG_PATH.sub(_org, v)
    v = URN.sub(lambda m: m.group(1) + "<id>", v)
    v = JOB.sub(lambda m: m.group(1) + "<jobid>", v)
    v = ARTICLE.sub(lambda m: m.group(1) + "<article>", v)
    v = QUERY_VALUE.sub(lambda m: m.group(1) + "<value>", v)
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


def survey(br, label, url, dump, probes, depth, settle, expand, scope=None, js_exprs=()):
    dump.both("# survey %s" % label)
    dump.both("# taken   %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    both_redacted(dump, "# request %s" % url)
    br.goto(url, settle=settle)
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
            for line in json.dumps(val, indent=1, ensure_ascii=True).splitlines():
                dump.text("    ", line)
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
    ap.add_argument("--port", type=int, default=9224)
    a = ap.parse_args()

    for p in (a.out, a.full_out):
        if p:
            os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    dump = Dump(a.out, a.full_out)
    final = "(not reached)"
    try:
        with Browser(a.port) as br:
            final = survey(br, a.label, a.url, dump, a.probe, a.depth, a.settle, a.expand, a.scope, a.js)
    finally:
        dump.close()
    print("RESULT survey label=%s final=%s safe=%s full=%s" % (a.label, final, a.out, a.full_out))


if __name__ == "__main__":
    main()
