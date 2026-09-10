# -*- coding: utf-8 -*-
"""Phase 3, the invitations we have sent: taking one back.

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
import json
import re
import time

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


# ===========================================================================
# THE REST OF PHASE 3: connect, invitations, follow / unfollow, invite-to-follow.
# Measured 2026-09-10; docs/phase-3-survey-2.md is what the measurements mean.
# ===========================================================================

# Whatever dialog is on screen, in BOTH implementations. The withdraw
# confirmation is a NATIVE <dialog> with an implicit role; the custom-invite
# modal is a <div role="dialog">. A probe for either one alone reports "no
# dialog appeared" while the other sits on screen intercepting every click -
# which is exactly what happened three times on 2026-09-10.
ANY_DIALOG_JS = r"""
(sel) => {
  const out = [];
  for (const d of document.querySelectorAll(sel)) {
    const b = d.getBoundingClientRect();
    if (b.width < 20 || b.height < 12) continue;
    const t = (d.innerText || '').replace(/\s+/g, ' ').trim();
    if (!t) continue;
    out.push({
      tag: d.tagName, role: d.getAttribute('role') || null,
      labelledby: d.getAttribute('aria-labelledby') || null,
      label: d.getAttribute('aria-label') || null,
      text: t.slice(0, 900),
      buttons: [...d.querySelectorAll('button, a[role="button"]')].map(x => ({
        aria: x.getAttribute('aria-label') || null,
        text: (x.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 60),
        disabled: !!x.disabled})).slice(0, 20),
    });
  }
  return out.slice(0, 8);
}
"""

NOTE_BOX_JS = r"""
(sel) => {
  const b = document.querySelector(sel);
  if (!b) return null;
  return {value: b.value || '', len: (b.value || '').length,
          maxlength: b.getAttribute('maxlength'),
          focused: document.activeElement === b};
}
"""

RECEIVED_ROWS_JS = r"""
(sel) => {
  const clean = t => (t || '').replace(/\s+/g, ' ').trim();
  const out = [];
  for (const b of document.querySelectorAll(sel.accept)) {
    let row = b, person = null;
    for (let up = 0; up < 10 && row; up++) {
      row = row.parentElement;
      if (!row) break;
      const p = row.querySelector('a[href*="/in/"]');
      if (p) { person = p; break; }
    }
    const times = [...(row ? row.querySelectorAll(sel.time) : [])].map(t => ({
      datetime: t.getAttribute('datetime') || null, text: clean(t.innerText)}));
    out.push({
      label: b.getAttribute('aria-label') || '',
      profile: person ? person.getAttribute('href') : null,
      name_on_link: person ? clean(person.innerText) : null,
      row_text: clean(row ? row.innerText : ''),
      times: times,
    });
  }
  return out;
}
"""

# Which filter's rows are on screen. See RECEIVED_FILTER_RADIO in selectors.
FILTERS_JS = r"""
(sel) => [...document.querySelectorAll(sel)].map(e => ({
  text: (e.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 40),
  checked: e.getAttribute('aria-checked'),
}))
"""

FOLLOW_JS = r"""
(sel) => {
  const scope = document.querySelector(sel.card) || document;
  const all = [...document.querySelectorAll(sel.button)];
  const inCard = all.filter(b => scope.contains(b));
  const pick = inCard.length ? inCard : [];
  return {
    total_on_page: all.length,
    in_top_card: inCard.length,
    top_card_present: !!document.querySelector(sel.card),
    controls: pick.map(b => ({
      pressed: b.getAttribute('aria-pressed'),
      label: b.getAttribute('aria-label') || '',
      text: (b.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 40),
      following_class: (b.className || '').split(/\s+/).indexOf(sel.following) >= 0,
      disabled: !!b.disabled,
    })),
  };
}
"""

PAGE_INVITE_JS = r"""
(sel) => {
  const clean = t => (t || '').replace(/\s+/g, ' ').trim();
  const dialogs = [...document.querySelectorAll(sel.dialog)].filter(d => {
    const b = d.getBoundingClientRect();
    return b.width > 200 && b.height > 100 && clean(d.innerText);
  });
  const d = dialogs.find(x => clean(x.innerText).indexOf(sel.name) >= 0) || null;
  if (!d) return {found: false, dialogs: dialogs.length,
                  texts: dialogs.map(x => clean(x.innerText).slice(0, 120))};
  const buttons = [...d.querySelectorAll('button')].map(b => ({
    aria: b.getAttribute('aria-label') || null,
    text: clean(b.innerText).slice(0, 40), disabled: !!b.disabled}));
  return {
    found: true,
    text: clean(d.innerText).slice(0, 900),
    options: d.querySelectorAll(sel.option).length,
    selects: [...d.querySelectorAll('[aria-label^="Select "]')].map(
      b => b.getAttribute('aria-label')).slice(0, 60),
    checked: [...d.querySelectorAll(sel.checkbox)].filter(c => c.checked).length,
    buttons: buttons.slice(0, 20),
  };
}
"""


def _dialogs(br, where):
    """Every dialog on screen, in both implementations. An EMPTY result on a
    surface where one has been measured is a broken instrument, never a clean
    page - see the note on DIALOG_ANY in kit/selectors.py."""
    return br.page.evaluate(ANY_DIALOG_JS, S.DIALOG_ANY)


# ------------------------------------------------------------------- connect

def connect(a):
    """Send one person an invitation. STAGED by default: it opens the invitation,
    types the note, proves NOTHING was sent, and dismisses."""
    from . import people as P

    slug = _slug(a.url)
    if a.submit and not a.expect_name:
        die("--expect-name is REQUIRED with --submit (design rule 0.3). A URL can be a typo "
            "and a typo lands on a real different person, and an invitation cannot be "
            "unsent - withdrawing one costs that person up to three weeks.")
    note = _note_text(a)
    pace = Pace()
    dump = {"slug_asked_for": slug, "when": time.strftime("%Y-%m-%d %H:%M:%S"),
            "submit": bool(a.submit), "note_chars": len(note or "")}
    try:
        _connect_run(a, slug, note, pace, dump, P)
    finally:
        if a.dump:
            with open(a.dump, "w", encoding="utf-8") as f:
                json.dump(dump, f, indent=1, ensure_ascii=False)
            log("wrote %s" % a.dump)


def _note_text(a):
    if a.note and a.note_file:
        die("pass --note or --note-file, not both")
    if a.note_file:
        with open(a.note_file, encoding="utf-8") as f:
            return f.read().strip("\n")
    return a.note


def _connect_run(a, slug, note, pace, dump, P):
    with Browser(a.port) as br:
        # 1. THE PROFILE, through read-profile's own resolver. Amendment A1: the
        # invite control is an <a> named "Invite <Name> to connect" and the word
        # "Connect" identifies nothing on this page - the right-hand rail's
        # suggestion cards are full of it. That resolver already gets this right
        # on all three measured shapes (on the card, behind More, absent), and a
        # second implementation here would be a second opinion that drifts.
        who = P.resolve_invite(br, pace, a.url)
        dump["profile"] = {k: who[k] for k in
                           ("name", "degree", "can_connect", "can_connect_reason",
                            "connect_via", "invitation_pending")}
        name = who["name"]
        log("profile %s: %r, degree %s, can_connect=%s via %s"
            % (slug, name, who["degree"], who["can_connect"], who["connect_via"]))

        if who["invitation_pending"]:
            die("an invitation to %s is already outstanding - the profile says so: %s. "
                "Sending another is not possible, and this verb says that rather than "
                "clicking something to find out." % (name, who["can_connect_reason"]))
        if who["can_connect"] is not True or not who["connect_url"]:
            die("this profile offers no invitation to send: %s. Nothing was pressed."
                % who["can_connect_reason"])

        # RULE 0.3, FIRST NAMING: the name on the top card the invitation was
        # resolved from, against what the caller said they expected.
        if a.expect_name is not None:
            if (name or "").strip().lower() != a.expect_name.strip().lower():
                die("--expect-name is %r and this profile's top card says %r. These are two "
                    "different people and nothing was pressed." % (a.expect_name, name))

        # 2. THE CUSTOM-INVITE PAGE. Measured 2026-09-10: it is a plain GET and
        # it SENDS NOTHING - proved by counting the Sent tab's own People pill
        # before and after, 39 and 39. It renders a dialog offering "Add a note"
        # and "Send without a note", and there is no Send on it at all.
        pace.before_view("the custom-invite page for %s" % slug)
        final = br.read(who["connect_url"], "the custom-invite page", settle=7)
        pace.after_view()
        if S.ON_CUSTOM_INVITE not in final:
            die("asked for the invitation page and landed on %s. Nothing was pressed." % final)
        modal = _invite_modal(br, dump, "on landing")

        # RULE 0.3, SECOND NAMING, off the surface being acted on: the modal
        # states "Personalize your invitation to <Name> by adding a note", so
        # the person is named again by the page that is about to send to them.
        if a.expect_name is not None and a.expect_name.strip():
            if a.expect_name.strip().lower() not in (modal["text"] or "").lower():
                die("--expect-name is %r and the invitation dialog does not name that person "
                    "(it reads %r). Nothing was pressed."
                    % (a.expect_name, (modal["text"] or "")[:160]))
        dump["modal_named_the_expected_person"] = bool(a.expect_name)

        limit = None
        typed = None
        if note is not None:
            limit, typed = _add_note(br, note, dump)

        if not a.submit:
            _staged_connect(br, pace, slug, name, note, dump)
            print(json.dumps({"kind": "connect-staged", "person": "/in/" + slug,
                              "name": name, "note_chars": len(note or ""),
                              "note_limit_on_the_page": limit,
                              "note_read_back": typed}, ensure_ascii=True))
            print("RESULT connect-staged person=/in/%s name=%r note_chars=%d "
                  "note_limit_stated=%s still_connectable=true not_in_sent_tab=true "
                  "pressed=nothing"
                  % (slug, name, len(note or ""), limit))
            return

        # -- the irreversible part ------------------------------------------
        want = S.INVITE_SEND if note is not None else S.INVITE_SEND_WITHOUT_NOTE
        btn = br.page.get_by_role("button", name=re.compile(r"^%s$" % re.escape(want), re.I))
        if btn.count() != 1:
            die("expected exactly one control named %r on the invitation dialog and found "
                "%d. NOTHING WAS SENT - the other control on this dialog sends immediately "
                "with no confirmation at all." % (want, btn.count()))
        if btn.first.is_disabled():
            die("the invitation dialog's %r is disabled. Nothing was sent." % want)
        pace.before("connect")
        # A CLICK, and the reason is the same as withdraw's: this is a dialog
        # control on a surface where the keyboard was measured to do nothing on
        # the withdraw anchor, and locator.click() hit-tests - it refuses if the
        # element at that point is not this one. On this dialog the neighbour is
        # "Send without a note", so landing on the wrong control sends a
        # different invitation rather than none.
        btn.first.click(timeout=15000)
        time.sleep(ACTIVATE_SETTLE)
        pace.after("connect")
        dump["what_appeared_after_send"] = _dialogs(br, "after sending")

        # THE PROOF IS THE PROFILE AND THE SENT TAB, not the absence of an error.
        after = P.resolve_invite(br, pace, a.url)
        sent = SentList(br, pace).load()
        in_sent = sent.find(slug) is not None
        dump["pending_after"] = after["invitation_pending"]
        dump["in_sent_tab_after"] = in_sent
        problems = []
        if not after["invitation_pending"]:
            problems.append("the profile does not say an invitation is pending (%s)"
                            % after["can_connect_reason"])
        if not in_sent:
            problems.append("the invitation is not on the Sent tab (%d rows, and the page "
                            "agrees the list is %s long)" % (len(sent.rows), sent.pill))
        if problems:
            die("the invitation may or may not have been sent: %s. Check it by hand before "
                "running this again." % "; ".join(problems))
        print(json.dumps({"kind": "connected", "person": "/in/" + slug, "name": name,
                          "note_chars": len(note or ""), "outstanding": len(sent.rows)},
                         ensure_ascii=True))
        print("RESULT connected person=/in/%s name=%r note_chars=%d pending=true "
              "outstanding=%d" % (slug, name, len(note or ""), len(sent.rows)))


def _invite_modal(br, dump, where):
    """The custom-invite dialog, identified by what LABELS it.

    Measured 2026-09-10: it is a <div role="dialog" aria-labelledby=
    "send-invite-modal">. `dialog[open]` matches nothing here - that is the
    withdraw confirmation's shape - so both forms are searched and the one that
    carries this label is the one acted on. An empty result on this page is a
    broken instrument: the dialog is what the page renders on landing.
    """
    found = _dialogs(br, where)
    dump.setdefault("dialogs", {})[where] = found
    mine = [d for d in found
            if (d.get("labelledby") or "") == S.INVITE_MODAL_LABELLEDBY]
    if len(mine) != 1:
        die("the invitation page %s shows %d dialog(s) labelled %r, and exactly one was "
            "expected. What is on screen: %s. Nothing was pressed."
            % (where, len(mine), S.INVITE_MODAL_LABELLEDBY,
               json.dumps([d.get("text", "")[:120] for d in found])[:400]))
    return mine[0]


def _add_note(br, note, dump):
    """Open the note box, ENFORCE THE LIMIT THE PAGE STATES, and type.

    THE LIMIT IS READ OFF THE PAGE, NEVER REMEMBERED - design 4.1 asks for
    exactly this and it was right to: the design remembered 200 and the page
    says 300. The textarea carries NO maxlength, so the browser does not enforce
    it either; a 400-character note goes in and is rejected or truncated at
    submit time, which is the one moment a caller cannot see.
    """
    add = br.page.get_by_role("button", name=re.compile(r"^%s$" % re.escape(S.INVITE_ADD_NOTE),
                                                        re.I))
    if add.count() != 1:
        die("expected exactly one %r control on the invitation dialog and found %d. Nothing "
            "was pressed." % (S.INVITE_ADD_NOTE, add.count()))
    add.first.click(timeout=15000)
    time.sleep(ACTIVATE_SETTLE)
    modal = _invite_modal(br, dump, "after Add a note")

    m = S.NOTE_LIMIT_SENTENCE.search(modal["text"] or "")
    counter = S.NOTE_COUNTER.search(modal["text"] or "")
    limit = int(m.group(1).replace(",", "")) if m else None
    if limit is None and counter:
        limit = int(counter.group(2).replace(",", ""))
    if limit is None:
        die("the note dialog states no character limit, and this verb will not fall back on "
            "a remembered one - the design remembered 200 and the page said 300. It reads "
            "%r. Nothing was typed." % (modal["text"] or "")[:200])
    dump["note_limit_stated_on_the_page"] = limit
    log("the page states a note limit of %d characters" % limit)
    if len(note) > limit:
        die("the note is %d characters and this page states a limit of %d. LinkedIn does not "
            "enforce it in the browser - the box has no maxlength - so a longer note is "
            "rejected or silently cut at the moment it is sent, which is the one moment "
            "nobody can see. Shorten it." % (len(note), limit))

    box = br.page.locator(S.NOTE_BOX)
    if box.count() != 1:
        die("%d elements match the note box (%s). Nothing was typed."
            % (box.count(), S.NOTE_BOX))
    box.first.focus()
    # ONE insertText FOR THE WHOLE NOTE, newlines included, and NOT the per-line
    # path the message composer uses. This is a real <textarea>: Input.insertText
    # puts a newline in it as a newline and fires no key events at all, so there
    # is no Enter to be careful about. The composer is a contenteditable inside a
    # form with a submit button, which is a different element with a different
    # hazard, and each gets the path its own shape earns.
    br.page.keyboard.insert_text(note)
    time.sleep(0.4)
    got = br.page.evaluate(NOTE_BOX_JS, S.NOTE_BOX)
    if got is None or got["value"] != note:
        die("the note did not arrive in the box as written: %d characters asked for, %s in "
            "the box. Nothing was sent."
            % (len(note), "none" if got is None else got["len"]))
    # THE PAGE'S OWN READBACK. It publishes N/300 and it updates as you type, so
    # this is a second, independent statement of how many characters LinkedIn
    # believes it has - free, and not derived from the same DOM read.
    after = _invite_modal(br, dump, "after typing the note")
    c = S.NOTE_COUNTER.search(after["text"] or "")
    stated = int(c.group(1).replace(",", "")) if c else None
    dump["note_counter_on_the_page"] = stated
    if stated is not None and stated != len(note):
        die("the note box holds %d characters and the page's own counter says %d. Those are "
            "two readings of the same thing and they disagree; nothing was sent."
            % (len(note), stated))
    log("note typed: %d characters, and the page's counter agrees" % len(note))
    return limit, got["len"]


def _staged_connect(br, pace, slug, name, note, dump):
    """RULE 0.1. A staged run PROVES the pre-action state survived.

    "We did not send it" is a claim of absence and an absence certifies itself,
    so this dismisses, RE-READS THE PROFILE FROM SCRATCH, and re-reads the Sent
    tab. Two independent surfaces have to agree that no invitation exists: the
    profile still offers one, and the invitation manager does not list one.
    """
    from . import people as P

    dismiss = br.page.get_by_role("button", name=re.compile(
        r"^%s$" % re.escape(S.INVITE_DISMISS), re.I))
    if dismiss.count():
        dismiss.first.click(timeout=10000)
        time.sleep(1.0)
    dump["dialogs_after_dismiss"] = _dialogs(br, "after dismiss")

    again = P.resolve_invite(br, pace, "https://www.linkedin.com/in/%s/" % slug)
    sent = SentList(br, pace).load()
    in_sent = sent.find(slug) is not None
    dump["staged_check"] = {"can_connect": again["can_connect"],
                            "invitation_pending": again["invitation_pending"],
                            "in_sent_tab": in_sent,
                            "outstanding": len(sent.rows), "pill": sent.pill}
    problems = []
    if again["invitation_pending"]:
        problems.append("the profile now says an invitation is PENDING")
    if again["can_connect"] is not True:
        problems.append("the profile no longer offers an invitation (%s)"
                        % again["can_connect_reason"])
    if in_sent:
        problems.append("an invitation to /in/%s is now on the Sent tab" % slug)
    if problems:
        die("STAGED RUN: the surface did not survive untouched - %s. A staged run that "
            "cannot prove the pre-action state is a FAILURE, and if an invitation really "
            "did go out it is on the Sent tab and can be withdrawn - at the cost of up to "
            "three weeks before %s can be invited again." % ("; ".join(problems), name))
    log("staged: %r is still invitable and is not on the Sent tab" % name)


# --------------------------------------------------------------- invitations

def invitations(a):
    """The invitations OTHER PEOPLE have sent us. Read-only in fact: this verb
    presses nothing, and the two controls on the page that would change another
    person's world - Accept and Ignore - are out of scope for Phase 3."""
    limit = max(1, min(int(a.limit or 25), 100))
    pace = Pace()
    with Browser(a.port) as br:
        pace.before_self_view("our own invitation manager, Received tab")
        final = br.read(S.INVITATIONS_RECEIVED, "the invitation manager's Received tab",
                        settle=9)
        pace.after_view()
        if S.ON_INVITATION_MANAGER not in final:
            die("asked for the Received tab and landed on %s" % final)

        rows = br.page.evaluate(RECEIVED_ROWS_JS,
                                {"accept": 'button[aria-label^="Accept"]',
                                 "time": S.RECEIVED_ROW_TIME})
        body = br.page.evaluate("() => document.body ? document.body.innerText.slice(0, 8000) : ''")
        pills = {k.title(): int(v.replace(",", ""))
                 for k, v in S.RECEIVED_COUNT_PILL.findall(body or "")}
        which = _active_filter(br, pills)
        stated = pills.get(which)

        # A4, NARROWED, AND THIS IS THE ONE EXCEPTION TO THE ZERO-ROWS RULE IN
        # THIS TOOLKIT. It is earned only by the page publishing a number to
        # check the parse against, and the number is a PER-FILTER PILL: the
        # header reads "Focused (1) Verified (1)" and there is no "N pending
        # invitations" sentence anywhere - it was searched for and is absent. So
        # the parse is compared with the pill of the SAME filter whose rows are
        # on screen, and IF THAT PILL CANNOT BE READ the exception does not
        # apply and zero rows is a FAIL like everywhere else.
        if stated is None:
            die("the Received tab states no count for the %r filter (the pills it does state "
                "are %s), so a parse of %d row(s) cannot be checked against anything. A "
                "count that cannot be read is a broken instrument, not a licence to trust "
                "the parse - and with no count, zero rows is a failure."
                % (which, json.dumps(pills), len(rows)))
        if len(rows) != stated:
            die("the Received tab says %s (%d) and %d row(s) were parsed. Either the list "
                "was read before it finished loading or the row selector has moved."
                % (which, stated, len(rows)))
        if not rows and stated == 0:
            log("no invitations received, and the page's own %s pill agrees" % which)

        out = []
        for r in rows[:limit]:
            m = S.RECEIVED_ACCEPT_ARIA.match(r["label"] or "")
            times = r["times"] or []
            out.append({
                "kind": "invitation", "name": (m.group(1) if m else r["name_on_link"]),
                "profile_url": _abs_profile(r["profile"]),
                # DESIGN 4.6 ASKS FOR `note` AND `when` AND THIS PAGE STATES
                # NEITHER. Measured 2026-09-10 on the one invitation this
                # account had outstanding: the row carries the person, their
                # headline, Ignore and Accept, and ZERO <time> elements. So both
                # fields are looked for and reported as null when the row does
                # not state them - and `note` being null MUST NOT be read as
                # "this person sent no note". It means the row did not say. The
                # day a row carries either, this reports it without a change.
                "note": _row_note(r),
                "when": (times[0]["text"] if times else None),
                "when_datetime": (times[0]["datetime"] if times else None),
                "headline": _row_headline(r, m.group(1) if m else r["name_on_link"]),
            })
            print(json.dumps(out[-1], ensure_ascii=True))
        with_note = sum(1 for r in out if r["note"])
        with_when = sum(1 for r in out if r["when"])
        print("RESULT invitations rows=%d of=%d filter=%s page_says=%d with_note=%d "
              "with_when=%d pressed=nothing"
              % (len(out), len(rows), which, stated, with_note, with_when))


