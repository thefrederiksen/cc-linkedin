# -*- coding: utf-8 -*-
"""Phase 3, the messages: reading the inbox, reading one thread, and composing
one WITHOUT sending it by accident.

MEASURED ON THE LIVE PAGES 2026-09-10. The dumps are
docs/surveys/messaging-list-2026-09-10.txt,
messaging-thread-read-2026-09-10.txt and
messaging-compose-send-options-2026-09-10.txt; what they mean is in
docs/phase-3-survey.md section 3 and 4 and docs/phase-3-survey-2.md sections 4
and 5.

THE ONE RULE THIS FILE EXISTS FOR - design rule 0.2.

    ON LINKEDIN'S MESSAGE BOX, ENTER SENDS.

`Browser.type_text`, which every Phase 1 verb uses, presses Enter ONCE PER
NEWLINE. Point it at this composer and a three-paragraph draft sends three
fragments to a real person, and nothing takes them back. Measured on the page:
the Send control is `type=submit` INSIDE A FORM, and the account carries a
setting - "Press Enter to Send" / "Click Send" - that decides whether a bare
Enter submits it. This code never depends on which is selected, because the rule
is absolute: **the composer is never sent a bare Enter, whatever the setting
says.**

So the composer gets its own typing path, and CARE IS NOT THE GUARD - a count
is:

  1. Text goes in with `Input.insertText`, which fires no key events at all.
  2. A line break is Shift+Enter, which does not submit under either setting.
  3. The BUBBLE COUNT is read before typing and again after EVERY LINE. If it
     ever rises, a fragment has already reached the recipient, and the verb
     fails saying exactly that. Per line and not merely at the end, so a
     three-paragraph draft that has started sending stops after one fragment
     rather than three.

FOUR MORE THINGS ABOUT THIS SURFACE, EACH WITH ITS OWN WRONG ANSWER.

1. A THREAD CARRIES ONE-CLICK QUICK-REPLY BUTTONS - amendment A6. They sit at
   the end of the message list, their accessible names are "Reply to
   conversation with <a canned phrase>", and ONE CLICK ON ONE OF THEM SENDS
   THAT MESSAGE. No composer, no confirmation, no draft. So nothing inside a
   thread is CLICKED here at all: the composer is reached with `focus()`, which
   dispatches no pointer event and cannot land on a neighbour, and the only
   click this module ever makes is on the Send button, under `--submit`, after
   it has been positively identified.

2. THE BUBBLE COUNT IS `li.msg-s-message-list__event` AND NOTHING ELSE.
   `.msg-s-message-list-content > li` also holds a top-of-list marker, a hidden
   loader, a typing indicator, the quick-reply row and a bottom-of-list marker:
   it reports 9 where the answer is 4. A guard that reads 9 before and 9 after
   cannot see a fragment that went, which makes it worse than no guard, because
   somebody would trust it.

3. AN EMPTY COMPOSER HOLDS ONE CHARACTER, NOT ZERO. Measured: `innerText.length`
   on an empty `.msg-form__contenteditable` is 1. A guard that reads "empty" as
   length zero is wrong before anybody has typed.

4. OPENING A THREAD MARKS IT READ, and that cannot be undone invisibly. So
   `read-inbox` reaches the list through a bare `/messaging/compose/`, which
   renders the whole list with NOTHING selected - measured, twice, seven hours
   apart, with the unread count unmoved at four both times - and it ASSERTS that
   no thread is open rather than trusting the route. `read-thread` opens one on
   purpose and says `marked_read=true` on the line the caller reads.
"""
import json
import re
import time

from . import selectors as S
from .browser import Browser, Pace, log, die

# How long to let the list and a thread settle. Named so the offline tests can
# zero them; a live run never should.
LIST_SETTLE = 6
THREAD_SETTLE = 6
TYPE_SETTLE = 0.35

