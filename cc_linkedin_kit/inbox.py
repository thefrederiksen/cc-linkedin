# -*- coding: utf-8 -*-
"""Phase 3, reading the owner's own messages: `read-inbox` and `read-thread`.

READ-INBOX MUST NOT OPEN A CONVERSATION. Opening one marks it read, and that is
a write dressed as a read: the unread signal is gone, and the other person can
be shown a read receipt. So the list is never reached through `/messaging/`,
which selects a conversation into its reading pane on load. It is reached
through `/messaging/compose/`, which renders the SAME list with the reading pane
holding an empty draft (survey section 4, 2026-09-10). Nothing here clicks a
conversation row, and the run proves it rather than promising it - see
`unread_regressions` and the `opened` / `marked_read` fields on the RESULT line.

READ-THREAD MARKS THE CONVERSATION READ. There is no way to read a thread
without opening it. The RESULT line says `marked_read=true`, always, because a
side effect nobody mentions is how a tool loses somebody's trust (design 4.5).

MEASURED ON THE LIVE PAGE (survey 2026-09-10; re-measured when this was built,
see the dated notes below):

  * The list: ul.msg-conversations-container__conversations-list, one
    li.msg-conversation-listitem per row, holding div.msg-conversation-card.
    Unread rows carried the extra class
    msg-conversation-card__convo-item-container--unread ON THE CARD on
    2026-09-10. ON 2026-10-03 THEY DID NOT: six unread rows under the Unread
    filter carried no such class, and the only marker was the per-row count
    below. A row is therefore unread if EITHER is present. Reading the class
    alone sees nothing unread, and the no-row-went-read proof then passes on an
    empty set - every run, forever.
  * Per row: .msg-conversation-card__participant-names (10 of 10),
    .msg-conversation-card__message-snippet (8 of 10 - TWO ROWS IN TEN HAVE
    NONE, so a parser that requires it drops a fifth of the inbox),
    time.msg-conversation-card__time-stamp (10 of 10). The per-row unread COUNT
    is an element whose aria-label reads "N unread message(s)".
  * ROWS HAVE NO HREF and carry no thread id in any attribute. The id first
    exists in the address bar after a row is opened. So `read-inbox` cannot
    return a thread URL without doing the thing it must not do (amendment A3);
    it returns a `thread_ref` instead, and `read-thread` accepts either.
  * The selected row is marked by msg-conversations-container__convo-item-link--active
    on its .msg-conversation-listitem__link. On the compose route NO row may
    carry it; that is asserted.
  * THE DEFAULT LIST IS NOT EVERY CONVERSATION. Measured 2026-10-03: the Unread
    filter listed nine unread conversations that the default list does not
    show at all, even at the position their date would give them - three dated
    Sep 28 are absent between its Sep 29 and Sep 23 rows. They live outside
    LinkedIn's main list (most likely its Other / message-request folder).
    The per-row unread label is the page's own, row by row - not a property of
    the filter - so `filter=all` means "the default list" and `--unread` can
    reach further than it does.
  * The Unread filter is button[data-test-messaging-inbox-filters__filter-pill=UNREAD]
    (aria-pressed flips to "true"; the address becomes /messaging/thread/new/?filter=unread,
    an empty draft - see NEW_DRAFT).
    `--unread` presses that rather than filtering rows itself, so the list the
    page calls unread is the list we report.
  * Inside a thread: one li.msg-s-message-list__event per message - NOT the
    children of .msg-s-message-list-content, which also holds a top marker, a
    loader, a typing indicator, a quick-reply row and a bottom marker (9 where
    the answer is 4). Each holds div.msg-s-event-listitem with data-event-urn;
    the sender is .msg-s-message-group__name and appears only on the first
    message of a group, so later messages in the group carry it forward;
    the text is .msg-s-event-listitem__body; a date boundary is
    time.msg-s-message-list__time-heading.
  * The thread ends with QUICK-REPLY BUTTONS that send canned text to a real
    person in ONE CLICK, no draft, no confirmation (amendment A6). Nothing in
    this module clicks anything inside a thread, and nothing presses a key on
    any messaging page. The only click in the whole module is the one that
    opens a conversation row in `read-thread`, on the row's own name element,
    after the row has been identified twice.

PACING. Every navigation that has a URL registers against pace.json through
`surface_kind`, the one place that decides which counter a URL belongs on. The
compose route is `view_self` (counted, uncapped: measured to open no
conversation). The Unread filter's draft address is `view_self` too, by the
owner's ruling of 2026-10-03 (docs/ruling-unread-draft-2026-10-03.md). A thread is `view`, CAPPED, because opening one
can show somebody else a read receipt. ONE choice is made here rather than
there: opening a thread FROM A ROW has no URL until after the click, so it is
registered with `before_view` by name - the capped counter, the direction that
cannot under-count.

PUBLIC REPO. This output names real people and quotes their messages. It goes to
stdout for the caller and is never pasted into a committed file.
"""
import base64
import json
import re
import time