def _active_filter(br, pills):
    """Which filter's rows are on screen.

    Measured 2026-09-10: `Focused (1)` is a plain BUTTON with no aria-checked at
    all, and `Verified (1)` is a RADIO carrying aria-checked="false". There is
    no attribute anywhere that says "Focused is on" - what there is, is a
    positive way to say no filter is: no radio is checked. So an unchecked page
    means the landing set, one checked radio names its own filter, and two
    checked is a page state this was not written against.
    """
    radios = br.page.evaluate(FILTERS_JS, S.RECEIVED_FILTER_RADIO)
    on = [r for r in radios if (r.get("checked") or "").lower() == "true"]
    if len(on) > 1:
        die("%d filters are switched on at once on the Received tab (%s). Which set of rows "
            "is on screen cannot be decided, so neither can the count they should be checked "
            "against." % (len(on), json.dumps([r["text"] for r in on])))
    if len(on) == 1:
        m = S.RECEIVED_COUNT_PILL.search(on[0]["text"] or "")
        if not m:
            die("the filter that is switched on reads %r, which states no count. A4's "
                "exception is earned by the page publishing a number and this one does not."
                % on[0]["text"])
        return m.group(1).title()
    if S.RECEIVED_DEFAULT_FILTER not in pills:
        die("no filter is switched on, so the rows on screen are the landing set - and the "
            "page states no %r count for it (it states %s). Without a number to check "
            "against, this refuses."
            % (S.RECEIVED_DEFAULT_FILTER, json.dumps(pills)))
    return S.RECEIVED_DEFAULT_FILTER