# Every conversation row on the list, with BOTH unread signals read separately
# so they can be compared rather than merged.
ROWS_JS = r"""
(sel) => {
  const cards = [...document.querySelectorAll(sel.card)];
  const clean = t => (t || '').replace(/\s+/g, ' ').trim();
  return cards.map((c, i) => {
    const li = c.closest('li') || c;
    const mark = sel.unread;
    // THE CLASS TOKEN, looked for on the card, on its list item, and on any
    // descendant of either - the measured element is an inner container and
    // which ancestor it hangs off is not something to guess at.
    const hasClass = (li.className || '').includes(mark)
                     || (c.className || '').includes(mark)
                     || !!li.querySelector('.' + mark);
    // THE SECOND, INDEPENDENT SIGNAL: the page's own "N unread message(s)"
    // element. Two signals for one fact, so that a renamed class shows up as a
    // DISAGREEMENT rather than as an inbox that quietly has nothing unread.
    const countEl = li.querySelector(sel.unreadCount);
    const nameEl = li.querySelector(sel.names);
    const snipEl = li.querySelector(sel.snippet);
    const timeEl = li.querySelector(sel.time);
    return {
      index: i,
      participant: nameEl ? clean(nameEl.innerText) : null,
      // Present on 8 of 10 rows, measured. A parser that REQUIRED it would drop
      // a fifth of the inbox and report the rest as a complete read.
      last_line: snipEl ? clean(snipEl.innerText) : null,
      when: timeEl ? clean(timeEl.innerText) : null,
      when_datetime: timeEl ? (timeEl.getAttribute('datetime') || null) : null,
      unread_class: hasClass,
      unread_count_label: countEl ? (countEl.getAttribute('aria-label') || '') : null,
      href: li.querySelector('a[href*="/messaging/thread/"]')
            ? li.querySelector('a[href*="/messaging/thread/"]').getAttribute('href') : null
    };
  });
}
"""

# What is on screen that says a thread is OPEN. Read as a guard, not as data:
# read-inbox must find zero of each.
THREAD_OPEN_JS = r"""
(sel) => ({
  events: document.querySelectorAll(sel.event).length,
  quickReplies: document.querySelectorAll(sel.quick).length,
  titleBar: document.querySelectorAll(sel.title).length,
})
"""

MESSAGES_JS = r"""
(sel) => {
  const clean = t => (t || '').replace(/\s+/g, ' ').trim();
  const out = [];
  let sender = null;
  for (const li of document.querySelectorAll(sel.event)) {
    const nameEl = li.querySelector(sel.sender);
    // A run of consecutive messages from one person names them ONCE, on the
    // first of the run. Carrying the last seen name forward is what makes the
    // second message of a run attributable at all; a parser that reported null
    // there would attribute half a conversation to nobody.
    if (nameEl && clean(nameEl.innerText)) sender = clean(nameEl.innerText);
    const bodyEl = li.querySelector(sel.body);
    const timeEl = li.querySelector(sel.time);
    out.push({
      sender: sender,
      sender_stated_here: !!(nameEl && clean(nameEl.innerText)),
      text: bodyEl ? clean(bodyEl.innerText) : null,
      when: timeEl ? clean(timeEl.innerText) : null,
    });
  }
  return out;
}
"""

COMPOSER_JS = r"""
(sel) => {
  const box = document.querySelector(sel.box);
  const send = document.querySelector(sel.send);
  return {
    present: !!box,
    text: box ? (box.innerText || '') : null,
    len: box ? (box.innerText || '').length : null,
    focused: !!(box && document.activeElement === box),
    // A contenteditable's focus can land on a child node rather than on the box
    // itself, so "is the focus inside the composer" is asked as well.
    focusInside: !!(box && box.contains(document.activeElement)),
    sendPresent: !!send,
    sendDisabled: send ? !!send.disabled : null,
    sendType: send ? send.getAttribute('type') : null,
    sendInForm: send ? !!send.closest('form') : null,
  };
}
"""


def _sel_list():
    return {"card": S.CONVO_CARD, "unread": S.CONVO_UNREAD_CLASS,
            "unreadCount": S.CONVO_UNREAD_COUNT, "names": S.CONVO_NAMES,
            "snippet": S.CONVO_SNIPPET, "time": S.CONVO_TIME}


def _sel_thread():
    return {"event": S.THREAD_EVENT, "sender": S.THREAD_SENDER,
            "body": S.THREAD_BODY, "time": S.THREAD_TIME,
            "quick": S.QUICK_REPLIES, "title": S.THREAD_TITLE_BAR}


def _sel_composer():
    return {"box": S.COMPOSER, "send": S.COMPOSER_SEND}