from .browser import Browser, Pace, surface_kind, log, die

COMPOSE_URL = "https://www.linkedin.com/messaging/compose/"
# 2026-10-03, measured: pressing the Unread filter on the compose route moves
# the address to /messaging/thread/new/?filter=unread - still an empty draft,
# no reading pane, no conversation. "new" is not a conversation id, so a test
# for "/messaging/thread/" alone stops a clean run AND, worse, satisfies
# read-thread's wait for a conversation before any row was clicked.
NEW_DRAFT = re.compile(r"/messaging/thread/new/?(?:[?#]|$)")
THREAD_PATH = re.compile(r"^https://(?:[a-z]{2,3}\.|www\.)?linkedin\.com/messaging/thread/([^/?#]+)/?(?:[?#].*)?$")

UNREAD_MARK = "msg-conversation-card__convo-item-container--unread"
ACTIVE_MARK = "msg-conversations-container__convo-item-link--active"
CARD = ".msg-conversation-card"
NAMES = ".msg-conversation-card__participant-names"
UNREAD_PILL = "button[data-test-messaging-inbox-filters__filter-pill=UNREAD]"
THREAD_LIST = ".msg-s-message-list-content"
# The compose draft's own To field. A conversation has no recipient field, so
# this is the PRESENCE that says the reading pane holds a draft (review defect
# 2, 2026-10-03: the old check was three absences, two of them class names of
# the kind that vanished between 09-10 and 10-03).
DRAFT_FIELD = "input.msg-connections-typeahead__search-field"
UNREAD_PILL_URL = "https://www.linkedin.com/messaging/thread/new/?filter=unread"
THREAD_SCROLLS_MAX = 40

LIMIT_MAX = 100
REF_PREFIX = "tr1."

ROWS_JS = r"""
(s) => {
  const t = e => e ? (e.innerText || '').replace(/\s+/g, ' ').trim() : '';
  const cards = [...document.querySelectorAll(s.card)];
  return {
    url: location.href,
    thread_pane: !!document.querySelector(s.thread_list),
    draft: !!document.querySelector(s.draft),
    active: document.querySelectorAll('.' + s.active).length,
    rows: cards.map((c, i) => {
      const uc = c.querySelector('[aria-label*="unread message"]');
      const tm = c.querySelector('time');
      return {
        index: i,
        unread: c.className.indexOf(s.unread) >= 0 || !!uc,
        participant: t(c.querySelector(s.names)),
        last_line: t(c.querySelector('.msg-conversation-card__message-snippet')),
        when: t(c.querySelector('time.msg-conversation-card__time-stamp')) || t(tm),
        unread_label: uc ? uc.getAttribute('aria-label') || '' : '',
      };
    }),
  };
}
"""

SCROLL_LIST_JS = r"""
() => {
  // Scroll the conversation list's own scrolling ancestor. Never the window,
  // never focus, never a key: a scroll position changes nothing anyone sees.
  let e = document.querySelector('ul.msg-conversations-container__conversations-list');
  while (e) {
    const oy = getComputedStyle(e).overflowY;
    if (/(auto|scroll)/.test(oy) && e.scrollHeight > e.clientHeight) {
      e.scrollTop = e.scrollHeight;
      return true;
    }
    e = e.parentElement;
  }
  return false;
}
"""