def _row_note(row):
    """A note, if the row states one. See the comment at the call site: on
    2026-09-10 no row on this account carried one, so this returns null and
    that null means "the row did not say", not "there was no note"."""
    text = row.get("row_text") or ""
    m = re.search(r"[“\"](.{3,300}?)[”\"]", text)
    return m.group(1).strip() if m else None


def _row_headline(row, name):
    text = (row.get("row_text") or "").strip()
    if name and text.startswith(name):
        text = text[len(name):]
    text = re.sub(r"\s*(Ignore|Accept)\s*$", "", text.strip())
    text = re.sub(r"\s*(Ignore|Accept)\s*", " ", text).strip()
    return text or None


def _abs_profile(href):
    if not href:
        return None
    if href.startswith("http"):
        return href.split("?")[0]
    return "https://www.linkedin.com" + ("" if href.startswith("/") else "/") + href.split("?")[0]


# --------------------------------------------------------- follow / unfollow

def follow(a):
    _set_follow(a, True)


def unfollow(a):
    _set_follow(a, False)


def _set_follow(a, want):
    """Flip a company page's Follow control, and assert it flipped AFTER A
    RELOAD.

    THREE INDEPENDENT SIGNALS AGREE ON THE STATE and all three are read:
    aria-pressed, the `is-following` class token, and the accessible name. Any
    disagreement is a FAIL - a control whose three signals disagree is one this
    code cannot read, and pressing it would be a guess about somebody's page.
    """
    key = _company_key(a.url)
    pace = Pace()
    dump = {"company": key, "want": "following" if want else "not following",
            "when": time.strftime("%Y-%m-%d %H:%M:%S")}
    try:
        with Browser(a.port) as br:
            before = _follow_state(br, pace, key, "before")
            dump["state_before"] = _plain(before)
            if before["following"] == want:
                print(json.dumps({"kind": "follow", "company": key,
                                  "following": before["following"],
                                  "changed": False}, ensure_ascii=True))
                print("RESULT %s company=%s following=%s changed=false pressed=nothing"
                      % ("follow" if want else "unfollow", key, before["following"]))
                return
            # FOLLOWING IS OUTBOUND. It is visible to the Page - a Page admin
            # sees their follower count move and can see who - so it takes the
            # 45-90 second gap and a daily cap like every other outbound act,
            # rather than being filed as a read because it looks like one.
            pace.before("follow")
            # THE KEYBOARD, and here the house rule holds rather than being the
            # exception withdraw needed. That control is an <a> with a live href
            # and Enter followed the link instead of running the page's handler;
            # this one is a real <button> with aria-pressed, which is precisely
            # the element a keystroke activates. The assertion after the reload
            # is what would catch it if that reasoning is wrong.
            br.press(before["locator"], "the Follow control on %s" % key)
            time.sleep(ACTIVATE_SETTLE)
            pace.after("follow")
            after = _follow_state(br, pace, key, "after")
            dump["state_after"] = _plain(after)
            if after["following"] != want:
                die("the Follow control on %s still reads %r after being pressed and the "
                    "page reloaded. Nothing about this page changed."
                    % (key, after["name"]))
            print(json.dumps({"kind": "follow", "company": key,
                              "following": after["following"], "changed": True,
                              "was": before["following"]}, ensure_ascii=True))
            print("RESULT %s company=%s following=%s was=%s changed=true"
                  % ("follow" if want else "unfollow", key, after["following"],
                     before["following"]))
    finally:
        if a.dump:
            with open(a.dump, "w", encoding="utf-8") as f:
                json.dump({k: v for k, v in dump.items()}, f, indent=1, ensure_ascii=False)
            log("wrote %s" % a.dump)


