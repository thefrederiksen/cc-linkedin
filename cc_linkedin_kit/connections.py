# -*- coding: utf-8 -*-
"""Phase 3, invitations: taking one back (`withdraw`), and sending one (`connect`,
at the bottom of this file, with its own measurements).

MEASURED ON THE LIVE PAGE 2026-09-10. The dump is
docs/surveys/invitations-sent-rows-2026-09-10.txt and what it means is in
docs/phase-3-withdraw-report.md.

FOUR THINGS ABOUT THIS SURFACE, EACH OF WHICH HAS ITS OWN WRONG ANSWER.

1. THE WITHDRAW CONTROL IS AN ANCHOR WITH A LIVE href (amendment A5), AND THE
   href HAS TWO FORMS, WHICH A5 DID NOT KNOW. Measured across all forty rows on
   2026-09-10: the first TEN - the server-rendered page - carry
   `href="https://www.linkedin.com/"`, the feed, exactly as the survey said. The
   THIRTY that arrive by lazy-load carry
   `href=".../mynetwork/invitation-manager/sent/"` - THIS PAGE.

   So A5's assertion, "afterwards the browser is still on the invitation
   manager", catches the trap on the first ten rows and CANNOT catch it on the
   other thirty: a fall-through navigation there reloads the Sent tab and leaves
   the address bar exactly where it was. The assertion is kept because it is
   right about the ten, and it is not enough for the thirty. What covers both is
   the count proof in point 3, plus a marker on `window` that a navigation
   destroys - which is how "the page swallowed it" is told from "the browser
   followed the link" when both end on the same URL.

4. THE CONFIRMATION IS A NATIVE <dialog>, AND IT IS WHY THIS TOOK FOUR ATTEMPTS.
   A native `<dialog>` has an IMPLICIT role, so it carries no role attribute and
   `[role="dialog"]` does not match it. The first probe looked for exactly that,
   found nothing, and reported "no confirmation appeared" three times while the
   confirmation was open on screen intercepting every pointer event. The pass
   condition was an ABSENCE and the absence was the instrument being blind. A
   missing confirmation is now a FAILURE rather than a shortcut, for that reason
   and no other.

2. THE LIST LAZY-LOADS TEN AT A TIME AND THE WINDOW IS NOT THE SCROLLER.
   `window.scrollTo(0, document.body.scrollHeight)` and twelve mouse-wheel
   events both left the list at ten rows of forty; the element that scrolls is
   `<main>`. A tool that scrolls the wrong thing sees ten rows and reports that
   somebody's invitation is not in the list. It is not a smaller list, it is a
   half-read one - the same shape as the short table row in `stats`.

3. "THE ROW IS GONE" IS AN ABSENCE, AND AN ABSENCE CERTIFIES ITSELF. A broken
   selector produces a missing row for free, and so does a page that failed to
   render. So the proof is a PRESENCE: the list is loaded to exhaustion before
   and after, the page's own `People (N)` pill is read both times, and what is
   asserted is that the total went DOWN BY EXACTLY ONE, that the pill agrees,
   and that every other row that was there before is still there. One row
   leaving is a number, not a hole.

WHAT IT COSTS THE CALLER, AND WHY THE RESULT LINE SAYS SO. Withdrawing spends
something that cannot be got back: LinkedIn will not let the same person be
invited again for a period after a withdrawal. That period is stated on the
RESULT line from what was MEASURED, and if the live surface stated nothing the
line says that instead of repeating a number from memory.
"""
import io
import json
import re
import sys
import time
import unicodedata
from urllib.parse import unquote

from . import people as P
from . import selectors as S
from .browser import Browser, Pace, log, die

# How long to let a lazy list settle after each scroll, and how many scrolls
# before a list that keeps growing is treated as broken rather than long.
SCROLL_SETTLE = 2.0
SCROLL_LIMIT = 60
# How long to let the page react to the withdraw control before reading what
# appeared. Named so the offline tests can zero it; live runs never should.
ACTIVATE_SETTLE = 2.5

ROWS_JS = r"""
() => {
  const links = [...document.querySelectorAll('a[aria-label^="Withdraw invitation sent to"]')];
  return links.map((a, i) => {
    // Walk up until the container also holds the person's profile link: that is
    // the row. Anything shallower is the control's own wrapper, anything taller
    // starts swallowing the next row - and a row that swallowed its neighbour
    // would carry two ages and two names.
    let row = a, person = null;
    for (let up = 0; up < 10 && row; up++) {
      row = row.parentElement;
      if (!row) break;
      const p = row.querySelector('a[href*="/in/"]');
      if (p) { person = p; break; }
    }
    const text = row ? (row.innerText || '') : '';
    const m = text.match(/Sent\s+([^\n]*?)\s*(?:\n|$)/);
    return {
      index: i,
      label: a.getAttribute('aria-label') || '',
      href: a.getAttribute('href') || '',
      profile: person ? person.getAttribute('href') : null,
      age: m ? ('Sent ' + m[1]) : null,
    };
  });
}
"""

# Whatever is on screen that a person would have to answer. Read AFTER the
# withdraw control is activated, and dumped whether or not it is understood.
DIALOG_JS = r"""
() => {
  const out = [];
  const sel = 'dialog[open], [data-testid*="dialog"], [role="dialog"], [role="alertdialog"]';
  for (const d of document.querySelectorAll(sel)) {
    const box = d.getBoundingClientRect();
    if (box.width < 40 || box.height < 40) continue;
    out.push({
      role: d.getAttribute('role') || d.tagName.toLowerCase(),
      label: d.getAttribute('aria-label') || '',
      text: (d.innerText || '').trim().slice(0, 1200),
      buttons: [...d.querySelectorAll('button, a[role="button"]')]
        .map(b => ((b.getAttribute('aria-label') || b.innerText || '').trim()).slice(0, 120))
        .filter(Boolean),
    });
  }
  return out;
}
"""

# Anything on the page that states a consequence, wherever it is put - a dialog,
# a toast, an inline note. Searched for by MEANING rather than by position,
# because the re-invite restriction had never been measured and could have been
# stated anywhere or nowhere.
CONSEQUENCE_JS = r"""
() => {
  const hits = [];
  const re = /(you (?:will|won'?t|can'?t|cannot)[^.]{0,120})|((?:\d+|three|two|four|six)\s*(?:weeks?|days?|months?)[^.]{0,120})|(withdraw[^.]{0,140})/gi;
  for (const e of document.querySelectorAll('body *')) {
    if (e.children.length) continue;
    const t = (e.innerText || '').trim();
    if (t.length < 12 || t.length > 400) continue;
    if (re.test(t)) hits.push(t);
    re.lastIndex = 0;
  }
  return [...new Set(hits)].slice(0, 40);
}
"""


