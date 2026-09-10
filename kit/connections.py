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