# --------------------------------------------------------------- thread_ref
#
# AMENDMENT A3. `read-inbox` cannot return a thread URL: the list's rows are not
# links and carry no id in any attribute, and the id first exists in the address
# bar AFTER a row is clicked - which is the thing read-inbox must not do. As
# design 4.4 was written it asked for a field obtainable only by doing what 4.4
# prohibits.
#
# So what comes back is an opaque handle built from what the row ACTUALLY
# carries: the participant, the last message's displayed time, and the row's
# position under a stated filter. It is not a URL and it is not stable - the
# list reorders as messages arrive - which is why resolving one re-reads the
# list and requires the participant and time to identify exactly ONE row. The
# position is carried for the caller's benefit and is deliberately NOT part of
# the match.
REF_PREFIX = "thread-ref:"


def make_ref(row, filter_name):
    return REF_PREFIX + json.dumps(
        {"who": row.get("participant"), "when": row.get("when"),
         "row": row.get("index"), "filter": filter_name},
        sort_keys=True, ensure_ascii=True)


def is_ref(value):
    return (value or "").strip().startswith(REF_PREFIX)


def parse_ref(value):
    raw = (value or "").strip()[len(REF_PREFIX):]
    try:
        got = json.loads(raw)
    except Exception:
        die("this is not a thread reference this tool wrote: %r. read-inbox prints one per "
            "row as `thread_ref`." % (value or "")[:80])
    if not isinstance(got, dict) or not got.get("who"):
        die("a thread reference must name a participant, and %r does not." % (value or "")[:80])
    return got


# ------------------------------------------------------------------ the list

class Inbox(object):
    """The conversation list, read WITHOUT opening anything."""

    def __init__(self, br, pace):
        self.br = br
        self.pace = pace
        self.rows = []
        self.filter = S.RECEIVED_DEFAULT_FILTER
        self.unread_marker_seen = False

    def load(self, unread_only=False):
        # A2 leaves /messaging/compose/ on the CAPPED counter, and this obeys
        # that as it stands. It is also the wrong way round and the report says
        # so: A2 uncapped `/messaging/` because it is the owner's own inbox and
        # notifies nobody, and `/messaging/compose/` is the only route to that
        # inbox this mission can prove does not mark somebody's conversation
        # read. Spending a capped view is the conservative direction, so this
        # verb takes the cost rather than re-scoring a safety ruling to suit
        # itself - the thing docs/ruling-view-cap-2026-09-09.md forbids by name.
        self.pace.before_view("our own messaging inbox, through the compose route")
        final = self.br.read(S.MESSAGING_INBOX, "the messaging inbox", settle=LIST_SETTLE)
        self.pace.after_view()
        if S.ON_MESSAGING not in final:
            die("asked for the messaging inbox and landed on %s" % final)
        self._assert_no_thread_open("on landing")
        if unread_only:
            self._apply_unread_filter()
        self.rows = self.br.page.evaluate(ROWS_JS, _sel_list())
        if not self.rows:
            die("no conversation rows on %s. Zero rows is a broken selector far more often "
                "than an inbox with nothing in it, so this is a failure and not an empty "
                "list (the row selector is %s)." % (final, S.CONVO_CARD))
        self._reconcile_unread()
        log("inbox: %d conversations, %d unread, filter=%s"
            % (len(self.rows), sum(1 for r in self.rows if r["unread_class"]), self.filter))
        return self

    def _assert_no_thread_open(self, where):
        """THE GUARD THAT MAKES read-inbox HONEST. Opening a thread marks it
        read; the compose route was measured not to open one; this asserts it
        rather than trusting it, so the day LinkedIn changes that behaviour the
        run goes red instead of quietly marking somebody's conversation read
        every time the inbox is listed."""
        got = self.br.page.evaluate(THREAD_OPEN_JS, _sel_thread())
        if got["events"] or got["titleBar"]:
            die("a conversation is OPEN on the inbox %s (%d message bubbles, %d title bars, "
                "%d quick-reply rows). The compose route was measured on 2026-09-10 to render "
                "the list with nothing selected; if that has changed, THIS RUN HAS ALREADY "
                "MARKED SOMEBODY'S CONVERSATION READ and that cannot be undone. Do not run "
                "read-inbox again until it is understood."
                % (where, got["events"], got["titleBar"], got["quickReplies"]))

    def _apply_unread_filter(self):
        """Drive the PAGE'S OWN unread filter rather than filtering rows here.
        The page knows what unread means; this code is reading a class token."""
        pill = self.br.page.locator(S.INBOX_UNREAD_PILL)
        if pill.count() != 1:
            die("--unread asks for the inbox's own Unread filter and %d controls match %s. "
                "Filtering the rows here instead would answer a different question - what "
                "this code thinks unread means, rather than what the page does."
                % (pill.count(), S.INBOX_UNREAD_PILL))
        self.br.press(pill.first, "the inbox's Unread filter")
        time.sleep(LIST_SETTLE)
        self.filter = "UNREAD"
        self._assert_no_thread_open("after the Unread filter")

    def _reconcile_unread(self):
        """TWO SIGNALS FOR ONE FACT, and a disagreement is a FAIL.

        The per-row unread FLAG is a class token; the per-row unread COUNT is a
        separate element carrying "N unread message(s)". Both were measured
        present on 2026-09-10. If the class is ever renamed, a verb reading only
        the class reports an inbox with nothing unread - an absence certifying
        itself, on a field callers will act on. Reading both and comparing turns
        that into a red run.

        AN INBOX WITH NOTHING UNREAD IS ORDINARY, so no-marker-anywhere is NOT a
        failure. It is reported as `unread_marker_seen=false` on the RESULT line,
        which says plainly that the run could not confirm the marker still works
        - never as a quiet "nothing is unread".
        """
        disagree = [r for r in self.rows
                    if bool(r["unread_class"]) != bool(r["unread_count_label"])]
        if disagree:
            die("%d row(s) disagree with themselves about being unread: the class token %r "
                "and the page's own unread-count element give different answers (rows %s). "
                "One of the two has moved, and a verb reading only one of them would report "
                "an inbox that quietly has nothing unread."
                % (len(disagree), S.CONVO_UNREAD_CLASS,
                   ", ".join(str(r["index"]) for r in disagree[:6])))
        self.unread_marker_seen = any(r["unread_class"] for r in self.rows)

    def find_ref(self, ref):
        """The ONE row a thread reference names. Two is ambiguity and ambiguity
        has no outcome here - resolving one opens a real conversation."""
        who, when = ref.get("who"), ref.get("when")
        hits = [r for r in self.rows
                if (r["participant"] or "") == who and (when is None or (r["when"] or "") == when)]
        if not hits:
            die("no conversation on this list matches that reference (%d rows read). A "
                "thread reference is built from the row as it was, and the list reorders as "
                "messages arrive - read the inbox again and take a current one."
                % len(self.rows))
        if len(hits) > 1:
            die("%d conversations match that reference. Ambiguity has no outcome here: "
                "resolving it opens somebody's real conversation and marks it read."
                % len(hits))
        return hits[0]