# Everything a person would have to answer or would be told, WIDER than a
# role=dialog. The first attempt looked only for [role=dialog] and found none,
# which proves nothing on a surface whose modals had never been measured.
APPEARED_JS = r"""
() => {
  const out = [];
  // A NATIVE <dialog> HAS NO role ATTRIBUTE - it has an IMPLICIT role - so
  // '[role="dialog"]' matches nothing on this surface. That is what made the
  // first three attempts report "no confirmation appeared" while the
  // confirmation was open on screen intercepting every pointer event.
  const sel = 'dialog[open], dialog, [data-testid*="dialog"], ' +
              '[role="dialog"], [role="alertdialog"], [aria-modal="true"], ' +
              '[role="alert"], [role="status"], [data-testid*="modal"], ' +
              '[data-testid*="toast"], [class*="modal"], [class*="toast"], [class*="artdeco-modal"]';
  for (const d of document.querySelectorAll(sel)) {
    const b = d.getBoundingClientRect();
    if (b.width < 20 || b.height < 12) continue;
    const t = (d.innerText || '').trim();
    if (!t) continue;
    out.push({
      role: d.getAttribute('role') || d.tagName,
      modal: d.getAttribute('aria-modal') || null,
      text: t.slice(0, 800),
      buttons: [...d.querySelectorAll('button, a[role="button"], a')]
        .map(b2 => ((b2.getAttribute('aria-label') || b2.innerText || '').trim()).slice(0, 120))
        .filter(Boolean).slice(0, 12),
    });
  }
  return out.slice(0, 12);
}
"""


def _slug(url_or_slug):
    """The /in/ slug, from a full profile URL or from a bare slug."""
    v = (url_or_slug or "").strip()
    if not v:
        die("no profile given")
    m = re.search(r"/in/([^/?#]+)", v)
    slug = (m.group(1) if m else v).strip("/").lower()
    if not slug or "/" in slug:
        die("cannot read a profile slug out of %r" % url_or_slug)
    return slug


def age_at_least_months(age_line):
    """How many WHOLE MONTHS the displayed age proves, at minimum.

    LinkedIn shows a rounded-down relative age and never a date, so "3 months
    ago" proves at least three months and "1 month ago" proves one. Everything
    shorter than a month proves zero. An age this cannot parse returns None -
    NOT zero and not a guess - because a caller filtering on age must be able to
    tell "newer than your threshold" from "I could not read this".
    """
    line = (age_line or "").strip()
    if not line:
        return None
    line = re.sub(r"^Sent\s+", "", line, flags=re.I).strip()
    if re.match(r"^(just now|today|now)$", line, re.I):
        return 0
    if re.match(r"^yesterday$", line, re.I):
        return 0
    m = S.SENT_AGE_UNITS.match(line)
    if not m:
        return None
    n = int(m.group(1) or 1)
    unit = m.group(2).lower()
    if unit in ("second", "minute", "hour", "day", "week"):
        return 0
    if unit == "month":
        return n
    if unit == "year":
        return n * 12
    return None


class SentList(object):
    """The Sent tab, loaded to exhaustion, with the count the page publishes."""

    def __init__(self, br, pace):
        self.br = br
        self.pace = pace
        self.rows = []
        self.pill = None

    def load(self):
        self.pace.before_self_view("our own invitation manager, Sent tab")
        final = self.br.read(S.INVITATIONS_SENT, "the invitation manager's Sent tab", settle=9)
        self.pace.after_view()
        if S.ON_INVITATION_MANAGER not in final:
            die("asked for the Sent tab and landed on %s" % final)
        self._scroll_to_exhaustion()
        self.rows = self.br.page.evaluate(ROWS_JS)
        self.pill = self._count_pill()
        if not self.rows:
            die("no invitation rows on %s. Zero rows is a broken selector far more often "
                "than an account with nothing outstanding, so this is a failure and not an "
                "empty list (the row selector is %s)." % (final, S.WITHDRAW_LINK))
        # A4: the parse is checked against the pill of the SAME filter whose rows
        # were parsed. A mismatch means the list was read half-loaded, and a
        # half-loaded list is what makes "the row is not here" a wrong answer.
        if self.pill is None:
            die("the Sent tab states no 'People (N)' count, so a parse of %d rows cannot be "
                "checked against anything. A count that cannot be read is a broken instrument, "
                "not a reason to trust the parse." % len(self.rows))
        if self.pill != len(self.rows):
            die("the Sent tab says People (%d) and %d rows were parsed. The list was read "
                "before it finished loading, or the row selector has moved."
                % (self.pill, len(self.rows)))
        log("Sent tab: %d invitations, and the page agrees" % len(self.rows))
        return self

    def _scroll_to_exhaustion(self):
        """Ten rows arrive at a time and <main> is the scroller, not the window."""
        seen, stable = -1, 0
        for i in range(SCROLL_LIMIT):
            where = self.br.page.evaluate(S.SENT_SCROLLER_JS)
            time.sleep(SCROLL_SETTLE)
            n = self.br.page.evaluate(
                "() => document.querySelectorAll(%s).length" % json.dumps(S.WITHDRAW_LINK))
            if n == seen:
                stable += 1
                if stable >= 3:
                    log("list settled at %d rows after %d scrolls of %s"
                        % (n, i + 1, where["tag"]))
                    return
            else:
                stable = 0
            seen = n
        die("the Sent list was still growing after %d scrolls (%d rows). It is not being "
            "read to the end and 'the row is not here' would be a wrong answer."
            % (SCROLL_LIMIT, seen))

    def _count_pill(self):
        body = self.br.page.evaluate(
            "() => document.body ? document.body.innerText.slice(0, 6000) : ''")
        m = S.SENT_COUNT_PILL.search(body or "")
        return int(m.group(1).replace(",", "")) if m else None

    def find(self, slug):
        """The ONE row for this person. Two is ambiguity and ambiguity has no
        outcome; zero says so as itself rather than as a failure to look."""
        hits = [r for r in self.rows if r["profile"] and _slug(r["profile"]) == slug]
        if len(hits) > 1:
            die("%d rows on the Sent tab point at /in/%s. Ambiguity has no outcome here - "
                "this verb acts on a real person." % (len(hits), slug))
        return hits[0] if hits else None

    def names(self):
        return set(r["label"] for r in self.rows)