PILL_JS = r"""
(sel) => {
  const b = document.querySelector(sel);
  return b ? {found: true, pressed: b.getAttribute('aria-pressed'),
              text: (b.innerText || '').trim()} : {found: false};
}
"""

MESSAGES_JS = r"""
(s) => {
  const t = e => e ? (e.innerText || '').replace(/\s+/g, ' ').trim() : '';
  const list = document.querySelector(s.thread_list);
  if (!list) return {found: false};
  let day = '';
  const out = [];
  for (const li of list.querySelectorAll('li.msg-s-message-list__event')) {
    const head = li.querySelector('time.msg-s-message-list__time-heading');
    if (head) day = t(head);
    for (const ev of li.querySelectorAll('.msg-s-event-listitem')) {
      const link = ev.querySelector('a.msg-s-event-listitem__link');
      out.push({
        urn: ev.getAttribute('data-event-urn') || '',
        sender: t(ev.querySelector('.msg-s-message-group__name')),
        sender_url: link ? (link.getAttribute('href') || '').split('?')[0] : '',
        time: t(ev.querySelector('time.msg-s-message-group__timestamp')),
        day: day,
        text: t(ev.querySelector('.msg-s-event-listitem__body')),
      });
    }
  }
  return {found: true, events: list.querySelectorAll('li.msg-s-message-list__event').length,
          messages: out};
}
"""

SCROLL_THREAD_UP_JS = r"""
(sel) => {
  let e = document.querySelector(sel);
  while (e) {
    const oy = getComputedStyle(e).overflowY;
    if (/(auto|scroll)/.test(oy) && e.scrollHeight > e.clientHeight) {
      e.scrollTop = 0;
      return true;
    }
    e = e.parentElement;
  }
  return false;
}
"""

HEADER_JS = r"""
(s) => {
  const t = e => e ? (e.innerText || '').replace(/\s+/g, ' ').trim() : '';
  const h = document.querySelector('.msg-entity-lockup__entity-title, h2.msg-overlay-bubble-header__title, .msg-thread__link-to-profile');
  // The selected row in the list names the open conversation too. Read both;
  // either one agreeing with the row that was clicked is the check.
  const act = document.querySelector('.' + s.active);
  const card = act ? act.closest(s.card) : null;
  return {header: t(h), active_row: card ? t(card.querySelector(s.names)) : ''};
}
"""


# ---------------------------------------------------------------- pure helpers

def is_conversation_url(url):
    """True for a real /messaging/thread/<id>/ address; False for the compose
    route and for the /messaging/thread/new/ draft the Unread filter lands on."""
    u = (url or "").split("#")[0]
    return "/messaging/thread/" in u and not NEW_DRAFT.search(u)