# ---------------------------------------------------------------- read-inbox

def read_inbox(a):
    """The conversation LIST. It does not open a thread, and it proves it."""
    limit = max(1, min(int(a.limit or 25), 100))
    pace = Pace()
    with Browser(a.port) as br:
        inbox = Inbox(br, pace).load(unread_only=bool(a.unread))
        rows = inbox.rows[:limit]
        for r in rows:
            rec = {"kind": "conversation", "index": r["index"],
                   "participant": r["participant"], "last_line": r["last_line"],
                   "when": r["when"], "when_datetime": r["when_datetime"],
                   "unread": bool(r["unread_class"]),
                   "thread_ref": make_ref(r, inbox.filter)}
            print(json.dumps(rec, ensure_ascii=True))
        # The guard again, AFTER the parse. Everything between the landing check
        # and here is a read, but saying so is cheaper than assuming it.
        inbox._assert_no_thread_open("at the end of the run")
        unread = sum(1 for r in rows if r["unread_class"])
        print("RESULT read-inbox rows=%d of=%d unread=%d filter=%s unread_marker_seen=%s "
              "opened_nothing=true"
              % (len(rows), len(inbox.rows), unread, inbox.filter,
                 "true" if inbox.unread_marker_seen else
                 "false (no row on this list carries the unread marker, so this run could "
                 "not confirm the marker still works - do not read that as an inbox with "
                 "nothing unread)"))


# --------------------------------------------------------------- read-thread