def _plain(state):
    """A follow state without its Playwright locator, so it can be written to
    the dump file."""
    return {k: v for k, v in state.items() if k != "locator"}


def _company_key(url):
    v = (url or "").strip()
    if not v:
        die("no company given")
    m = re.search(r"/(?:company|school|showcase)/([^/?#]+)", v)
    key = (m.group(1) if m else v).strip("/").lower()
    if not key or "/" in key:
        die("cannot read a company key out of %r" % url)
    return key


def _follow_state(br, pace, key, when):
    """Read the state off the TOP CARD only, from all three signals."""
    url = S.COMPANY_MEMBER_VIEW % key
    from .browser import is_own_page
    if is_own_page(key):
        pace.before_self_view("our own Page %s (%s the follow)" % (key, when))
    else:
        pace.before_view("company page %s (%s the follow)" % (key, when))
    final = br.read(url, "the company page %s" % key, settle=7)
    pace.after_view()
    # One company URL redirected to /posts/?feedView=all and another stayed put,
    # measured on the same night, so what is asserted is the KEY surviving the
    # redirect rather than the whole URL matching what was asked for.
    if (S.COMPANY_KEY_IN_URL % key) not in final.lower():
        die("asked for the company page %s and landed on %s" % (key, final))
    got = br.page.evaluate(FOLLOW_JS, {"card": S.COMPANY_TOP_CARD, "button": S.FOLLOW_BUTTON,
                                       "following": S.FOLLOW_STATE_FOLLOWING})
    if not got["top_card_present"]:
        die("no top card on the company page %s (%s). Follow controls for OTHER "
            "organisations sit further down this page on recommendation cards, so a search "
            "that is not scoped to the top card can flip the wrong Page."
            % (key, S.COMPANY_TOP_CARD))
    if len(got["controls"]) != 1:
        die("expected exactly one Follow control on %s's top card and found %d (the page "
            "holds %d in total, the rest on recommendation cards). Nothing was pressed."
            % (key, len(got["controls"]), got["total_on_page"]))
    c = got["controls"][0]
    by_pressed = (c["pressed"] or "").lower() == "true"
    by_class = bool(c["following_class"])
    by_name = bool(S.FOLLOW_NAME_FOLLOWING.match((c["label"] or c["text"] or "").strip()))
    if not (by_pressed == by_class == by_name):
        die("the Follow control on %s disagrees with itself about its own state: "
            "aria-pressed says %s, the %r class token says %s, and its name %r says %s. "
            "A control this code cannot read is not one to press."
            % (key, by_pressed, S.FOLLOW_STATE_FOLLOWING, by_class,
               c["label"] or c["text"], by_name))
    loc = br.page.locator(S.COMPANY_TOP_CARD).locator(S.FOLLOW_BUTTON)
    return {"following": by_pressed, "name": c["label"] or c["text"],
            "pressed_attr": c["pressed"], "class_token": by_class,
            "locator": loc.first, "url": final}