def _clean(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def unread_count(label):
    """'3 unread messages' -> 3. None when the row states no count."""
    m = re.search(r"(\d+)\s+unread message", label or "")
    return int(m.group(1)) if m else None


def row_key(row):
    """What identifies a row across two reads of the same list. Position is
    deliberately NOT part of it: a new message moves a row to the top."""
    return (_clean(row.get("participant")), _clean(row.get("when")))


def thread_id(url):
    m = THREAD_PATH.match((url or "").strip())
    return m.group(1) if m else None


def first_sight(snapshots):
    """Every row as it was the FIRST time this run saw it, across all the
    snapshots in order (review defect 1, 2026-10-03). The baseline for the
    no-row-went-read proof has to be taken BEFORE anything that could open a
    row: a baseline taken after the scrolls records an opened row as read and
    then finds nothing changed. Duplicate keys stay duplicates: the k-th copy
    of a key is first seen in the first snapshot that holds k of them."""
    seen = {}
    out = []
    for rows in snapshots:
        here = {}
        for r in rows:
            here.setdefault(row_key(r), []).append(r)
        for k, rs in here.items():
            have = seen.get(k, 0)
            if len(rs) > have:
                out.extend(rs[have:])
                seen[k] = len(rs)
    return out


def message_problem(msgs):
    """Why a thread read cannot be passed as a read, or None (rule 4: an empty
    read is a failure). A body selector that moved gives every message an
    empty text and still counts twenty of them."""
    if not msgs:
        return "no messages"
    if not any(m.get("text") for m in msgs):
        return ("%d messages and NOT ONE carries text: the body selector "
                ".msg-s-event-listitem__body has moved" % len(msgs))
    blank = [m for m in msgs if not m.get("sender")]
    if blank:
        return ("%d of %d messages carry no sender; a message nobody can attribute is "
                "a parse failure, not a message" % (len(blank), len(msgs)))
    return None


def same_person(expect, seen):
    """The name on the row that was clicked, against a name the open
    conversation shows. EXACT after whitespace, never a substring: 'Ann' is
    inside 'Joanne'."""
    return bool(_clean(expect)) and _clean(expect) == _clean(seen)


def unread_regressions(before, after):
    """The rows that were unread at the start of a run and are read at the end.

    This is the proof that `read-inbox` opened nothing. It is a PRESENCE test
    on the before side: a row has to have been SEEN unread to count, and then
    SEEN again, read. A row missing from the second read is not counted here -
    `unread_lost` returns those, and the caller fails on them too, so a vanished
    row can never pass as a clean one.
    """
    now = {}
    for r in after:
        now.setdefault(row_key(r), []).append(bool(r.get("unread")))
    was = {}
    for r in before:
        if r.get("unread"):
            was.setdefault(row_key(r), []).append(r)
    went_read = []
    for k, rows in was.items():
        seen = now.get(k)
        if not seen:
            continue
        # Counted per key, so of two rows sharing a name and a time, one going
        # read is caught too (review, 2026-10-03).
        short = len(rows) - sum(seen)
        if short > 0:
            went_read.extend(rows[:short])
    return went_read


def unread_lost(before, after):
    """Rows unread at the start that the second read did not see at all."""
    keys = {row_key(r) for r in after}
    return [r for r in before if r.get("unread") and row_key(r) not in keys]


def make_ref(row, filt):
    """An opaque handle for one row (amendment A3). Built only from what the row
    carries: who, when, where it sat, and under which filter. NOT a URL."""
    body = {"p": _clean(row["participant"]), "w": _clean(row["when"]),
            "i": int(row["index"]), "f": filt}
    raw = json.dumps(body, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    return REF_PREFIX + base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def parse_ref(ref):
    """The dict make_ref encoded, or raise ValueError naming what is wrong."""
    ref = (ref or "").strip()
    if not ref.startswith(REF_PREFIX):
        raise ValueError("not a thread_ref (it does not start %r) and not a "
                         "/messaging/thread/ URL" % REF_PREFIX)
    b = ref[len(REF_PREFIX):]
    try:
        body = json.loads(base64.urlsafe_b64decode(b + "=" * (-len(b) % 4)).decode("ascii"))
    except Exception:
        raise ValueError("thread_ref is damaged: it does not decode")
    if (not isinstance(body, dict) or not body.get("p") or "w" not in body
            or not isinstance(body.get("i"), int) or body.get("f") not in ("all", "unread")):
        raise ValueError("thread_ref is damaged: fields missing")
    return body


def match_ref(rows, ref):
    """Index of the ONE row this ref names, or (None, why).

    Who and when must both agree. Position only breaks a tie between rows that
    agree on both - and if it cannot, the run refuses rather than guess, because
    the wrong guess opens a stranger's conversation and marks it read."""
    hits = [r for r in rows if _clean(r["participant"]) == ref["p"]
            and _clean(r["when"]) == ref["w"]]
    if len(hits) == 1:
        return hits[0]["index"], None
    if not hits:
        same = [r for r in rows if _clean(r["participant"]) == ref["p"]]
        if same:
            return None, ("the row for %r now reads %r, not %r - a newer message has "
                          "arrived or the time has rolled over. Run read-inbox again for "
                          "a fresh thread_ref" % (ref["p"], _clean(same[0]["when"]), ref["w"]))
        return None, ("no row in the %d read carries %r. Run read-inbox again for a "
                      "fresh thread_ref" % (len(rows), ref["p"]))
    for r in hits:
        if r["index"] == ref["i"]:
            return r["index"], None
    return None, ("%d rows read %r at %r and none sits at position %d any more; "
                  "refusing to guess which" % (len(hits), ref["p"], ref["w"], ref["i"]))


def carry_senders(messages):
    """A sender's name is printed on the first message of a group only. Carry it
    forward, and say which ones were carried, rather than print a blank."""
    last = None
    out = []
    for m in messages:
        m = dict(m)
        if m.get("sender"):
            last = (m["sender"], m.get("sender_url"))
            m["sender_carried"] = False
        elif last:
            m["sender"], m["sender_url"] = last[0], m.get("sender_url") or last[1]
            m["sender_carried"] = True
        else:
            m["sender_carried"] = False
        out.append(m)
    return out


# ---------------------------------------------------------------- the list

def _register(pace, url, what):
    """One navigation, on the counter surface_kind gives it. Written out with
    both branches visible at the call site, as in tools/survey.py."""
    if surface_kind(url) == "view_self":
        pace.before_self_view(what + " (a surface that opens no conversation)")
    else:
        pace.before_view(what)


def _read_rows(br):
    return br.page.evaluate(ROWS_JS, {"card": CARD, "names": NAMES, "unread": UNREAD_MARK,
                                      "active": ACTIVE_MARK, "thread_list": THREAD_LIST,
                                      "draft": DRAFT_FIELD})


def _on_draft_route(url):
    path = (url or "").split("#")[0]
    return "/messaging/compose" in path or bool(NEW_DRAFT.search(path))


def _assert_nothing_open(snap, where):
    """The reading pane must POSITIVELY hold an empty draft: the address is the
    compose route or the /thread/new/ draft, AND the draft's To field is on the
    page (review defect 2). The absences - no conversation pane, no selected
    row - are still checked, but the pass no longer rests on them."""
    if not _on_draft_route(snap["url"]):
        die("%s: the browser is on %s, which is neither the compose route nor the new-"
            "message draft. A conversation may have been opened and marked read. Stopping."
            % (where, snap["url"].split("?")[0]))
    if not snap["draft"]:
        die("%s: the draft's recipient field (%s) is not on the page, so nothing proves "
            "the reading pane holds a draft rather than a conversation. Stopping."
            % (where, DRAFT_FIELD))
    if is_conversation_url(snap["url"]):
        die("%s: the browser is on a conversation (%s), so one was OPENED and is now "
            "marked read. Stopping." % (where, snap["url"].split("?")[0]))
    if snap["thread_pane"]:
        die("%s: the reading pane is showing a conversation, so one was opened and is "
            "now marked read. Stopping." % where)
    if snap["active"]:
        die("%s: %d conversation row(s) are marked selected; reading from here could "
            "open one. Stopping." % (where, snap["active"]))


def _open_list(br, pace, unread_only):
    """Load the conversation list without opening a conversation. Returns the
    latest snapshot and the list of every snapshot's rows, in order."""
    _register(pace, COMPOSE_URL, "the conversation list, via the compose route")
    final = br.read(COMPOSE_URL, "the conversation list", settle=6)
    pace.after_view()
    if "/messaging/compose" not in final:
        die("asked for %s and landed on %s" % (COMPOSE_URL, final))
    snap = _read_rows(br)
    _assert_nothing_open(snap, "after loading the list")
    snaps = [snap["rows"]]
    if unread_only:
        pill = br.page.evaluate(PILL_JS, UNREAD_PILL)
        if not pill["found"]:
            die("--unread asked for the page's own Unread filter and there is no %s on "
                "the list. Not filtering by hand: the page's notion of unread is the one "
                "being reported." % UNREAD_PILL)
        if pill["pressed"] != "true":
            # A FILTER PILL IN THE LIST HEADER, NOT ANYTHING INSIDE A THREAD.
            # Identified by its data-test attribute, then hit-tested. It MOVES
            # THE ADDRESS (measured 2026-10-03, to UNREAD_PILL_URL), so it is a
            # navigation and is registered as one, on whatever counter
            # surface_kind gives that address - view_self since the owner's
            # ruling of 2026-10-03, decided THERE and not here (review defect 8).
            _register(pace, UNREAD_PILL_URL, "the Unread filter of the conversation list")
            br.page.locator(UNREAD_PILL).first.click(timeout=8000)
            time.sleep(4)
            pace.after_view()
        pill = br.page.evaluate(PILL_JS, UNREAD_PILL)
        if pill["pressed"] != "true":
            die("pressed the Unread filter and it reads aria-pressed=%r, not 'true'. The "
                "list on screen is not the unread list." % pill["pressed"])
        snap = _read_rows(br)
        _assert_nothing_open(snap, "after pressing the Unread filter")
        snaps.append(snap["rows"])
    return snap, snaps


def _load_rows(br, want, first, snaps):
    """Scroll the list until it holds `want` rows or stops growing. Every
    snapshot goes onto `snaps`, so first_sight sees each row as it was when it
    first appeared."""
    snap = first
    stalls = 0
    while len(snap["rows"]) < want and stalls < 3:
        n = len(snap["rows"])
        if not br.page.evaluate(SCROLL_LIST_JS):
            break
        time.sleep(2.5)
        snap = _read_rows(br)
        _assert_nothing_open(snap, "after scrolling the list")
        snaps.append(snap["rows"])
        stalls = stalls + 1 if len(snap["rows"]) <= n else 0
    return snap


def read_inbox(a):
    limit = 20 if a.limit is None else int(a.limit)
    if limit < 1:
        die("--limit must be at least 1")
    if limit > LIMIT_MAX:
        die("--limit is capped at %d" % LIMIT_MAX)
    filt = "unread" if a.unread else "all"
    t0 = time.time()
    pace = Pace()
    with Browser(a.port) as br:
        first, snaps = _open_list(br, pace, a.unread)
        snap = _load_rows(br, limit, first, snaps)
        rows = snap["rows"]
        if not rows:
            die("no conversations on the %s list at %s. Zero rows is a broken selector far "
                "more often than an empty inbox, so this is a failure and not an empty list "
                "(the row selector is %s)." % (filt, snap["url"], CARD))
        nameless = [r for r in rows if not r["participant"] or not r["when"]]
        if nameless:
            die("%d of %d rows carry no participant or no time (selectors %s and "
                "time.msg-conversation-card__time-stamp). A row nobody can name is a "
                "parse failure, not a conversation." % (len(nameless), len(rows), NAMES))
        if not any(r["last_line"] for r in rows):
            die("%d rows and NOT ONE carries a message snippet (.msg-conversation-card__"
                "message-snippet). Two rows in ten have none; every row having none is a "
                "selector that moved." % len(rows))
        if a.unread and not all(r["unread"] for r in rows[:limit]):
            die("the Unread filter is pressed but %d row(s) on it lack the unread marker "
                "(the class %r or an 'N unread message' label). The marker has moved, so "
                "the unread column cannot be trusted."
                % (sum(1 for r in rows[:limit] if not r["unread"]), UNREAD_MARK))

        # THE PROOF NOTHING WAS OPENED: every row as it was when the run FIRST
        # saw it - including before the Unread filter was pressed - against the
        # same list read again at the end (review defect 1).
        base = first_sight(snaps)
        time.sleep(2)
        last = _read_rows(br)
        _assert_nothing_open(last, "at the end of the run")
        went = unread_regressions(base, last["rows"])
        if went:
            die("%d conversation(s) were unread when this run started and are READ now: %s. "
                "Something opened them. Stop and find out what before running this again."
                % (len(went), ", ".join(r["participant"] for r in went)))
        # A row that was unread and is now simply GONE is not a pass. Under the
        # Unread filter that is exactly what reading one looks like: it leaves
        # the list instead of changing class.
        lost = unread_lost(base, last["rows"])
        if lost:
            die("%d conversation(s) unread when this run started are not on the list at "
                "the end: %s. That is what an opened conversation looks like under the "
                "Unread filter, so it cannot be passed as clean."
                % (len(lost), ", ".join(r["participant"] for r in lost)))

        out = rows[:limit]
        for rank, r in enumerate(out, 1):
            rec = {"kind": "conversation", "rank": rank,
                   "participant": r["participant"],
                   "last_line": r["last_line"] or None,
                   "when": r["when"], "unread": bool(r["unread"]),
                   "unread_count": unread_count(r["unread_label"]),
                   "thread_ref": make_ref(r, filt)}
            print(json.dumps(rec, ensure_ascii=True))
        # With no unread row in view the comparison had nothing to compare, and
        # "marked_read=0" would be a claim resting on an empty set (review
        # defect 3). The line says so instead.
        rechecked = sum(1 for r in base if r["unread"])
        print("RESULT inbox rows=%d unread=%d filter=%s opened=0 marked_read=%s "
              "unread_rechecked=%d seconds=%d"
              % (len(out), sum(1 for r in out if r["unread"]), filt,
                 "0" if rechecked else "unproven-no-unread-row-in-view", rechecked,
                 time.time() - t0))


# ---------------------------------------------------------------- one thread

OPENED = (" THE CONVERSATION WAS OPENED and is now marked read; the other person may "
          "have been shown a read receipt.")


def die_opened(msg):
    """A failure AFTER a conversation was opened. There is no RESULT line on
    this path, so the side effect is said here or nowhere (review defect 9)."""
    die(msg + OPENED)


def _open_from_ref(br, pace, ref):
    """Find the row the ref names and open it. Returns (was_unread, participant).

    THE ORDER IS THE GUARD (review defect 4). The capped view is reserved - and
    its 3-8 s pacing wait sits - BEFORE the row is matched. Matching, the second
    identification and the click then run back to back on ONE pinned element
    handle with no sleep between them, so a message that arrives and shifts the
    rows cannot slide another person under the click."""
    first, snaps = _open_list(br, pace, ref["f"] == "unread")
    _load_rows(br, ref["i"] + 1, first, snaps)
    pace.before_view("a conversation thread, opened from its row (MARKS IT READ)")
    snap = _read_rows(br)
    _assert_nothing_open(snap, "before opening the row")
    idx, why = match_ref(snap["rows"], ref)
    if idx is None:
        die("thread_ref does not resolve: %s. Nothing was opened." % why)
    row = snap["rows"][idx]
    handle = br.page.locator(CARD).nth(idx).locator(NAMES).first.element_handle(timeout=5000)
    got = _clean(handle.inner_text())
    if got != ref["p"]:
        die("row %d names %r on the element about to be clicked, not %r. Refusing; "
            "nothing was opened." % (idx, got, ref["p"]))
    handle.click(timeout=8000)
    deadline = time.time() + 20
    while time.time() < deadline and not is_conversation_url(br.page.url):
        time.sleep(0.5)
    pace.after_view()
    if not is_conversation_url(br.page.url):
        die("clicked the row for %r and the browser is on %s, not a conversation. It may "
            "still have been marked read." % (ref["p"], br.page.url))
    return bool(row["unread"]), ref["p"]


def read_thread(a):
    target = (a.target or "").strip()
    t0 = time.time()
    pace = Pace()
    url = None
    ref = None
    if target.startswith("http"):
        if not THREAD_PATH.match(target) or not is_conversation_url(target):
            die("%r is not a /messaging/thread/<id>/ URL. read-thread takes a thread URL or "
                "a thread_ref from read-inbox." % target)
        url = target
    else:
        try:
            ref = parse_ref(target)
        except ValueError as exc:
            die(str(exc))

    with Browser(a.port) as br:
        if url:
            _register(pace, url, "a conversation thread (MARKS IT READ)")
            final = br.read(url, "the conversation", settle=6)
            pace.after_view()
            # The SAME conversation, by id - not merely "a conversation". A stale
            # or mistyped id that LinkedIn redirects elsewhere would otherwise
            # mark a different one read and print it under a normal RESULT line
            # (review defect 6).
            if thread_id(final) != thread_id(url):
                die_opened("asked for conversation %s and landed on %s."
                           % (thread_id(url), final.split("?")[0]))
            was_unread, expect = None, None
        else:
            was_unread, expect = _open_from_ref(br, pace, ref)
            br.assert_signed_in("the conversation")

        try:
            br.page.locator(THREAD_LIST).first.wait_for(state="attached", timeout=20000)
        except Exception:
            die_opened("the conversation at %s shows no message list (%s)."
                       % (br.page.url.split("?")[0], THREAD_LIST))
        time.sleep(2)

        def messages():
            got = br.page.evaluate(MESSAGES_JS, {"thread_list": THREAD_LIST})
            if not got.get("found"):
                die_opened("the message list %s disappeared while it was being read."
                           % THREAD_LIST)
            return got

        # Older messages load when the list is scrolled to the top. Scroll -
        # never a key - until the count stops growing, and no further than
        # THREAD_SCROLLS_MAX; `complete` on the RESULT line says which.
        got = messages()
        stalls = 0
        scrolls = 0
        while (stalls < 2 and scrolls < THREAD_SCROLLS_MAX
               and br.page.evaluate(SCROLL_THREAD_UP_JS, THREAD_LIST)):
            n = len(got["messages"])
            time.sleep(2.5)
            got = messages()
            scrolls += 1
            stalls = stalls + 1 if len(got["messages"]) <= n else 0
        complete = scrolls < THREAD_SCROLLS_MAX or stalls >= 2

        msgs = carry_senders(got["messages"])
        why = message_problem(msgs)
        if why:
            die_opened("the conversation at %s cannot be passed as a read (%d events): %s."
                       % (br.page.url.split("?")[0], got.get("events", 0), why))

        # WHO IS THIS CONVERSATION WITH. Opened from a ref, it must positively
        # be the person whose row was clicked, by the header or by the selected
        # row - an empty header is a FAIL, not a skipped check (review defect 5).
        seen = br.page.evaluate(HEADER_JS, {"active": ACTIVE_MARK, "card": CARD,
                                            "names": NAMES})
        if expect and not (same_person(expect, seen["header"])
                           or same_person(expect, seen["active_row"])):
            die_opened("opened the row for %r, and the conversation shows header %r and "
                       "selected row %r. Neither is that person."
                       % (expect, seen["header"], seen["active_row"]))
        # Measured 2026-10-03: the header's text carries LinkedIn's presence
        # line after the name ("... Status is online Active now"). The name
        # the caller gets is the row's, where a row was matched.
        header = expect or re.sub(r"\s*Status is .*$", "",
                                  _clean(seen["header"]) or _clean(seen["active_row"]))
        if not header:
            die_opened("the conversation names nobody: no header and no selected row.")

        thread_url = br.page.url.split("?")[0]
        for i, m in enumerate(msgs, 1):
            rec = {"kind": "message", "rank": i, "sender": m["sender"],
                   "sender_url": (("https://www.linkedin.com" + m["sender_url"])
                                  if (m["sender_url"] or "").startswith("/")
                                  else m["sender_url"]) or None,
                   "sender_carried": m["sender_carried"],
                   "day": m["day"] or None, "time": m["time"] or None,
                   "text": m["text"], "urn": m["urn"] or None}
            print(json.dumps(rec, ensure_ascii=True))
        print("RESULT thread messages=%d complete=%s participant=%s url=%s marked_read=true "
              "was_unread=%s seconds=%d"
              % (len(msgs), str(complete).lower(), json.dumps(header), thread_url,
                 "unknown" if was_unread is None else str(was_unread).lower(),
                 time.time() - t0))