def read_thread(a):
    """One conversation, in order. IT MARKS THE THREAD READ and says so."""
    pace = Pace()
    with Browser(a.port) as br:
        opened = _open_thread(br, pace, a.url)
        msgs = br.page.evaluate(MESSAGES_JS, _sel_thread())
        if not msgs:
            die("no message bubbles in this thread (%s counted zero). An open conversation "
                "with nothing in it is a broken selector far more often than an empty "
                "thread." % S.THREAD_EVENT)
        for i, m in enumerate(msgs):
            print(json.dumps({"kind": "message", "index": i, "sender": m["sender"],
                              "text": m["text"], "when": m["when"]}, ensure_ascii=True))
        # A6, reported rather than merely avoided: the caller is told the thread
        # carries controls that send with one click, because a person reading
        # this output may go and drive the page by hand next.
        quick = br.page.locator(S.QUICK_REPLIES).count()
        print("RESULT read-thread messages=%d with=%r url=%s marked_read=true "
              "quick_reply_rows=%d"
              % (len(msgs), opened["name"], opened["url"], quick))


def _open_thread(br, pace, target):
    """Open one conversation and return {url, name, slug}.

    THIS IS A WRITE WEARING A READ'S CLOTHES and every caller of it says so on
    its RESULT line. Opening a thread marks it read and can show the other
    participant a read receipt, which is why amendment A2 leaves a THREAD on the
    capped counter while the list is not.
    """
    if is_ref(target):
        ref = parse_ref(target)
        inbox = Inbox(br, pace).load()
        row = inbox.find_ref(ref)
        pace.before_view("one messaging thread (resolved from a thread reference)")
        _click_row(br, row)
        pace.after_view()
    else:
        if S.ON_MESSAGING not in (target or "") or not S.THREAD_URL.search(target or ""):
            die("read-thread takes a thread URL containing /messaging/thread/<id>/, or a "
                "thread_ref that read-inbox printed. %r is neither." % (target or "")[:80])
        pace.before_view("one messaging thread")
        br.read(target, "a messaging thread", settle=THREAD_SETTLE)
        pace.after_view()
    return _thread_header(br)


def _click_row(br, row):
    """Open the conversation at `row`'s index, and prove it is the right one.

    A CLICK, and this is the one place in this module that makes one on the
    list. There is no href to navigate to - amendment A3 - so a row can only be
    opened by pressing it. It is identified by the participant name the row
    itself carries, read again immediately before the click and compared, so a
    list that reordered between the read and the click cannot open the wrong
    person's conversation.
    """
    fresh = br.page.evaluate(ROWS_JS, _sel_list())
    here = [r for r in fresh if r["index"] == row["index"]]
    if not here or (here[0]["participant"] or "") != (row["participant"] or ""):
        die("the conversation list moved between reading it and opening a row: position %d "
            "was %r and is now %r. Nothing was opened."
            % (row["index"], row["participant"],
               here[0]["participant"] if here else "gone"))
    cards = br.page.locator(S.CONVO_CARD)
    if cards.count() <= row["index"]:
        die("the list holds %d rows and row %d was asked for. Nothing was opened."
            % (cards.count(), row["index"]))
    cards.nth(row["index"]).click(timeout=15000)
    time.sleep(THREAD_SETTLE)


def _thread_header(br):
    """Who this open thread is with, read off the title bar - and the ONE place
    rule 0.3's second naming comes from for `message`."""
    link = br.page.locator(S.THREAD_HEADER_LINK)
    if link.count() < 1:
        die("this conversation's title bar carries no link to a profile (%s found none), so "
            "there is no way to say who the composer is pointed at. Nothing was typed."
            % S.THREAD_HEADER_LINK)
    name = (link.first.inner_text() or "").strip()
    href = link.first.get_attribute("href") or ""
    m = re.search(r"/in/([^/?#]+)", href)
    return {"url": br.page.url, "name": name, "slug": (m.group(1).lower() if m else None)}


# -------------------------------------------------------------------- message

def _bubbles(br):
    return br.page.locator(S.THREAD_EVENT).count()


def _composer(br):
    got = br.page.evaluate(COMPOSER_JS, _sel_composer())
    if not got["present"]:
        die("there is no message composer on this page (%s found none). Nothing was typed."
            % S.COMPOSER)
    return got