def _named_twice(row, expect_name, slug):
    """Rule 0.3: an irreversible act names its target twice. Once in the URL the
    caller passed, and once read off the control that is about to be pressed."""
    m = S.WITHDRAW_ARIA.match(row["label"] or "")
    if not m:
        die("the withdraw control for /in/%s is labelled %r, which is not the sentence this "
            "verb identifies a person by (%s). Nothing was pressed."
            % (slug, row["label"], S.WITHDRAW_ARIA.pattern))
    on_page = m.group(1).strip()
    if expect_name is not None:
        if on_page.strip().lower() != expect_name.strip().lower():
            die("--expect-name is %r and the control on the page says %r. These are two "
                "different people and nothing was pressed." % (expect_name, on_page))
    return on_page


def withdraw(a):
    """Withdraw one invitation we sent, from the invitation manager's Sent tab."""
    slug = _slug(a.url)
    if a.submit and not a.expect_name:
        die("--expect-name is REQUIRED with --submit (design rule 0.3). A URL can be a typo "
            "and a typo lands on a real different person.")
    want_months = a.older_than_months
    pace = Pace()
    dump = {"slug_asked_for": slug, "when": time.strftime("%Y-%m-%d %H:%M:%S")}

    try:
        _withdraw(a, slug, want_months, pace, dump)
    finally:
        if a.dump:
            with open(a.dump, "w", encoding="utf-8") as f:
                json.dump(dump, f, indent=1, ensure_ascii=False)
            log("wrote %s" % a.dump)


def _withdraw(a, slug, want_months, pace, dump):
    with Browser(a.port) as br:
        sent = SentList(br, pace).load()
        before_total, before_pill = len(sent.rows), sent.pill
        before_names = sent.names()

        row = sent.find(slug)
        if row is None:
            die("no outstanding invitation to /in/%s on the Sent tab (%d rows read, and the "
                "page agrees the list is %d long). Either it was accepted, it was already "
                "withdrawn, or it was never sent." % (slug, before_total, before_pill))

        name = _named_twice(row, a.expect_name, slug)
        age = row["age"]
        months = age_at_least_months(age)
        dump.update({"age_displayed": age, "age_months_at_least": months,
                     "rows_before": before_total, "pill_before": before_pill,
                     "href_on_the_control": row["href"]})
        log("row found: %s, displayed age %r (at least %s months)"
            % (row["label"], age, months))

        if want_months is not None:
            if months is None:
                die("this row's age reads %r and this verb cannot turn that into a number of "
                    "months. --older-than-months was given, so it refuses rather than guess "
                    "at the age of somebody's invitation." % age)
            if months < want_months:
                die("this invitation displays %r, which proves at most %d month(s), and "
                    "--older-than-months %d was asked for. Nothing was pressed."
                    % (age, months, want_months))

        if not a.submit:
            # A TRUE STAGE. It does NOT activate the control - see the module
            # docstring: there may or may not be a confirmation step, so
            # activating and then escaping could complete a real withdrawal.
            # Rule 0.1 asks a staged run to prove the pre-action state survived,
            # and here that is the row still being in the list it was read from.
            again = SentList(br, pace).load()
            still = again.find(slug)
            if still is None or len(again.rows) != before_total:
                die("staged run: the invitation to %s is no longer as it was (%d rows now, "
                    "%d before). A staged run must leave the surface untouched."
                    % (name, len(again.rows), before_total))
            print(json.dumps(dump, ensure_ascii=True))
            print("RESULT withdraw-staged person=/in/%s age=%r months_at_least=%s "
                  "outstanding=%d pressed=nothing"
                  % (slug, age, months, before_total))
            return

        # -- the irreversible part ------------------------------------------
        link = br.page.locator('a[aria-label="%s"]' % row["label"].replace('"', '\\"'))
        if link.count() != 1:
            die("expected exactly one control labelled %r and found %d. Nothing was pressed."
                % (row["label"], link.count()))

        pace.before("withdraw")
        # ACTIVATED WITH A REAL MOUSE CLICK ON THE ELEMENT, AND THE FIRST
        # ATTEMPT USED THE KEYBOARD AND DID NOT WORK - measured 2026-09-10.
        #
        # Everything else in this toolkit is pressed with focus + Enter, and the
        # reason is written in cc_linkedin.py: a click delivered after a dialog
        # has closed falls through to whatever is underneath it, and a keystroke
        # cannot. That reason does not reach this control. There is no dialog
        # here; the row is static; and Enter on this anchor produced NOTHING -
        # no confirmation, no change to the list, and the page's own count
        # unmoved at forty. The browser followed the anchor's href instead of
        # the page's handler running, which is A5 happening exactly as amended.
        #
        # locator.click() is a trusted CDP mouse event AND it hit-tests: it
        # scrolls the element into view, and it refuses if the element at that
        # point is not this one. So the thing the keyboard was protecting
        # against - landing a few pixels away on the next person's row - is
        # checked by the click itself rather than avoided by not clicking.
        box = link.first.bounding_box()
        # A MARKER THAT DOES NOT SURVIVE A NAVIGATION. This is how "the page
        # swallowed the activation" is told apart from "the browser followed the
        # anchor's href", and the two are otherwise identical here: for every row
        # past the first ten that href IS this page, so a fall-through navigation
        # reloads the Sent tab and leaves the address bar exactly where it was.
        # The URL assertion A5 asks for cannot see that. This can.
        br.page.evaluate("() => { window.__ccWithdrawMarker = 1; }")
        log("clicking the withdraw control for %s at %s" % (row["label"], box))
        link.first.click(timeout=15000)
        time.sleep(ACTIVATE_SETTLE)
        survived = br.page.evaluate("() => window.__ccWithdrawMarker === 1")
        dump["page_survived_the_activation"] = bool(survived)
        log("the page %s the activation" % ("SWALLOWED" if survived else "NAVIGATED away on"))
        dump["what_appeared"] = br.page.evaluate(APPEARED_JS)
        for w in dump["what_appeared"]:
            log("  appeared: %s" % json.dumps(w)[:400])

        # Whatever appeared, dumped BEFORE anything answers it. This is the
        # measurement survey section 10.4 says was never taken.
        dialogs = br.page.evaluate(DIALOG_JS)
        consequence = br.page.evaluate(CONSEQUENCE_JS)
        dump["confirmation"] = dialogs
        dump["consequence_text_on_screen"] = consequence
        dump["url_after_activating"] = br.page.url
        log("after activating: url=%s dialogs=%d" % (br.page.url, len(dialogs)))
        for d in dialogs:
            log("  dialog role=%s buttons=%s text=%r"
                % (d["role"], d["buttons"], d["text"][:300]))

        if dialogs:
            d = dialogs[0]
            # THE TARGET IS NAMED A THIRD TIME, on the last control pressed. The
            # confirm button's visible text is "Withdraw", and so is part of the
            # dialog's own heading, so a bare word has three candidates here.
            # Its ACCESSIBLE NAME is the same sentence the row carried, and that
            # is what is matched, scoped inside the open dialog.
            btn = br.page.locator(S.DIALOG_OPEN).locator(
                'button[aria-label="%s"]' % row["label"].replace('"', '\\"'))
            if btn.count() != 1:
                die("a confirmation appeared and this verb cannot identify which control "
                    "confirms it: %d buttons inside it are labelled %r. It holds %s and says "
                    "%r. NOTHING WAS CONFIRMED and the invitation to %s still stands."
                    % (btn.count(), row["label"], d["buttons"], d["text"][:200], name))
            btn.first.click(timeout=15000)
            log("confirmed: clicked the dialog's %r" % row["label"])
            dump["confirmed_with"] = row["label"]
            dump["confirmation_said"] = d["text"]
            time.sleep(ACTIVATE_SETTLE)
            dump["consequence_text_after_confirming"] = br.page.evaluate(CONSEQUENCE_JS)
        else:
            # A CONFIRMATION WAS MEASURED ON THIS SURFACE on 2026-09-10, so its
            # absence is a change in the page and not a shortcut. It is not
            # treated as one: the last time this verb said "no confirmation
            # appeared", one was open on screen intercepting every pointer
            # event, and the only thing that had gone wrong was its own probe.
            # An absence that used to be a presence is a broken instrument until
            # something proves otherwise.
            dump["confirmed_with"] = None
            die("no confirmation dialog appeared. One was measured on this surface on "
                "2026-09-10 - a native <dialog data-testid=\"dialog\"> reading 'If you "
                "withdraw now, you won't be able to resend to this person for up to 3 "
                "weeks.' - so this is either a changed page or a probe that has gone blind "
                "again. Nothing was confirmed and the invitation to %s still stands." % name)

        pace.after("withdraw")

        # -- A5: prove where we are, then prove what changed -----------------
        landed = br.page.url
        dump["url_after_confirming"] = landed
        if S.ON_INVITATION_MANAGER not in landed:
            die("the withdraw control is an anchor whose href is the feed, and the browser "
                "is now on %s. The activation was NOT swallowed by the page, so the "
                "invitation to %s was almost certainly NOT withdrawn - check it by hand "
                "before running this again." % (landed, name))

        after = SentList(br, pace).load()
        dump["rows_after"] = len(after.rows)
        dump["pill_after"] = after.pill
        gone = after.find(slug) is None
        lost = before_names - after.names()

        # The proof is a NUMBER, not a hole. A broken selector, a half-loaded
        # list and a page that failed to render all produce a missing row for
        # free; none of them produces a count that fell by exactly one with the
        # page's own pill agreeing and every other row still present.
        problems = []
        if not gone:
            problems.append("the row for /in/%s is still on the Sent tab" % slug)
        if len(after.rows) != before_total - 1:
            problems.append("the list went from %d rows to %d, not to %d"
                            % (before_total, len(after.rows), before_total - 1))
        if after.pill != before_pill - 1:
            problems.append("the page's own count went from %s to %s, not to %s"
                            % (before_pill, after.pill, before_pill - 1))
        if lost != set([row["label"]]):
            problems.append("the rows that left are %s, and exactly one was expected to"
                            % (sorted(lost) if lost else "none"))
        if problems:
            die("the withdraw did not land cleanly: %s. The browser stayed on the invitation "
                "manager, so something else moved - do not run this again until it is "
                "understood." % "; ".join(problems))

        restriction = _restriction(dump)
        dump["reinvite_restriction"] = restriction
        print(json.dumps({"kind": "withdrawn", "person": "/in/" + slug, "name": name,
                          "age_displayed": age, "age_months_at_least": months,
                          "outstanding_before": before_total,
                          "outstanding_after": len(after.rows)}, ensure_ascii=True))
        print("RESULT withdrawn person=/in/%s age=%r months_at_least=%s outstanding=%d "
              "reinvite=%s" % (slug, age, months, len(after.rows), json.dumps(restriction)))


