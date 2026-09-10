# -*- coding: utf-8 -*-
"""Phase 3, the invitations we have sent: taking one back.

MEASURED ON THE LIVE PAGE 2026-09-10. The dump is
docs/surveys/invitations-sent-rows-2026-09-10.txt and what it means is in
docs/phase-3-withdraw-report.md.

THREE THINGS ABOUT THIS SURFACE, EACH OF WHICH HAS ITS OWN WRONG ANSWER.

1. THE WITHDRAW CONTROL IS AN ANCHOR WHOSE href IS THE FEED (amendment A5).
   Not a button. `href="https://www.linkedin.com/"`. If the page's own handler
   does not swallow the activation, the browser NAVIGATES TO THE FEED and the
   invitation is not withdrawn - and nothing anywhere says so. That is the
   defect class this whole week has been about: a success inferred from the
   absence of an error. So this verb asserts, afterwards, that it is still on
   the invitation manager, and it says exactly that when it is not.

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
  for (const d of document.querySelectorAll('[role="dialog"], [role="alertdialog"]')) {
    const box = d.getBoundingClientRect();
    if (box.width < 40 || box.height < 40) continue;
    out.push({
      role: d.getAttribute('role'),
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
        # Activated with the KEYBOARD, not a coordinate click. On an anchor,
        # Enter produces the browser's own activation - the page's handler sees
        # a real click event and can cancel the navigation - and a keystroke
        # cannot land a few pixels away on the next person's row.
        br.press(link.first, "Withdraw for %s" % row["label"])
        time.sleep(ACTIVATE_SETTLE)

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
            confirm = None
            for label in d["buttons"]:
                if S.CONFIRM_WITHDRAW.match(label.strip()):
                    confirm = label.strip()
                    break
            if confirm is None:
                die("a confirmation appeared and this verb cannot identify which control "
                    "confirms it. It holds %s and says %r. NOTHING WAS CONFIRMED and the "
                    "invitation to %s still stands - put the right name in "
                    "selectors.CONFIRM_WITHDRAW and run it again."
                    % (d["buttons"], d["text"][:200], name))
            btn = br.page.get_by_role("button", name=re.compile(r"^%s$" % re.escape(confirm), re.I))
            if btn.count() < 1:
                die("the confirmation offers %r and it cannot be located to press. Nothing "
                    "was confirmed." % confirm)
            br.press(btn.first, "the confirmation %r" % confirm)
            dump["confirmed_with"] = confirm
            time.sleep(ACTIVATE_SETTLE)
            dump["consequence_text_after_confirming"] = br.page.evaluate(CONSEQUENCE_JS)
        else:
            dump["confirmed_with"] = None
            log("no confirmation appeared: activating the control is the whole act")

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
        if a.dump:
            with open(a.dump, "w", encoding="utf-8") as f:
                json.dump(dump, f, indent=1, ensure_ascii=False)
            log("wrote %s" % a.dump)
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