def _focus_composer(br):
    """Put the keyboard in the composer WITHOUT clicking.

    A6, and it is the reason this is `focus()` and not `click()`. A thread's
    message list ends with one-click quick-reply buttons that send canned text
    to that person with no draft stage, and a coordinate click that misses by a
    few pixels on this surface does not produce a typo - it sends a message.
    `focus()` dispatches no pointer event at all, so there is nothing to miss
    with, and the composer is identified by a selector that matches exactly one
    element before it is touched.
    """
    box = br.page.locator(S.COMPOSER)
    if box.count() != 1:
        die("%d elements match the message composer (%s). This module will not type into a "
            "page where the composer cannot be identified as exactly one element."
            % (box.count(), S.COMPOSER))
    box.first.focus()
    time.sleep(0.3)
    got = _composer(br)
    if not (got["focused"] or got["focusInside"]):
        die("focusing the message composer did not put the keyboard in it. Nothing was "
            "typed - a keystroke aimed at an unknown element on THIS page can send a "
            "message to a real person.")
    return box


def _type_message(br, text, before):
    """Rule 0.2's typing path, with the count that can fire.

    NEVER A BARE ENTER. Text goes in with Input.insertText, which fires no key
    events; a line break is Shift+Enter, which does not submit under either of
    the account's two send settings. And because both of those are care rather
    than proof, the bubble count is read AFTER EVERY LINE: if it rises, a
    fragment has already reached the recipient and this says so at once, rather
    than finishing the draft and sending two more.
    """
    lines = (text or "").split("\n")
    for i, line in enumerate(lines):
        if i:
            br.page.keyboard.press("Shift+Enter")
        if line:
            br.page.keyboard.insert_text(line)
        time.sleep(TYPE_SETTLE)
        now = _bubbles(br)
        if now != before:
            die("THE THREAD GAINED A MESSAGE WHILE THIS DRAFT WAS BEING TYPED: %d bubbles "
                "before, %d after line %d of %d. A FRAGMENT OF THIS MESSAGE HAS REACHED THE "
                "RECIPIENT AND CANNOT BE TAKEN BACK. Typing stopped here rather than sending "
                "the remaining %d line(s) as further fragments. Check the conversation by "
                "hand." % (before, now, i + 1, len(lines), len(lines) - i - 1))


def _clear_composer(br):
    """Take the draft back out, and prove the box is empty.

    Ctrl+A inside a focused contenteditable selects that element's contents, and
    Delete removes them. The focus is asserted first, because Ctrl+A with the
    focus elsewhere selects the whole document instead - harmless here, since
    Delete on a non-editable selection does nothing, but it would leave the
    draft in place while this returned as if it had cleared it.
    """
    _focus_composer(br)
    br.page.keyboard.press("Control+A")
    br.page.keyboard.press("Delete")
    time.sleep(TYPE_SETTLE)
    got = _composer(br)
    if got["len"] is not None and got["len"] > S.COMPOSER_EMPTY_LEN:
        die("the draft is still in the composer after clearing it (%d characters, and an "
            "empty box holds %d). A staged run must leave the surface as it found it."
            % (got["len"], S.COMPOSER_EMPTY_LEN))
    return got


def message(a):
    """Compose a message. STAGED by default: it types, proves nothing went, and
    takes the draft back out. `--submit` presses Send."""
    text = _text_of(a)
    if a.submit and not a.expect_name:
        die("--expect-name is REQUIRED with --submit (design rule 0.3). A URL can be a typo "
            "and a typo lands on a real different person, and a message cannot be unsent.")
    pace = Pace()
    dump = {"when": time.strftime("%Y-%m-%d %H:%M:%S"), "submit": bool(a.submit),
            "lines": len((text or "").split("\n")), "chars": len(text or "")}
    try:
        _message(a, text, pace, dump)
    finally:
        if a.dump:
            with open(a.dump, "w", encoding="utf-8") as f:
                json.dump(dump, f, indent=1, ensure_ascii=False)
            log("wrote %s" % a.dump)


def _text_of(a):
    if a.text and a.text_file:
        die("pass --text or --text-file, not both")
    if a.text_file:
        with open(a.text_file, encoding="utf-8") as f:
            return f.read().strip("\n")
    if not a.text:
        die("--text or --text-file is required: there is nothing to compose")
    return a.text