def _restriction(dump):
    """What the live surface said about inviting this person again.

    Design 4.2 requires the RESULT line to carry the consequence, and survey
    section 10.5 records that NOTHING on any surveyed page states it. So this
    reports what was measured on THIS run and says plainly when that is nothing.
    A number repeated from memory on the line a caller reads is worse than an
    honest gap, because it is the sentence they would rely on instead of
    checking.
    """
    said = []
    # First choice: the sentence the confirmation dialog itself states, matched
    # by the pattern measured off it. This is the thing design 4.2 asked for and
    # it exists - it just could not be found until the probe could see a native
    # <dialog>.
    for d in dump.get("confirmation") or []:
        m = S.REINVITE_RESTRICTION.search(d.get("text") or "")
        if m:
            # The tight sentence, and nothing else. A RESULT line that also
            # carried the whole dialog would bury the one clause the caller has
            # to read behind the button names.
            return "stated-on-screen: you " + m.group(0).strip()
    for text in (dump.get("consequence_text_on_screen") or []) + \
                (dump.get("consequence_text_after_confirming") or []):
        if re.search(r"(weeks?|days?|months?)\b", text, re.I) and \
           re.search(r"(invit|withdraw|again|resend)", text, re.I):
            said.append(text.strip())
    for d in dump.get("confirmation") or []:
        t = (d.get("text") or "").strip()
        if re.search(r"(weeks?|days?|months?)\b", t, re.I):
            said.append(t)
    said = [s for s in dict.fromkeys(said)]
    if said:
        return "stated-on-screen: " + " / ".join(s[:200] for s in said[:3])
    return ("not-stated-on-screen: LinkedIn showed no period on the withdraw surface on "
            "2026-09-10, so this tool does not name one. Treat a withdrawal as spending the "
            "ability to invite this person again for a while and verify before relying on it.")