# ---------------------------------------------------------- invite-to-follow

def invite_to_follow(a):
    """Invite one or more of our connections to follow a Page we administer.

    THE PROOF IS THE CREDIT COUNT AND NOT A ROW THAT SAYS "Invited". A credit is
    the thing that is actually spent; the page's own "N/50 credits available"
    line is read before and after and must fall by exactly the number invited.
    """
    key = _company_key(a.page)
    people = [p.strip() for p in (a.name or []) if p.strip()]
    if not people:
        die("--name is required, once per person: the accessible name of the row control is "
            "'Select <Full Name>', so a person is picked BY NAME and never by position in a "
            "list of twenty that reorders.")
    if len(people) > MAX_INVITES_PER_RUN:
        die("%d people asked for and this verb spends at most %d credits in one run. The "
            "Page's whole monthly budget is 50." % (len(people), MAX_INVITES_PER_RUN))
    pace = Pace()
    dump = {"page": key, "people": len(people), "submit": bool(a.submit),
            "when": time.strftime("%Y-%m-%d %H:%M:%S")}
    try:
        _invite_run(a, key, people, pace, dump)
    finally:
        if a.dump:
            with open(a.dump, "w", encoding="utf-8") as f:
                json.dump(dump, f, indent=1, ensure_ascii=False)
            log("wrote %s" % a.dump)