def _message(a, text, pace, dump):
    with Browser(a.port) as br:
        header = _open_target(br, pace, a.url)
        dump["thread_url"] = header["url"]
        dump["recipient_on_the_page"] = header["name"]

        # RULE 0.3, and this surface offers the naming TWICE on one control: the
        # title bar's link carries the recipient's displayed name AND their
        # profile slug. So --expect-name is checked against the name, and the
        # /in/ slug the caller passed - when they passed one - is checked
        # against the slug. Two readings of the same control, either of which
        # can catch a thread that is not the one asked for.
        if a.expect_name is not None:
            if (header["name"] or "").strip().lower() != a.expect_name.strip().lower():
                die("--expect-name is %r and this conversation's title bar says %r. These "
                    "are two different people and NOTHING WAS TYPED."
                    % (a.expect_name, header["name"]))
        want = re.search(r"/in/([^/?#]+)", a.url or "")
        if want and header["slug"] and want.group(1).lower() != header["slug"]:
            die("this conversation is with /in/%s and /in/%s was asked for. Nothing was "
                "typed." % (header["slug"], want.group(1).lower()))

        before = _bubbles(br)
        last_before = _last_text(br)
        dump["bubbles_before"] = before
        pre = _composer(br)
        dump["composer_before"] = {k: pre[k] for k in
                                   ("len", "sendDisabled", "sendType", "sendInForm")}
        # THE EMPTY-COMPOSER PRE-FLIGHT, measured 2026-09-10: on an empty form
        # Send is disabled. A run that finds it ENABLED before it has typed
        # anything is looking at something other than an empty composer - a
        # restored draft, most likely - and typing into that appends to somebody
        # else's half-written sentence.
        if pre["len"] is not None and pre["len"] > S.COMPOSER_EMPTY_LEN:
            die("the composer already holds %d characters before this run typed anything "
                "(an empty box holds %d). That is a draft this run did not write, and "
                "typing into it would send the two together. Nothing was typed."
                % (pre["len"], S.COMPOSER_EMPTY_LEN))
        log("thread with %r: %d message(s), composer empty, Send disabled=%s"
            % (header["name"], before, pre["sendDisabled"]))

        _focus_composer(br)
        _type_message(br, text, before)
        after_typing = _bubbles(br)
        dump["bubbles_after_typing"] = after_typing
        got = _composer(br)
        dump["composer_after_typing_len"] = got["len"]
        # THE READBACK. What the box holds is compared with what was asked for,
        # normalised for whitespace only - the contenteditable renders a line
        # break as its own node and the exact character is not something to
        # assert on.
        if _norm(got["text"]) != _norm(text):
            die("the composer holds %d characters and the draft is %d, and they do not "
                "match after normalising whitespace. The text did not arrive as written; "
                "nothing has been sent and the draft is being taken back out."
                % (got["len"] or 0, len(text)))
        # Rule 0.2's guard, stated once more at the end. Per-line it has already
        # fired if it was going to; this is the whole-draft statement of the
        # same fact, and it is what design row P3-7 asserts.
        if after_typing != before:
            die("the thread had %d messages before typing and has %d now. Something reached "
                "the recipient." % (before, after_typing))

        if not a.submit:
            _clear_composer(br)
            # RULE 0.1. "We did not send" is a claim of ABSENCE and an absence
            # certifies itself, so the surface is re-read from scratch: reload,
            # and assert the thread is exactly as it was AND the draft is gone.
            pace.before_view("re-reading the thread to prove the staged run changed nothing")
            br.read(header["url"], "the thread, re-read after staging", settle=THREAD_SETTLE)
            pace.after_view()
            again = _bubbles(br)
            last_after = _last_text(br)
            box = _composer(br)
            dump["bubbles_after_reload"] = again
            problems = []
            if again != before:
                problems.append("the thread had %d messages and now has %d" % (before, again))
            if _norm(last_after) != _norm(last_before):
                problems.append("the last message was %r and is now %r"
                                % ((last_before or "")[:60], (last_after or "")[:60]))
            if box["len"] is not None and box["len"] > S.COMPOSER_EMPTY_LEN:
                problems.append("the composer still holds %d characters, so the draft "
                                "survived the reload" % box["len"])
            if problems:
                die("staged run: the surface did NOT survive untouched - %s. A staged run "
                    "that cannot prove the pre-action state is a failure, not a success."
                    % "; ".join(problems))
            print(json.dumps({"kind": "message-staged", "with": header["name"],
                              "thread": header["url"], "bubbles": before,
                              "chars": len(text), "lines": dump["lines"]},
                             ensure_ascii=True))
            print("RESULT message-staged with=%r bubbles=%d unchanged=true draft_cleared=true "
                  "chars=%d lines=%d sent=nothing"
                  % (header["name"], before, len(text), dump["lines"]))
            return

        # -- the irreversible part ------------------------------------------
        send = br.page.locator(S.COMPOSER_SEND)
        if send.count() != 1:
            die("%d controls match the composer's Send button (%s). NOTHING WAS SENT - on "
                "this surface a control that cannot be identified as exactly one element is "
                "next to buttons that send canned replies with one click."
                % (send.count(), S.COMPOSER_SEND))
        if send.first.is_disabled():
            die("the composer's Send button is disabled with a %d-character draft in the "
                "box. Nothing was sent." % (got["len"] or 0))
        pace.before("message")
        # A CLICK, and it is the only one this module makes inside a thread. It
        # is the Send button of the composer this run typed into, matched as
        # exactly one element, and locator.click() hit-tests - it refuses if the
        # element at that point is not this one, which on a surface carrying
        # one-click quick replies is the check that matters.
        send.first.click(timeout=15000)
        time.sleep(THREAD_SETTLE)
        pace.after("message")

        pace.before_view("re-reading the thread to prove what was sent")
        br.read(br.page.url, "the thread, re-read after sending", settle=THREAD_SETTLE)
        pace.after_view()
        msgs = br.page.evaluate(MESSAGES_JS, _sel_thread())
        dump["bubbles_after_send"] = len(msgs)
        last = msgs[-1] if msgs else None
        problems = []
        if len(msgs) != before + 1:
            problems.append("the thread had %d messages and now has %d, not %d"
                            % (before, len(msgs), before + 1))
        if last is None or _norm(last.get("text")) != _norm(text):
            problems.append("the last message is %r and this run sent %r"
                            % ((last or {}).get("text", "")[:60], text[:60]))
        if problems:
            die("the message may or may not have been sent as written: %s. Check the "
                "conversation by hand before running this again." % "; ".join(problems))
        print(json.dumps({"kind": "message-sent", "with": header["name"],
                          "thread": br.page.url, "bubbles": len(msgs),
                          "chars": len(text)}, ensure_ascii=True))
        print("RESULT message-sent with=%r thread=%s bubbles=%d chars=%d"
              % (header["name"], br.page.url, len(msgs), len(text)))