# ============================================================================
# `connect`: send ONE invitation to ONE person, staged by default.
# ============================================================================
#
#     cc-linkedin connect <profile URL or slug> [--note TEXT | --note-file F]
#                         [--expect-name "Name"] [--submit] [--shot out.png]
#
# THIS REACHES A REAL PERSON AND CANNOT BE TAKEN BACK - a withdrawal afterwards
# costs "up to 3 weeks" of not being able to invite them again (see withdraw).
#
# MEASURED 2026-10-20 (tools/probe_invite.py; selectors.py, PHASE 3: SENDING AN
# INVITATION). The two facts the whole verb is built round:
#
#   * PRESSING THE CARD'S Connect DOES NOT OPEN THE NOTE DIALOG. It fires an
#     SDUI "post-connect drawer" request and refreshes the top card - the shape
#     of a press that has already sent. That request was blocked while it was
#     measured, so this verb never presses that control, on the card or in the
#     More menu.
#   * THE CONTROL'S href IS THE INVITATION'S OWN PAGE. /preload/custom-invite/
#     ?vanityName=<slug> renders LinkedIn's classic modal: it names the person,
#     offers Add a note / Send without a note, and Dismiss closes it having sent
#     nothing. That is the surface this verb acts on.
#
# THE RULES, EACH ONE ENFORCED HERE RATHER THAN HOPED FOR
#
#   * STAGED BY DEFAULT. Without --submit the modal is opened, the note is typed
#     and read back, the screenshot is taken, the modal is DISMISSED, and the
#     profile is reloaded to prove the pre-action state survived: the invite
#     control still where it was, and no Pending control (design rule 0.1).
#   * WHILE THE MODAL IS OPEN, invitation-shaped requests are ABORTED in the
#     browser, and one appearing at all fails the run. On --submit the guard is
#     lifted only for the Send press itself. So "a staged run sends nothing" is
#     a property of the run, and the reload is the proof of it rather than the
#     only thing standing behind it.
#   * --submit REQUIRES --expect-name, and the top card AND the modal must each
#     name exactly that person (rule 0.3). Staged runs check it too when given.
#   * The pre-check is read-profile's own: degree 1st is already-connected, a
#     Pending control is already-pending, and anything that is not a positively
#     seen, enabled invite control whose page is for THIS person refuses.
#   * The NOTE LIMIT IS READ OFF THE MODAL - the sentence and the counter's
#     denominator, which must agree - and a longer note is refused before a
#     character is typed, never left for the box to truncate. No key is ever
#     pressed in the note box: the note goes in as one insertText, and the
#     box's value and the page's own counter are read back and compared.
#   * PACING: the send is an outbound action on pace.json's `connect` line,
#     the 45-90 s gap and the daily cap. Every page is a CAPPED view.
#
# PROOF OF SEND is LinkedIn's own Pending control on the profile after a
# reload, read by the same code read-profile uses. A Send press with no Pending
# afterwards is a FAIL saying the invitation MAY have gone.

CONNECT_SETTLE = 4         # seconds for the modal to render after the page loads
VIEWS_PER_RUN = 3          # the profile, the invitation page, the proving reload

MODAL_JS = r"""
(s) => {
  const vis = e => !!(e && (e.offsetParent || e.getClientRects().length));
  const t = e => (e ? (e.innerText || '') : '').replace(/\s+/g, ' ').trim();
  const counter = /^\s*\d+\s*\/\s*\d+\s*$/;
  const modals = [...document.querySelectorAll(s.modal)].filter(vis);
  const m = modals.length === 1 ? modals[0] : null;
  const boxes = m ? [...m.querySelectorAll(s.box)].filter(vis) : [];
  return {
    url: location.href,
    modals: modals.length,
    text: t(m),
    buttons: m ? [...m.querySelectorAll('button')].filter(vis).map(b => ({
        name: (b.getAttribute('aria-label') || t(b)).trim(),
        disabled: b.disabled === true || b.getAttribute('aria-disabled') === 'true'})) : [],
    boxes: boxes.length,
    value: boxes.length === 1 ? boxes[0].value : null,
    counters: m ? [...m.querySelectorAll('*')]
        .filter(e => !e.children.length && vis(e) && counter.test(t(e))).map(t) : [],
  };
}
"""


class Refused(Exception):
    """A decision, not a breakage: the run will not act, and says why."""


def load_note(note, note_file):
    """The note exactly as it will be put in the box, or None for no note.

    Line endings become \\n, trailing whitespace on each line and at the ends
    goes, and invisible control or format characters refuse - they cannot be
    seen in a mockup and they defeat the read-back."""
    from . import messaging as M
    if note is not None and note_file:
        die("give the note with --note or --note-file, not both")
    if note_file:
        try:
            # utf-8-sig: PowerShell 5.1 writes a BOM, and a BOM in a note is invisible.
            with io.open(note_file, encoding="utf-8-sig") as f:
                raw = f.read()
        except OSError as exc:
            die("cannot read --note-file %s: %s" % (note_file, exc))
    elif note is not None:
        raw = note
    else:
        return None
    raw = raw.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    bad = sorted({"U+%04X" % ord(c) for c in raw if c not in M.ALLOWED_INVISIBLE
                  and unicodedata.category(c) in ("Cc", "Cf")})
    if bad:
        die("the note holds invisible control or format characters (%s). They cannot be "
            "seen in a mockup and they defeat the read-back; take them out." % ", ".join(bad))
    out = "\n".join(ln.rstrip() for ln in raw.split("\n")).strip("\n")
    if not out.strip():
        die("the note is empty. Leave --note off to send without one.")
    return out


def page_length(text):
    """The length LinkedIn's counter shows: a JavaScript string length, which
    counts UTF-16 units, so an emoji outside the basic plane counts two."""
    return len((text or "").encode("utf-16-le")) // 2


def invite_slug(url):
    """The vanityName an invitation page is for, lower-cased, or None."""
    m = S.CUSTOM_INVITE.search(url or "")
    return unquote(m.group(1)).strip("/").lower() if m else None


def modal_name(text):
    """The person the modal's first state names, or None."""
    m = S.INVITE_MODAL_NAME.search(text or "")
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else None


def note_limit(text, counters):
    """The note limit the open modal states, or raise Refused naming why not.

    TWO readings, and they must agree: the sentence ("limit personal note to N
    characters") and the counter's denominator ("0/N"). One alone is read; none
    is a modal this was not measured on, and a limit that cannot be read is not
    a reason to type and hope."""
    said = S.INVITE_NOTE_LIMIT_TEXT.search(text or "")
    dens = sorted({int(S.INVITE_NOTE_COUNTER.match(c).group(2)) for c in counters or []
                   if S.INVITE_NOTE_COUNTER.match(c)})
    if len(dens) > 1:
        raise Refused("the note box shows %d different counters (%s), so which limit applies "
                      "cannot be read" % (len(dens), ", ".join(map(str, dens))))
    a = int(said.group(1)) if said else None
    b = dens[0] if dens else None
    if a is None and b is None:
        raise Refused("the note box states no limit - neither the 'limit personal note to N "
                      "characters' sentence nor an 'n/N' counter - so the note cannot be "
                      "checked against one")
    if a is not None and b is not None and a != b:
        raise Refused("the note box states two limits: %d in its sentence and %d on its counter"
                      % (a, b))
    return a if a is not None else b