MAX_INVITES_PER_RUN = 5


def _invite_run(a, key, people, pace, dump):
    with Browser(a.port) as br:
        state = _invite_dialog(br, pace, key, "before")
        before = state["credits"]
        dump["credits_before"] = before
        dump["refill"] = state["refill"]
        log("the Page states %s of %s credits available, refilling %s"
            % (before, state["total"], state["refill"]))
        if before is None:
            die("the invite dialog states no credit count, and the credit is the only thing "
                "that proves an invitation was actually spent. Nothing was selected.")
        if before < len(people):
            die("%d people asked for and the Page has %d credit(s) left (refill %s). "
                "Nothing was selected." % (len(people), before, state["refill"]))

        picked = []
        for who in people:
            picked.append(_pick(br, who))
        dump["selected"] = picked
        after_pick = br.page.evaluate(PAGE_INVITE_JS, _invite_sel())
        dump["checked_after_picking"] = after_pick.get("checked")
        if after_pick.get("checked") != len(people):
            die("%d people were asked for and the dialog has %d checkbox(es) ticked. "
                "Nothing was invited." % (len(people), after_pick.get("checked")))

        if not a.submit:
            # RULE 0.1: prove the pre-action state survived. Dismiss, RELOAD the
            # dialog from its URL, and read the credit line again - the number
            # that would have moved if anything had been spent.
            br.page.keyboard.press("Escape")
            time.sleep(1.0)
            again = _invite_dialog(br, pace, key, "after staging")
            dump["credits_after_staging"] = again["credits"]
            if again["credits"] != before:
                die("STAGED RUN: the Page's credits went from %s to %s. A staged run must "
                    "spend nothing." % (before, again["credits"]))
            if again["checked"]:
                die("STAGED RUN: the reloaded dialog still has %d row(s) ticked, so this run "
                    "left a selection behind." % again["checked"])
            print(json.dumps({"kind": "invite-to-follow-staged", "page": key,
                              "people": picked, "credits": before,
                              "credits_total": state["total"]}, ensure_ascii=True))
            print("RESULT invite-to-follow-staged page=%s people=%d credits=%s unchanged=true "
                  "refill=%r pressed=nothing"
                  % (key, len(picked), before, state["refill"]))
            return

        # -- the irreversible part ------------------------------------------
        btn = br.page.get_by_role("button", name=S.PAGE_INVITE_SUBMIT)
        visible = [btn.nth(i) for i in range(btn.count()) if btn.nth(i).is_visible()]
        if len(visible) != 1:
            die("expected exactly one visible Invite button on the dialog and found %d. "
                "Nothing was invited." % len(visible))
        if visible[0].is_disabled():
            die("the dialog's Invite button is disabled with %d row(s) ticked. Nothing was "
                "invited." % len(people))
        for _ in people:
            pace.before("invite")
        visible[0].click(timeout=15000)
        time.sleep(ACTIVATE_SETTLE)
        for _ in people:
            pace.after("invite")

        after = _invite_dialog(br, pace, key, "after inviting")
        dump["credits_after"] = after["credits"]
        if after["credits"] != before - len(people):
            die("the Page's credits went from %s to %s, and %d invitation(s) should have "
                "taken it to %s. THE CREDIT IS THE THING THAT IS ACTUALLY SPENT, so this "
                "does not report a success it cannot see."
                % (before, after["credits"], len(people), before - len(people)))
        print(json.dumps({"kind": "invited-to-follow", "page": key, "people": picked,
                          "credits_before": before, "credits_after": after["credits"]},
                         ensure_ascii=True))
        print("RESULT invited-to-follow page=%s people=%d credits=%s->%s refill=%r"
              % (key, len(picked), before, after["credits"], after["refill"]))