def _open_target(br, pace, target):
    """A thread URL, a thread reference, or a profile URL. Returns the header."""
    t = (target or "").strip()
    if not t:
        die("message needs a thread URL, a thread_ref from read-inbox, or a profile URL")
    if is_ref(t) or S.THREAD_URL.search(t):
        return _open_thread(br, pace, t)
    if "/in/" not in t:
        die("message takes a profile URL, a thread URL containing /messaging/thread/<id>/, "
            "or a thread_ref that read-inbox printed. %r is none of them." % t[:80])
    # THE PROFILE ROUTE. The Message control's href is taken off the profile
    # itself rather than assembled here: it carries a urn this code has no other
    # way to know, and a hand-built compose URL that resolves to the wrong
    # person is exactly the mistake rule 0.3 exists against.
    pace.before_view("a profile, to find where its Message control points")
    br.read(t, "the profile the message is for", settle=6)
    pace.after_view()
    href = br.page.evaluate(
        "() => { const a = [...document.querySelectorAll('a[href*=\"/messaging/\"]')]"
        ".filter(e => (e.offsetParent || e.getClientRects().length)); "
        "return a.length ? a[0].getAttribute('href') : null; }")
    if not href:
        die("this profile's top card offers no Message control, so there is no conversation "
            "to compose in. Nothing was typed.")
    url = href if href.startswith("http") else "https://www.linkedin.com" + href
    pace.before_view("the conversation reached from that profile")
    br.read(url, "the conversation reached from the profile", settle=THREAD_SETTLE)
    pace.after_view()
    return _thread_header(br)


def _last_text(br):
    msgs = br.page.evaluate(MESSAGES_JS, _sel_thread())
    return msgs[-1]["text"] if msgs else None


def _norm(t):
    return re.sub(r"\s+", " ", t or "").strip()