def counter_value(counters):
    """The counter's numerator - what the page believes is typed - or None."""
    for c in counters or []:
        m = S.INVITE_NOTE_COUNTER.match(c)
        if m:
            return int(m.group(1))
    return None


def button_names(state):
    return [b["name"] for b in state.get("buttons") or []]


# The modal's checks as plain functions of what was read off it, so each one can
# be watched failing without a browser (review finding 2, 2026-10-20). Each
# returns why not, or None.

def box_problem(state):
    """The note box, just revealed: exactly one, and empty."""
    if state["boxes"] != 1 or (state["value"] or "") != "":
        return ("the note box is not one empty box (%d boxes, holding %d chars)"
                % (state["boxes"], len(state["value"] or "")))
    return None


def readback_problem(note, state):
    """After typing: the box holds exactly the note, the page's own counter
    agrees on its length, and one enabled 'Send invitation' is offered."""
    n = page_length(note)
    if (state["value"] or "").replace("\r\n", "\n") != note:
        return ("the note box reads back %d characters that are not the note (%d typed)"
                % (page_length(state["value"]), n))
    shown = counter_value(state["counters"])
    if shown != n:
        return "the page's own counter reads %r after typing %d characters" % (shown, n)
    send = [b for b in state["buttons"] if b["name"] == S.INVITE_SEND_NOTE]
    if len(send) != 1 or send[0]["disabled"]:
        return ("with the note typed, the modal does not offer one enabled %r button (%s)"
                % (S.INVITE_SEND_NOTE, button_names(state)))
    return None


def modal_problem(state, name):
    """The modal as first opened: one of it, naming this person, offering
    exactly the three controls it was measured with."""
    if state["modals"] != 1:
        return "the invitation page shows %d invitation modals, not one" % state["modals"]
    on = modal_name(state["text"])
    if on is None or on != re.sub(r"\s+", " ", name).strip():
        return "the invitation modal names %r and the profile names %r" % (on, name)
    want = sorted([S.INVITE_DISMISS, S.INVITE_ADD_NOTE, S.INVITE_SEND_BARE])
    if sorted(button_names(state)) != want:
        return ("the invitation modal offers %s, not the %s it was measured with. A different "
                "modal (an email check, a quota notice) is not one this verb acts on"
                % (button_names(state), want))
    return None


def visible_one(n_visible, name):
    """button(): exactly one visible control with this accessible name."""
    if n_visible != 1:
        return ("the invitation modal holds %d visible buttons named %r, not one"
                % (n_visible, name))
    return None


def decide_precheck(degree, can_connect, reason, pending, via, url, slug):
    """What the profile says before anything is opened.

    Returns ('already-connected' | 'already-pending', why) for the two answers
    that need no action, raises Refused for every no, and returns ('go', None)
    only for a positively seen, enabled invite control whose invitation page is
    for THIS person."""
    if degree == "self":
        raise Refused("this is the signed-in member's own profile")
    if degree == "1st":
        return "already-connected", "the top card shows the 1st-degree badge"
    if pending:
        return "already-pending", reason
    if can_connect is None:
        raise Refused("whether this person can be invited cannot be read off the page: %s"
                      % reason)
    if can_connect is not True:
        raise Refused("there is no invite control for this person: %s" % reason)
    if via not in ("topcard", "more-menu"):
        raise Refused("the invite control was found at %r, which this verb was not measured on"
                      % via)
    got = invite_slug(url)
    if got != slug:
        raise Refused("the invite control's page is %r, which is for %r and not for /in/%s"
                      % (url, got, slug))
    return "go", None