def _invite_sel():
    return {"dialog": S.PAGE_INVITE_DIALOG, "name": S.PAGE_INVITE_DIALOG_NAME,
            "option": S.PAGE_INVITE_OPTION, "checkbox": S.PAGE_INVITE_CHECKBOX}


def _invite_dialog(br, pace, key, when):
    """Open (or re-open) the Page's invite dialog and read its credit line.

    THE DIALOG IS NOT FOUND BY ITS ACCESSIBLE NAME, and that is a correction to
    a measurement taken seven hours earlier: the first survey recorded
    aria-label="Invite to follow" and the second pass, same account and same
    Page, found aria-label=null with those words as the heading only. So it is
    found by role and CONFIRMED by what it says about itself - the heading, and
    the credits line.
    """
    url = S.PAGE_INVITE_URL % key
    from .browser import is_own_page
    if is_own_page(key):
        pace.before_self_view("our own Page's invite dialog (%s)" % when)
    else:
        # A Page we do not administer has no invite dialog at all, so this will
        # fail below - but the view is counted honestly on the way in.
        pace.before_view("a Page's invite dialog (%s)" % when)
    final = br.read(url, "the Page's invite dialog", settle=8)
    pace.after_view()
    if S.PAGE_INVITE_QUERY not in final:
        die("asked for the invite dialog and landed on %s, which does not carry %r. "
            "?invite=true redirects from /admin/ to /admin/dashboard/ and that is expected; "
            "losing the parameter is not." % (final, S.PAGE_INVITE_QUERY))
    got = br.page.evaluate(PAGE_INVITE_JS, _invite_sel())
    if not got.get("found"):
        die("no dialog on %s states %r (%d dialog(s) on screen: %s). Nothing was selected."
            % (final, S.PAGE_INVITE_DIALOG_NAME, got.get("dialogs", 0),
               json.dumps(got.get("texts", []))[:300]))
    m = S.PAGE_INVITE_CREDITS.search(got["text"] or "")
    r = S.PAGE_INVITE_REFILL.search(got["text"] or "")
    return {"credits": int(m.group(1).replace(",", "")) if m else None,
            "total": int(m.group(2).replace(",", "")) if m else None,
            "refill": r.group(1).strip() if r else None,
            "options": got.get("options"), "checked": got.get("checked"),
            "text": got["text"], "url": final}


def _pick(br, who):
    """Tick ONE person, found by the control that NAMES THEM.

    The row's checkbox is a bare `input.ember-checkbox` with no label at all and
    twenty of them are on screen before anybody has searched. What names the
    person is the row control's accessible name, "Select <Full Name>" - so that
    is what is matched, exactly, and two matches is ambiguity with no outcome.
    """
    search = br.page.locator(S.PAGE_INVITE_DIALOG).locator(S.PAGE_INVITE_SEARCH)
    if search.count():
        search.first.fill("")
        search.first.type(who, delay=20)
        time.sleep(2.5)
    want = re.compile(r"^Select %s$" % re.escape(who), re.I)
    btn = br.page.get_by_role("button", name=want)
    n = btn.count()
    if n == 0:
        btn = br.page.get_by_label(want)
        n = btn.count()
    if n != 1:
        die("expected exactly one control named 'Select %s' in the invite dialog and found "
            "%d. A credit is spent on a person, so a name that does not identify exactly "
            "one row has no outcome here." % (who, n))
    btn.first.click(timeout=15000)
    time.sleep(0.8)
    return who