class Connect(object):
    """One invitation to one person. Holds the page and the facts read off it."""

    def __init__(self, br, pace, slug):
        self.br = br
        self.page = br.page
        self.pace = pace
        self.slug = slug
        self.name = None
        self.pressed = False       # a Send control was pressed: it MAY have gone
        self.blocked = []          # invitation-shaped requests aborted by the guard
        self.armed = False
        self.routed = False

    # -- the network guard ---------------------------------------------------

    # ONLY ADDRESSES SHAPED LIKE AN INVITATION ARE INTERCEPTED, and the pattern
    # is a regex so Playwright's driver does the matching. The first version
    # routed "**/*" and decided in Python - and with the sync API a route
    # handler is only answered while Python is inside a Playwright call, so
    # every request the page made during a time.sleep stalled. Measured
    # 2026-10-20: the invitation page sat on a spinner for five minutes and the
    # run never returned. Nothing LinkedIn needs to load the modal matches this
    # pattern, so nothing it needs can be held up by it. What that costs, two
    # limits: a request whose ADDRESS says nothing about invitations is not
    # caught however its body reads, and every GET passes - it must, because the
    # invitation page itself is a GET to an address that matches. An invitation
    # sent by a GET would not be caught. The reload is the proof; this is the
    # second line.

    def _guard(self, route, request):
        if not self.armed or request.method == "GET":
            return route.continue_()
        self.blocked.append(request.url.split("?")[0][:160])
        return route.abort()

    # The route is installed ONCE and never removed; `armed` decides. Measured
    # 2026-10-20: page.unroute() after Dismiss never returned - with the sync
    # API it can wait on a handler that is itself waiting for this thread - and
    # the run hung with the modal already closed. The tab closes at the end of
    # the run and takes the route with it.

    def arm(self):
        if not self.routed:
            self.page.route(S.INVITATION_REQUEST, self._guard)
            self.routed = True
        self.armed = True

    def disarm(self):
        self.armed = False

    def wait(self, seconds):
        """Wait while still answering the page. Never time.sleep with the guard
        up: see the note above the guard."""
        self.page.wait_for_timeout(int(seconds * 1000))

    # -- reading -------------------------------------------------------------

    def profile(self, why):
        """Load the profile and read it the way read-profile does. Returns
        (name, degree, (can_connect, reason, via, url, pending))."""
        self.pace.before_view("profile %s, for connect (%s)" % (self.slug, why))
        # pump=True: the route stays installed for the page's life, so a sleep
        # here would hold any matching request (review finding 5).
        final = self.br.read("https://www.linkedin.com/in/%s/" % self.slug,
                             "the profile %s" % self.slug, settle=7, pump=True)
        self.pace.after_view()
        got = P.SLUG.search(final)
        if not got or unquote(got.group(1)).lower() != self.slug:
            die("asked for the profile /in/%s and landed on %s" % (self.slug, final))
        card = self.page.evaluate(P.TOPCARD_JS, [S.PROFILE_TOPCARD,
                                                 {"fill": S.PROFILE_PRIMARY_FILL}])
        if not card or not card.get("name"):
            die("no profile top card with a name on %s (selector %s)"
                % (final, S.PROFILE_TOPCARD))
        name = re.sub(r"\s+", " ", card["name"]).strip()
        degree = P._degree(card, name)
        return name, degree, P._connect(self.br, card, name, degree)

    def modal(self):
        return self.page.evaluate(MODAL_JS, {"modal": S.INVITE_MODAL, "box": S.INVITE_NOTE_BOX})

    def button(self, name):
        """The ONE visible button in the modal with exactly this accessible name."""
        loc = self.page.locator(S.INVITE_MODAL).get_by_role("button", name=name, exact=True)
        vis = [loc.nth(i) for i in range(loc.count()) if loc.nth(i).is_visible()]
        why = visible_one(len(vis), name)
        if why:
            die("%s. Nothing was pressed." % why)
        return vis[0]

    # -- acting --------------------------------------------------------------

    def open_invitation(self, url):
        self.pace.before_view("the invitation page for %s" % self.name)
        # goto, not read: the open modal marks the page behind it aria-hidden, so
        # the "Me" control read() proves sign-in by is not in the accessibility
        # tree here (measured 2026-10-20). The profile read a moment ago proved
        # it, and the PRESENCE proof on this page is the modal itself, naming
        # the person - which a signed-out page cannot render.
        self.br.goto(url, settle=CONNECT_SETTLE, pump=True)
        self.pace.after_view()
        if invite_slug(self.page.url) != self.slug:
            die("asked for the invitation page for /in/%s and landed on %s. Nothing was sent."
                % (self.slug, self.page.url))
        try:
            self.page.locator(S.INVITE_MODAL).first.wait_for(state="visible", timeout=15000)
        except Exception:                                         # noqa: BLE001
            die("the invitation page %s showed no invitation modal (%s). Nothing was sent."
                % (url, S.INVITE_MODAL))
        self.wait(1)
        return self.modal()

    def dismiss(self):
        """Close the modal with its own Dismiss button and prove it closed."""
        self.button(S.INVITE_DISMISS).click(timeout=8000)
        deadline = time.time() + 8
        while time.time() < deadline:
            if self.modal()["modals"] == 0:
                return
            self.wait(0.5)
        die("Dismiss was pressed and the invitation modal was still open. Nothing was sent. "
            "The run's tab is closed as it ends; look at the profile before running again.")

    def type_note(self, note):
        """THE ONLY TYPING IN THIS VERB: one insertText into the note box, no key
        pressed. Then the box's value and the page's own counter are read back.
        Returns (limit, modal state)."""
        self.button(S.INVITE_ADD_NOTE).click(timeout=8000)
        try:
            self.page.locator(S.INVITE_MODAL + " " + S.INVITE_NOTE_BOX).first.wait_for(
                state="visible", timeout=10000)
        except Exception:                                         # noqa: BLE001
            die("'Add a note' was pressed and no note box (%s) appeared. Nothing was typed."
                % S.INVITE_NOTE_BOX)
        self.wait(0.8)
        st = self.modal()
        lim = note_limit(st["text"], st["counters"])
        why = box_problem(st)
        if why:
            die("%s. Nothing was typed." % why)
        n = page_length(note)
        if n > lim:
            raise Refused("the note is %d characters and this modal allows %d. Shorten it - "
                          "nothing was typed, rather than leave the box to cut it" % (n, lim))
        box = self.page.locator(S.INVITE_MODAL + " " + S.INVITE_NOTE_BOX).first
        box.click(timeout=8000)
        self.page.keyboard.insert_text(note)
        self.wait(1)
        st = self.modal()
        why = readback_problem(note, st)
        if why:
            die("%s. Nothing was sent." % why)
        log("note typed: %d characters of %d, read back exactly, and the page's counter agrees"
            % (n, lim))
        return lim, st

    def prove_unchanged(self, via):
        """Rule 0.1: after a reload the invite control is still where it was and
        there is no Pending control. Returns where the invite control is now."""
        name, degree, (can, reason, via2, url, pending) = self.profile(
            "to prove nothing was sent")
        if pending:
            die("THE PROFILE NOW SHOWS PENDING: an invitation to %s exists, and this run "
                "pressed no Send. Look at the invitation manager's Sent tab." % name)
        if can is not True or via2 != via:
            die("after the reload the invite control reads can_connect=%r via=%r, not True via "
                "%r as before (%s). The pre-action state did not survive."
                % (can, via2, via, reason))
        return via2


def _ascii_line(s):
    return str(s).encode("ascii", "replace").decode("ascii")


def connect(a):
    t0 = time.time()
    slug = _slug(a.url)
    note = load_note(a.note, a.note_file)
    expect = re.sub(r"\s+", " ", a.expect_name).strip() if a.expect_name else None
    if a.submit and not expect:
        _refused(slug, "--submit needs --expect-name: an irreversible act names its target "
                       "twice (design rule 0.3). Nothing was opened.")
    pace = Pace()
    if a.submit and pace.count("connect") >= Pace.CAPS["connect"]:
        _refused(slug, "daily cap reached for connect (%d today, cap %d). Tomorrow. Nothing "
                       "was opened." % (pace.count("connect"), Pace.CAPS["connect"]))
    if pace.count("view") + VIEWS_PER_RUN > Pace.VIEW_CAP:
        _refused(slug, "the daily view cap (%d) leaves fewer than the %d views this run "
                       "needs - the profile, the invitation page and the reload that proves "
                       "it. Tomorrow. Nothing was opened." % (Pace.VIEW_CAP, VIEWS_PER_RUN))

    with Browser(a.port) as br:
        run = Connect(br, pace, slug)
        try:
            _connect(a, run, note, expect, t0)
        except SystemExit:
            if run.pressed:
                print("FAIL the step above stopped connect AFTER a Send control was pressed: "
                      "the invitation to %s MAY HAVE GONE. Look at the profile before trying "
                      "again." % _ascii_line(run.name), flush=True)
            raise
        except Exception as exc:                                  # noqa: BLE001
            # Never a bare traceback: the caller is told what was left behind.
            if run.pressed:
                die("unexpected error after a Send control was pressed (%s: %s). The "
                    "invitation to %s MAY HAVE GONE."
                    % (type(exc).__name__, str(exc).splitlines()[0][:160], run.name))
            die("unexpected error: %s: %s. No Send control was pressed."
                % (type(exc).__name__, str(exc).splitlines()[0][:160]))


def _refused(slug, why, opened=False):
    """A refusal is a RESULT, not a FAIL: the verb decided not to act, and the
    caller - the outreach seat - needs to tell that from a broken page."""
    print(json.dumps({"kind": "connect-refused", "person": "/in/" + slug, "reason": why},
                     ensure_ascii=True))
    print("RESULT connect refused person=/in/%s sent=nothing%s reason=%s"
          % (slug, " modal=dismissed-and-proven" if opened else "",
             json.dumps(why, ensure_ascii=True)), flush=True)
    sys.exit(1)


def _connect(a, run, note, expect, t0):
    from . import inbox as I
    from . import messaging as M
    slug = run.slug

    # -- 1. the profile, read the way read-profile reads it -------------------
    name, degree, (can, reason, via, url, pending) = run.profile("before")
    run.name = name
    if expect and not I.same_person(expect, name):
        _refused(slug, "the top card names %r, not %r. Nothing was opened." % (name, expect))
    try:
        verdict, why = decide_precheck(degree, can, reason, pending, via, url, slug)
    except Refused as exc:
        _refused(slug, "%s. Nothing was opened." % exc)
    if verdict != "go":
        print(json.dumps({"kind": "connect", "person": "/in/" + slug, "name": name,
                          "degree": degree, "invitation_pending": pending}, ensure_ascii=True))
        print("RESULT connect %s person=/in/%s name=%s degree=%s sent=nothing why=%s"
              % (verdict, slug, json.dumps(name, ensure_ascii=True), degree,
                 json.dumps(why, ensure_ascii=True)))
        return
    if note is not None:
        bad = M.greeting_problem(note, name)
        if bad:
            _refused(slug, "%s. Nothing was opened."
                     % bad.replace("this conversation is with", "this person is"))
    log("%s (%s): invite control %s, nothing pending" % (name, degree, via))

    # -- 2. the invitation's own page, with the guard up ----------------------
    run.arm()
    st = run.open_invitation(url)
    why = modal_problem(st, name)
    if why:
        if st["modals"]:
            run.dismiss()
        die("%s. %s; nothing was sent."
            % (why, "Dismissed" if st["modals"] else "Nothing was pressed"))
    # The modal must name the profile's person (above), and that name was held
    # to --expect-name before anything opened - so the modal is held to it too.

    limit = None
    if note is not None:
        try:
            limit, st = run.type_note(note)
        except Refused as exc:
            run.dismiss()
            run.disarm()
            run.prove_unchanged(via)
            _refused(slug, "%s." % exc, opened=True)
    if a.shot:
        run.br.screenshot(a.shot)
        log("screenshot %s" % a.shot)
    chars = page_length(note) if note is not None else 0

    if not a.submit:
        # -- 3. staged: dismiss, then PROVE nothing happened (rule 0.1) -------
        run.dismiss()
        run.disarm()
        if run.blocked:
            die("while the modal was open the page tried to send %d invitation-shaped "
                "request(s) (%s). They were BLOCKED, so nothing went - but this surface was "
                "measured sending none, so the page has changed."
                % (len(run.blocked), ", ".join(run.blocked[:3])))
        after = run.prove_unchanged(via)
        print(json.dumps({"kind": "connect-staged", "person": "/in/" + slug, "name": name,
                          "degree": degree, "via": via, "note_chars": chars,
                          "note_limit": limit}, ensure_ascii=True))
        print("RESULT connect staged person=/in/%s name=%s degree=%s via=%s note_chars=%d "
              "note_limit=%s sent=nothing blocked=0 invite_after_reload=%s "
              "pending_after_reload=false shot=%s seconds=%d"
              % (slug, json.dumps(name, ensure_ascii=True), degree, via, chars,
                 limit if limit is not None else "-", after, a.shot or "-", time.time() - t0))
        return

    # -- 3. --submit. The gap first, then everything re-read ------------------
    run.pace.before("connect")
    st = run.modal()
    if st["modals"] != 1:
        die("after the pacing gap the invitation modal is gone (%d open). Nothing was sent."
            % st["modals"])
    # Rule 0.3 AT THE PRESS, not 90 seconds before it (review finding 1). The
    # browser is shared: the tab must still be THIS person's invitation page,
    # and without a note the modal's first state - which names the person - is
    # still the one on screen, so it must still name them.
    if invite_slug(run.page.url) != slug:
        die("after the pacing gap the tab is on %s, not the invitation page for /in/%s. "
            "Nothing was sent." % (run.page.url, slug))
    if note is None and not I.same_person(expect, modal_name(st["text"]) or ""):
        die("after the pacing gap the invitation modal names %r, not %r. Nothing was sent."
            % (modal_name(st["text"]), expect))
    if note is not None and (st["value"] or "").replace("\r\n", "\n") != note:
        die("after the pacing gap the note box no longer holds exactly the note. Nothing "
            "was sent.")
    if run.blocked:
        die("before Send the page had already tried %d invitation-shaped request(s) (%s); "
            "they were blocked, so nothing went - but the page has changed."
            % (len(run.blocked), ", ".join(run.blocked[:3])))
    control = S.INVITE_SEND_NOTE if note is not None else S.INVITE_SEND_BARE
    send = run.button(control)
    run.disarm()
    # A hit-tested CLICK on the modal's own control, named in full - never Enter.
    # The flag moves FIRST: a click that raises may still have landed.
    run.pressed = True
    send.click(timeout=8000)
    run.pace.after("connect")
    log("pressed %r" % control)
    deadline = time.time() + 15
    while time.time() < deadline and run.modal()["modals"]:
        run.wait(1)

    name2, degree2, (can2, reason2, via2, url2, pending2) = run.profile("to prove it was sent")
    if pending2 is not True:
        die("%r was pressed and after a reload the profile shows NO Pending control "
            "(can_connect=%r: %s). The invitation MAY have gone - look before trying again."
            % (control, can2, reason2))
    print(json.dumps({"kind": "connect-sent", "person": "/in/" + slug, "name": name,
                      "degree": degree, "via": via, "note_chars": chars}, ensure_ascii=True))
    print("RESULT connect sent person=/in/%s name=%s degree=%s via=%s note_chars=%d "
          "note_limit=%s pending_after_reload=true shot=%s seconds=%d"
          % (slug, json.dumps(name, ensure_ascii=True), degree, via, chars,
             limit if limit is not None else "-", a.shot or "-", time.time() - t0))
