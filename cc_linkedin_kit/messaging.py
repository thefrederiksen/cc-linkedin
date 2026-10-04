# -*- coding: utf-8 -*-
"""Phase 3, `message`: one direct message to one person, staged by default.

    cc-linkedin message <profile URL | thread URL | thread_ref>
                        (--text "..." | --text-file f.txt) [--expect-name "Name"]
                        [--submit | --leave] [--shot out.png]

THIS REACHES A REAL PERSON AND CANNOT BE TAKEN BACK. Everything below follows
from that, and from a wrong-name DM that went to a real prospect on 2026-07-21.

THE RULES, EACH ONE ENFORCED HERE RATHER THAN HOPED FOR

  * STAGED BY DEFAULT. Without --submit the conversation is opened, the text is
    typed and read back, the screenshot is taken, and then the composer is
    CLEARED and proven empty, the bubble count is proven unchanged, and the
    conversation is reloaded to prove the last message is still the one that
    was last before we typed (design 4.3, rule 0.1). --leave stops before the
    clearing so the owner can press Send himself, and the RESULT line says so.
  * --submit REQUIRES --expect-name, and before Send is pressed the page itself
    must name that person as the one participant. A text that opens with a
    greeting ("Hi X", "Hey X", "Hello X") must greet the participant's first
    name. Either mismatch refuses, clears the composer, and sends nothing. The
    greeting check runs on staged runs too, so a wrong name shows up while it
    is still cheap.
  * NEVER ENTER. A line break is Shift+Enter, through this module's own typing
    path. `Browser.type_text` presses Enter once per newline and is never used
    here (design rule 0.2). The bubble count is read before typing and asserted
    unchanged after typing and again just before Send; if it rose, something
    has ALREADY gone, and the FAIL line says so in those words.
  * Nothing inside a conversation is touched except the composer and its Send
    button, each identified positively first (amendment A6). The quick-reply
    buttons send canned text in one click; nothing here can reach them. The
    "Open send options" menu is not opened either - see the measurement below.
  * One recipient per run. No list input, no loop. A conversation with more
    than one other participant is refused.
  * The composer must be empty before typing. A leftover draft that is exactly
    this text (a --leave run) is cleared and retyped; any other draft refuses,
    because it may be words the owner typed by hand.
  * PROOF OF SEND: after Send, the conversation is reloaded and must hold one
    more message from us whose text is this text, and the last message from us
    must be it. Only then is the RESULT line `sent`. A click with no such proof
    is a FAIL that says the message MAY have gone. If the last message from us
    already equals this text, nothing is typed: `already-sent`.
  * PACING: the send is an outbound action on pace.json's `message` line, with
    the 45-90 s gap and the daily cap of 30, like comment and react.

OPENING THE CONVERSATION MARKS IT READ, on every route, staged or not, and the
other person may be shown a read receipt. The RESULT line always carries
`marked_read=true`, as read-thread's does, and every FAIL after the open says
so too.

MEASURED ON THE LIVE PAGE, 2026-10-04 (tools/probe_thread_composer.py,
tools/probe_profile_message.py):

  * The composer, in a conversation AND on the compose route:
    div.msg-form__contenteditable[role=textbox][contenteditable=true],
    aria-label "Write a message...", inside form.msg-form. Empty, it holds
    exactly <p><br></p> (innerText "\\n").
  * Send: button.msg-form__send-button, type=submit, text "Send", DISABLED on an
    empty composer. That is the pre-flight check: Send enabled before we typed
    means the composer is not empty, whatever its text reads.
  * "Open send options" is button.msg-form__send-toggle. It opens two radios,
    "Press Enter to Send" and "Click Send". On this account "Click Send" was
    selected. It is NOT read by the verb, because reading it means clicking
    inside the conversation, and it does not matter: Shift+Enter is a line
    break in both modes, Enter is never pressed, and the bubble guard is what
    catches it if either of those is ever wrong.
  * The conversation's header: h2.msg-entity-lockup__entity-title holds the
    participant's name exactly; a.msg-thread__link-to-profile links to their
    /in/ profile and its text carries a presence line after the name.
  * A profile's Message control is an <a> in the top card whose href is
    /messaging/compose/?profileUrn=urn:li:fsd_profile:<id>&recipient=<id>&...
    THAT ROUTE IS NOT AN EMPTY DRAFT when a conversation already exists: it
    shows the whole conversation under a "New message" heading, with the
    recipient as ONE dismissible pill, button.artdeco-pill--dismiss whose
    aria-label is "Remove <Name>". So it is registered here on the CAPPED view
    line, whatever surface_kind says about the bare compose path - it can show
    somebody a read receipt. The pill is read and never clicked.
  * Our own messages: the sender's name is the signed-in member's, which the
    global navigation states as the alt text of img.global-nav__me-photo.
    Other people's carry .msg-s-event-listitem--other; ours are matched by the
    name, positively, not by that class's absence.

PUBLIC REPO. The output names a real person and quotes text meant for them. It
goes to stdout for the caller and is never pasted into a committed file.
"""
import io
import json
import re
import time
import unicodedata

from . import inbox as I
from . import people as P
from . import selectors as S
from .browser import Browser, Pace, log, die

EDITOR = "form.msg-form .msg-form__contenteditable[contenteditable=true]"
SEND = "form.msg-form button.msg-form__send-button"
HEADER = "h2.msg-entity-lockup__entity-title"
HEADER_LINK = "a.msg-thread__link-to-profile"
PILL = "button.artdeco-pill--dismiss[aria-label^='Remove ']"
ME_PHOTO = "img.global-nav__me-photo"
EVENT = "li.msg-s-message-list__event"
COMPOSE_PREFIX = "/messaging/compose/"
# NOT MEASURED - no InMail form has been seen. A subject field is what an InMail
# or a message request carries and a message to a connection does not, so its
# PRESENCE refuses. Its absence proves nothing; the 1st-degree badge is the proof.
SUBJECT = ("form.msg-form input[name*='subject' i], form.msg-form input[placeholder*='Subject'], "
           "form.msg-form input[aria-label*='Subject']")
PROFILE_URL = re.compile(r"^https://(?:[a-z]{2,3}\.|www\.)?linkedin\.com/in/[^/?#]+/?(?:[?#].*)?$")

# A greeting, and the rest of ITS OWN LINE: "Hi" then a blank line then
# "Thanks for..." greets nobody, and "Thanks" is not a name.
GREETING = re.compile(r"^\s*(hi|hey|hello)\b([^\n]*)", re.I)
# What may sit between the greeting and the name: any horizontal space,
# including a no-break space, and ordinary punctuation ("Hi, Anna").
GREETING_GAP = re.compile(r"^[\s,.!:;\-]*")
GREETING_WORD = re.compile(r"^[^\s,.!?:;]+")
# Words that follow a greeting and are not anybody's name.
NOT_A_NAME = frozenset({"there", "all", "everyone", "team"})
# Characters refused in a message: control and format characters (a BOM, a
# zero-width space, a direction mark) are invisible, and they defeat every
# comparison made here. Line breaks are allowed, and so are the zero-width
# joiner and the variation selector, which emoji are built from.
ALLOWED_INVISIBLE = frozenset({"\n", "\u200d", "\ufe0f"})

STATE_JS = r"""
(s) => {
  const t = e => e ? (e.innerText || '').replace(/\s+/g, ' ').trim() : '';
  const vis = e => !!(e && (e.offsetParent || e.getClientRects().length));
  const eds = [...document.querySelectorAll(s.editor)].filter(vis);
  const sends = [...document.querySelectorAll(s.send)].filter(vis);
  const ed = eds.length === 1 ? eds[0] : null;
  const paras = ed ? [...ed.children].map(p => p.tagName === 'P'
      ? (p.innerText || '').replace(/\n$/, '') : null) : [];
  const links = [...document.querySelectorAll(s.header_link)].filter(vis);
  const me = document.querySelector(s.me);
  return {
    subject: document.querySelectorAll(s.subject).length,
    url: location.href,
    editors: eds.length,
    sends: sends.length,
    send_disabled: sends.length === 1 ? sends[0].disabled : null,
    send_text: sends.length === 1 ? t(sends[0]) : null,
    editor_text: ed ? ed.innerText : null,
    editor_paras: paras,
    editor_html_len: ed ? ed.innerHTML.length : 0,
    header: t([...document.querySelectorAll(s.header)].filter(vis)[0]),
    header_links: links.map(a => a.getAttribute('href') || ''),
    pills: [...document.querySelectorAll(s.pill)].filter(vis)
        .map(b => (b.getAttribute('aria-label') || '').replace(/^Remove\s+/, '').trim()),
    events: document.querySelectorAll(s.event).length,
    me: me ? (me.getAttribute('alt') || '').trim() : '',
  };
}
"""


TYPING_JS = r"""
(s) => {
  const e = document.querySelector(s.editor);
  return {focused: !!e && document.activeElement === e,
          paras: e ? e.children.length : -1,
          events: document.querySelectorAll(s.event).length};
}
"""


# ---------------------------------------------------------------- pure helpers

def _clean(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _fold(s):
    """Case- and accent-folded, for comparing a greeting to a first name."""
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).casefold()


def load_text(text, text_file):
    """The message, exactly as it will be typed. Line endings become \\n and
    trailing whitespace on each line and at the ends is dropped, because the
    composer drops it too and the read-back would then never match."""
    if bool(text) == bool(text_file):
        die("give the message with exactly one of --text or --text-file")
    if text_file:
        try:
            # utf-8-sig: Windows PowerShell 5.1 writes a BOM by default, and a
            # BOM typed into a message is invisible and defeats the greeting check.
            with io.open(text_file, encoding="utf-8-sig") as f:
                raw = f.read()
        except OSError as exc:
            die("cannot read --text-file %s: %s" % (text_file, exc))
    else:
        raw = text
    raw = raw.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    bad = sorted({"U+%04X" % ord(c) for c in raw if c not in ALLOWED_INVISIBLE
                  and unicodedata.category(c) in ("Cc", "Cf")})
    if bad:
        die("the message holds invisible control or format characters (%s). They cannot be "
            "seen in a mockup and they defeat the checks made here; take them out."
            % ", ".join(bad))
    lines = [ln.rstrip() for ln in raw.split("\n")]
    out = "\n".join(lines).strip("\n")
    if not out.strip():
        die("the message is empty")
    return out


def lines_of(text):
    """The lines the composer is expected to hold, one per paragraph."""
    return text.split("\n")


def first_name(participant):
    """The participant's first name as the page prints it: the first word."""
    words = _clean(participant).split(" ")
    return words[0] if words and words[0] else ""


def greeting_problem(text, participant):
    """Why the greeting is wrong for this participant, or None.

    Only a text that OPENS with Hi/Hey/Hello and a word is checked. That word
    must be the participant's first name (case and accents folded). "Hi there"
    and friends greet nobody in particular and pass."""
    m = GREETING.match(text)
    if not m:
        return None
    rest = GREETING_GAP.sub("", m.group(2))
    if not rest.strip():
        return None
    w = GREETING_WORD.match(rest)
    said = w.group(0) if w else rest.strip()[:20]
    if _fold(said) in NOT_A_NAME:
        return None
    first = first_name(participant)
    if not first:
        return "the text greets %r and the page names no participant to check it against" % said
    if _fold(said) != _fold(first):
        return ("the text opens %r and this conversation is with %r, whose first name is %r. "
                "A greeting followed by words on the same line must name the participant; "
                "start 'Hi %s' or put the greeting on its own line"
                % (m.group(0).strip()[:40], participant, first, first))
    return None


def editor_is_empty(state):
    """Positively empty: one editor, holding nothing but whitespace, AND the
    page's own Send button disabled. Either alone can lie."""
    return (state["editors"] == 1 and not (state["editor_text"] or "").strip()
            and state["send_disabled"] is True)


def ours(messages, me):
    """The messages whose (carried) sender is the signed-in member."""
    return [m for m in messages if me and _clean(m.get("sender")) == _clean(me)]


def last_ours_text(messages, me):
    mine = ours(messages, me)
    return mine[-1]["text"] if mine else None


def same_text(a, b):
    """A bubble's text against ours. The bubble collapses whitespace and line
    breaks, so the comparison does too - and nothing more."""
    return _clean(a) == _clean(b) and bool(_clean(a))


def problem_in(msgs, me, who):
    """Why these messages cannot be attributed, or None (review defect 2).

    In a one-to-one conversation every message is from us or from them. A
    third name means the signed-in name and the name on our messages differ,
    and `ours` would then find nothing - so already-sent would never fire and
    a retry would send twice. Any such sender, and any message with no urn,
    refuses."""
    why = I.message_problem(msgs)
    if why:
        return why
    names = {_clean(me), _clean(who)}
    other = sorted({_clean(m.get("sender")) for m in msgs} - names)
    if other:
        return ("messages from %s, who is neither the signed-in member %r nor the participant "
                "%r" % (", ".join(repr(o) for o in other), me, who))
    nourn = sum(1 for m in msgs if not m.get("urn"))
    if nourn:
        return "%d message(s) carry no event urn" % nourn
    return None


def send_proof(before_msgs, after_msgs, me, text):
    """None when the reloaded conversation proves our text went, else why not.

    PRESENCE: the last message from us after the reload carries exactly this
    text AND an event urn that was not on the page before we typed - a NEW
    message, not an old one that happens to match. Counting matching texts
    instead would depend on how much history each load happened to bring in."""
    mine = ours(after_msgs, me)
    if not mine:
        return "the reloaded conversation shows no message from %r at all" % me
    last = mine[-1]
    if not same_text(last["text"], text):
        return ("the last message from us after the reload is %r, not this text"
                % _clean(last["text"])[:80])
    if not last.get("urn"):
        return "the last message from us carries no event urn, so it cannot be shown to be new"
    if last["urn"] in {m.get("urn") for m in before_msgs}:
        return ("the last message from us (%s) was already there before we typed; no new "
                "message from us is on the page" % last["urn"])
    return None


def classify_target(target):
    """('thread', url) | ('ref', ref) | ('profile', url), or die naming why."""
    t = (target or "").strip()
    if not t:
        die("no target: give a profile URL, a /messaging/thread/<id>/ URL, or a thread_ref")
    if t.startswith("http"):
        if I.THREAD_PATH.match(t) and I.is_conversation_url(t):
            return "thread", t
        if PROFILE_URL.match(t):
            return "profile", t
        die("%r is neither a /messaging/thread/<id>/ URL nor a /in/ profile URL" % t)
    if t.startswith(I.REF_PREFIX):
        try:
            return "ref", I.parse_ref(t)
        except ValueError as exc:
            die(str(exc))
    if re.match(r"^[A-Za-z0-9\-_%]+$", t):
        return "profile", "https://www.linkedin.com/in/%s/" % t.strip("/")
    die("%r is not a profile URL or slug, a thread URL, or a thread_ref" % t)


# ---------------------------------------------------------------- the run

OPENED = (" THE CONVERSATION WAS OPENED and is now marked read; the other person may "
          "have been shown a read receipt.")

# How far a run has got. Every failure is worded from this, so that a failure
# raised anywhere - here, in Pace, in Browser, in inbox - says what it left
# behind (review defect 3, 2026-10-04).
START, OPEN, TYPED, CLICKED, DONE = "start", "opened", "typed", "send-clicked", "done"


class Run(object):
    """One message to one conversation. Holds the page and the facts read off it."""

    def __init__(self, br, pace, shot=None):
        self.br = br
        self.page = br.page
        self.pace = pace
        self.shot = shot
        self.phase = START
        self.reported = False    # a FAIL line naming what was left behind is out
        self.url = None          # what to reload to see this conversation again
        self.via = None
        self.who = None
        self.me = None
        self.before = []         # the history read before typing, for every later comparison

    # -- failure paths -------------------------------------------------------

    def fail_shot(self):
        """<shot>.fail.png, when a shot was asked for and the page can still be
        captured. Best effort by design: it must never be the thing that hides
        the reason the run failed."""
        if not self.shot:
            return
        try:
            self.br.screenshot(self.shot + ".fail.png")
            log("failure screenshot %s.fail.png" % self.shot)
        except Exception:                                         # noqa: BLE001
            log("could not write %s.fail.png" % self.shot)

    def aftermath(self):
        """What this run has left behind, in words, from its phase. After the
        Send click it says the message MAY HAVE GONE; after typing it clears the
        composer and says whether that worked; after the open it says the
        conversation is read."""
        if self.phase == CLICKED:
            return (" Send WAS CLICKED, so the message MAY HAVE GONE to %s. Read the conversation "
                    "before trying again - a retry could send it twice.%s" % (self.who, OPENED))
        if self.phase == TYPED:
            # "Nothing was sent" is a claim, so it is checked, not assumed
            # (re-review defect 1): a line break that sent resets the editor,
            # and a focus that moved can have pressed a button.
            gone = self.new_since_before()
            cleared = self.clear_quietly()
            if cleared:
                self.phase = OPEN
            box = ("The composer was cleared and is empty." if cleared else
                   "THE COMPOSER COULD NOT BE PROVEN EMPTY - look at the browser before anyone "
                   "presses Send.")
            if gone is None:
                said = (" WHETHER ANYTHING WAS SENT COULD NOT BE CHECKED - the conversation "
                        "could not be re-read. Look at it before trying again.")
            elif [m for m in gone if not m.get("sender")
                  or _clean(m.get("sender")) != _clean(self.who)]:
                # Ours, or nobody's that can be named: a fragment may have gone.
                said = (" %d NEW MESSAGE(S) APPEARED SINCE TYPING BEGAN (%s). SOMETHING MAY HAVE "
                        "BEEN SENT to %s - look at the conversation now and tell the person."
                        % (len(gone), ", ".join(sorted({_clean(m.get("sender")) or "?"
                                                         for m in gone})), self.who))
            elif gone:
                said = (" Nothing from us was sent: the only new message(s) since typing began "
                        "are from %s." % self.who)
            else:
                said = " Nothing was sent: the conversation holds no message newer than before typing."
            return "%s %s%s" % (said, box, OPENED)
        if self.phase in (OPEN, DONE):
            return OPENED
        return " Nothing was opened."

    def new_since_before(self):
        """Messages on the page now whose urn was not there before typing, or
        None when the page cannot be read. Waits a moment first, so a send that
        is still landing is counted."""
        try:
            time.sleep(2)
            got = self.page.evaluate(I.MESSAGES_JS, {"thread_list": I.THREAD_LIST})
            if not got.get("found"):
                return None
            now = I.carry_senders(got.get("messages") or [])
        except Exception:                                         # noqa: BLE001
            return None
        old = {m.get("urn") for m in self.before}
        return [m for m in now if not m.get("urn") or m.get("urn") not in old]

    def fail(self, msg):
        """THE failure path for everything this module decides."""
        tail = self.aftermath()
        self.fail_shot()
        self.reported = True
        die(msg + tail)

    def foreign_exit(self):
        """Somebody else's die() ended the run - Pace at a cap, Browser at a
        security check, inbox refusing a ref. Its FAIL line is already out but
        knows nothing of this run, so a second line says what was left."""
        if self.reported or self.phase == START:
            return
        self.reported = True
        print("FAIL the step above stopped the message run." + _ascii_line(self.aftermath()),
              flush=True)

    # -- reading -------------------------------------------------------------

    def state(self):
        return self.page.evaluate(STATE_JS, {
            "editor": EDITOR, "send": SEND, "header": HEADER, "header_link": HEADER_LINK,
            "pill": PILL, "event": EVENT, "me": ME_PHOTO, "subject": SUBJECT})

    def history(self, me, who, where):
        """Every message in view, POSITIVELY read (review defect 1). An empty
        read passes nothing: every guard downstream - already-sent, the staged
        proof, the proof of send - would otherwise pass on an empty list.

        A conversation route must show a message list with messages in it. The
        compose route may hold NO history (a first message to a connection),
        and then says so; that is the one empty read allowed, and the RESULT
        line carries history=0 so nobody reads more into it."""
        try:
            self.page.locator(I.THREAD_LIST).first.wait_for(state="attached", timeout=15000)
        except Exception:                                         # noqa: BLE001
            pass
        time.sleep(1)
        got = self.page.evaluate(I.MESSAGES_JS, {"thread_list": I.THREAD_LIST})
        events = got.get("events", 0) if got.get("found") else 0
        if not got.get("found") or not got.get("messages"):
            # The ONE empty read allowed: the compose route, the message list
            # POSITIVELY present, and zero events in it (re-review defect 2).
            # A list that is not found at all is a selector that moved.
            if self.via == "profile" and got.get("found") and events == 0:
                return []
            self.fail("%s: the conversation shows no readable message list (%s found=%s, %d "
                      "events). An empty read is a broken selector far more often than an "
                      "empty conversation." % (where, I.THREAD_LIST, got.get("found"), events))
        msgs = I.carry_senders(got["messages"])
        # A window that opens mid-group carries no sender on its first messages.
        # Those are older than everything after them; their urns are kept (so an
        # old message can never pass as new) but they cannot be attributed.
        k = 0
        while k < len(msgs) and not msgs[k].get("sender"):
            k += 1
        why = problem_in(msgs[k:], me, who)
        if why:
            self.fail("%s: %s. Refusing rather than guess whose messages are whose." % (where, why))
        for m in msgs[:k]:
            m["sender"] = None
        return msgs

    def participant(self, st):
        """The ONE other person this conversation is with, read off the page.

        In a conversation: the header's name, AND exactly one profile link in
        the header. On the compose route: exactly one recipient pill. Anything
        else - a group, a blank header, two pills - is refused."""
        if COMPOSE_PREFIX in st["url"]:
            if len(st["pills"]) != 1:
                self.fail("the new-message draft names %d recipients (%s); this verb sends to "
                          "exactly one." % (len(st["pills"]), ", ".join(st["pills"]) or "none"))
            if st["subject"]:
                self.fail("the new-message form has a subject field, which is what an InMail "
                          "or a message request looks like, not a message to a connection. "
                          "Out of scope (design section 6).")
            return _clean(st["pills"][0])
        if not st["header"]:
            self.fail("the conversation names nobody: %s is empty." % HEADER)
        if len(st["header_links"]) != 1 or "/in/" not in st["header_links"][0]:
            self.fail("the conversation header carries %d profile link(s), not one. A group "
                      "conversation, or a header this was not measured on; refusing."
                      % len(st["header_links"]))
        return _clean(st["header"])

    # -- opening -------------------------------------------------------------

    def open_thread_url(self, url):
        self.pace.before_view("a conversation thread, for message (MARKS IT READ)")
        # Set BEFORE the navigation: once it starts, the conversation may be
        # read, and an error mid-load must not report "nothing was opened".
        self.phase = OPEN
        final = self.br.read(url, "the conversation", settle=6)
        self.pace.after_view()
        if I.thread_id(final) != I.thread_id(url):
            self.fail("asked for conversation %s and landed on %s."
                      % (I.thread_id(url), final.split("?")[0]))
        self.url, self.via = final.split("?")[0], "thread"

    def open_ref(self, ref):
        # The phase moves AT the row click, through inbox's hook (re-review
        # defect 3): a stale ref refused before any click says "Nothing was
        # opened" and nothing here contradicts it.
        def clicked():
            self.phase = OPEN
        I._open_from_ref(self.br, self.pace, ref, on_click=clicked)
        self.br.assert_signed_in("the conversation")
        self.url, self.via = self.page.url.split("?")[0], "ref"

    def open_profile(self, url, expect):
        """Profile -> its top card's own Message control -> that destination.

        Two views, both CAPPED: the profile is somebody else's, and the
        destination shows the conversation (see the module docstring)."""
        self.pace.before_view("a profile, for its Message control")
        final = self.br.read(url, "the profile", settle=7)
        self.pace.after_view()
        if "/in/" not in final:
            self.fail("asked for the profile %s and landed on %s." % (url, final))
        card = self.page.evaluate(P.TOPCARD_JS, [S.PROFILE_TOPCARD,
                                                 {"fill": S.PROFILE_PRIMARY_FILL}])
        if not card or not card.get("name"):
            self.fail("no profile top card with a name on %s (selector %s)."
                      % (final, S.PROFILE_TOPCARD))
        name = _clean(card["name"])
        if expect and not I.same_person(expect, name):
            self.fail("the profile's top card names %r, not %r. Refusing before opening any "
                      "conversation." % (name, expect))
        # A direct message is to a 1st-degree connection. Anything else behind a
        # Message link - an open profile, a Premium account - is InMail or a
        # message request, out of scope (review defect 7). PRESENCE of the
        # badge, read off the card; no badge refuses.
        degree = P._degree(card, name)
        if degree != "1st":
            self.fail("the top card for %r shows degree %r, not 1st. A direct message goes to a "
                      "1st-degree connection; anything else here would be InMail or a message "
                      "request." % (name, degree))
        # The top card's OWN Message link, by its destination. "Message top
        # connections" and the sticky header's copy are why this is not a
        # name match (survey section 2, trap 3): the href is the identity.
        hrefs = sorted({c["href"] for c in card["controls"]
                        if c["tag"] == "A" and _clean(c["text"]) == "Message"
                        and c["href"].startswith(COMPOSE_PREFIX + "?") and "profileUrn=" in c["href"]})
        if len(hrefs) != 1:
            self.fail("the top card for %r carries %d distinct Message destinations, not one."
                      % (name, len(hrefs)))
        dest = "https://www.linkedin.com" + hrefs[0]
        # CAPPED BY NAME, NOT BY surface_kind: the bare compose path is an empty
        # draft and uncapped, but WITH a recipient it shows the conversation.
        self.pace.before_view("the Message destination for %s (SHOWS THE CONVERSATION, "
                              "MARKS IT READ)" % name)
        self.phase = OPEN
        self.br.read(dest, "the conversation with %s" % name, settle=7)
        self.pace.after_view()
        self.url, self.via = dest, "profile"

    def shown_url(self):
        """The address for the RESULT line. A thread's id is the whole identity,
        so its query goes; the compose route's identity IS its query."""
        return self.url if self.via == "profile" else self.url.split("?")[0]

    def reload(self, why):
        self.pace.before_view("the conversation again, %s" % why)
        self.br.read(self.url, "the conversation", settle=7)
        self.pace.after_view()

    # -- the composer --------------------------------------------------------

    def wait_composer(self):
        try:
            self.page.locator(EDITOR).first.wait_for(state="visible", timeout=20000)
        except Exception:                                         # noqa: BLE001
            self.fail("no message composer (%s) appeared." % EDITOR)
        time.sleep(1)

    def typing_check(self, bubbles0, paras):
        """One reading taken after every keystroke group: the editor holds the
        focus, holds `paras` paragraphs, and the conversation holds bubbles0
        messages. Returns why not, or None."""
        got = self.page.evaluate(TYPING_JS, {"editor": EDITOR, "event": EVENT})
        # The bubble count FIRST: a line break that sent also resets the editor,
        # and the paragraph check must not be the one that names it.
        if got["events"] != bubbles0:
            return "BUBBLES:%d" % got["events"]
        if not got["focused"]:
            return "the message editor lost the focus while typing"
        if got["paras"] != paras:
            return "the editor holds %d paragraph(s) where %d were expected" % (got["paras"], paras)
        return None

    def type_message(self, text, bubbles0, before, me):
        """THE ONLY TYPING PATH IN THIS MODULE. insert_text per line, Shift+Enter
        between lines, and NOTHING ELSE: there is no code path here that presses
        Enter alone.

        Checked after EVERY line break, not once at the end (review defect 5):
        if Shift+Enter ever sends, or the focus ever leaves the editor, the run
        stops there - at most one fragment can have gone, not one per line."""
        ed = self.page.locator(EDITOR)
        if ed.count() != 1:
            self.fail("the page holds %d message editors (%s), not one." % (ed.count(), EDITOR))
        try:
            ed.first.click(timeout=15000)
        except Exception as exc:                                  # noqa: BLE001
            self.fail("the message editor could not be clicked, so nothing was typed (%s)."
                      % str(exc).splitlines()[0][:120])
        time.sleep(0.4)
        why = self.typing_check(bubbles0, 1)
        if why:
            self.fail("before typing: %s. Nothing was typed." % why.replace(
                "BUBBLES:", "the message count moved to "))
        self.phase = TYPED
        kb = self.page.keyboard
        for i, line in enumerate(lines_of(text)):
            if i:
                kb.press("Shift+Enter")
                time.sleep(0.25)
                why = self.typing_check(bubbles0, i + 1)
                if why:
                    self.stop_typing(why, bubbles0, before, me)
            if line:
                kb.insert_text(line)
        time.sleep(1.2)
        why = self.typing_check(bubbles0, len(lines_of(text)))
        if why:
            self.stop_typing(why, bubbles0, before, me)

    def stop_typing(self, why, bubbles0, before, me):
        if why.startswith("BUBBLES:"):
            self.bubble_rise(bubbles0, before, me, "while typing")
        self.fail("%s." % why)

    def bubble_rise(self, bubbles0, before, me, when):
        """The message count moved. Say WHOSE message it is (review defect 6):
        ours means a fragment HAS GONE; theirs means a message arrived. Either
        way the run stops, the composer is cleared, and nothing more is sent."""
        try:
            got = self.page.evaluate(I.MESSAGES_JS, {"thread_list": I.THREAD_LIST})
            now = I.carry_senders(got.get("messages") or [])
        except Exception:                                         # noqa: BLE001
            now = []
        old = {m.get("urn") for m in before}
        new = [m for m in now if m.get("urn") and m.get("urn") not in old]
        mine = [m for m in new if _clean(m.get("sender")) == _clean(me)]
        if mine or not new:
            self.fail("THE MESSAGE COUNT MOVED FROM %d %s, and %s. A line break may have become "
                      "a send."
                      % (bubbles0, when,
                         "%d new message(s) are OURS" % len(mine) if mine else
                         "the new message(s) could not be attributed"))
        self.fail("a new message from %s arrived %s (%d new). Refusing to send into a "
                  "conversation that moved; read it first."
                  % (", ".join(sorted({_clean(m.get("sender")) or "?" for m in new})), when,
                     len(new)))

    def clear_quietly(self):
        """Select everything in the editor and delete it. True only when the
        composer is then positively empty (text and the disabled Send agree)."""
        try:
            ed = self.page.locator(EDITOR)
            if ed.count() != 1:
                return False
            ed.first.click(timeout=8000)
            self.page.keyboard.press("Control+A")
            self.page.keyboard.press("Delete")
            time.sleep(1.2)
            return editor_is_empty(self.state())
        except Exception:                                         # noqa: BLE001
            return False


def _ascii_line(s):
    return str(s).encode("ascii", "replace").decode("ascii")


# ---------------------------------------------------------------- the verb

def message(a):
    t0 = time.time()
    text = load_text(a.text, a.text_file)
    kind, target = classify_target(a.target)
    expect = _clean(a.expect_name) if a.expect_name else None
    if a.submit and not expect:
        die("--submit needs --expect-name: an irreversible act names its target twice "
            "(design rule 0.3). Nothing was opened.")
    if a.submit and a.leave:
        die("--leave leaves the text typed for a person to send; --submit sends it. Pick one.")
    pace = Pace()
    if a.submit and pace.count("message") >= Pace.CAPS["message"]:
        die("daily cap reached for message (%d today, cap %d). Tomorrow. Nothing was opened."
            % (pace.count("message"), Pace.CAPS["message"]))

    with Browser(a.port) as br:
        run = Run(br, pace, a.shot)
        try:
            _message(a, br, run, pace, text, kind, target, expect, t0)
        except SystemExit:
            run.foreign_exit()
            raise
        except Exception as exc:                                  # noqa: BLE001
            # Never a bare traceback: the caller must be told what was left
            # behind, and a traceback says nothing of the kind.
            run.fail("unexpected error: %s: %s." % (type(exc).__name__,
                                                   str(exc).splitlines()[0][:160]))


def _message(a, br, run, pace, text, kind, target, expect, t0):
    if kind == "thread":
        run.open_thread_url(target)
    elif kind == "ref":
        run.open_ref(target)
    else:
        run.open_profile(target, expect)
    run.wait_composer()

    st = run.state()
    who = run.who = run.participant(st)
    me = _clean(st["me"])
    if not me:
        run.fail("the global navigation states no signed-in name (%s alt), so our own "
                 "messages cannot be told from theirs." % ME_PHOTO)
    if I.same_person(me, who):
        run.fail("this conversation's participant reads %r, which is the signed-in member."
                 % who)
    # A ref names a person; the conversation that opened must be that person
    # (review defect 8), whether or not --expect-name was given.
    if kind == "ref" and not I.same_person(target["p"], who):
        run.fail("the thread_ref names %r and the conversation that opened is with %r. "
                 "Refusing; nothing was typed." % (target["p"], who))
    if expect and not I.same_person(expect, who):
        run.fail("this conversation is with %r, not %r. Refusing; nothing was typed."
                 % (who, expect))
    bad = greeting_problem(text, who)
    if bad:
        run.fail("%s. Refusing; nothing was typed." % bad)

    before = run.before = run.history(me, who, "before typing")
    run.me = me
    log("conversation with %r (via %s), %d messages in view" % (who, run.via, len(before)))
    if same_text(last_ours_text(before, me), text):
        run.phase = DONE
        print("RESULT message already-sent participant=%s via=%s url=%s chars=%d "
              "marked_read=true seconds=%d"
              % (json.dumps(who), run.via, run.shown_url(), len(text), time.time() - t0))
        return

    # The run must be able to take its proving reload. Checked BEFORE typing,
    # so the view cap cannot stop a run between the Send click and its proof.
    if pace.count("view") + 1 > Pace.VIEW_CAP:
        run.fail("the daily view cap (%d) leaves no view for the reload that proves this "
                 "run. Tomorrow. Nothing was typed." % Pace.VIEW_CAP)

    # A FRESH COMPOSER. A leftover draft that is exactly this text came from
    # a --leave run and is cleared; anything else may be the owner's own
    # words and is not ours to delete.
    if not editor_is_empty(st):
        left = st["editor_text"] or ""
        if same_text(left, text):
            log("the composer still holds this same text (a --leave run); clearing it "
                "before typing")
            if not run.clear_quietly():
                run.fail("the composer holds this text from an earlier run and could not "
                         "be cleared.")
            st = run.state()
        else:
            run.fail("the composer already holds a draft of %d characters that is not this "
                     "text (Send disabled=%s). It may be words typed by hand; clear it in "
                     "the browser and run again. Nothing was typed."
                     % (len(left.strip()), st["send_disabled"]))
    bubbles0 = st["events"]

    run.type_message(text, bubbles0, before, me)
    st = run.state()
    if st["events"] != bubbles0:
        run.bubble_rise(bubbles0, before, me, "while typing")
    if st["editor_paras"] != lines_of(text):
        got = st["editor_paras"]
        run.fail("the composer reads back %d paragraph(s), not the %d lines typed; first "
                 "difference near %r." % (len(got), len(lines_of(text)),
                                          next((g for g, w in zip(got, lines_of(text)) if g != w),
                                               got[-1] if got else None)))
    if st["send_disabled"] is not False:
        run.fail("the composer holds the text but Send is not enabled (disabled=%r)."
                 % st["send_disabled"])
    log("typed %d chars in %d line(s); read back exactly; message count unchanged at %d"
        % (len(text), len(lines_of(text)), bubbles0))
    if a.shot:
        br.screenshot(a.shot)
        log("screenshot %s" % a.shot)

    if not a.submit:
        if a.leave:
            st = run.state()
            if st["events"] != bubbles0:
                run.bubble_rise(bubbles0, before, me, "after typing")
            # THE TAB STAYS OPEN, in front. Measured 2026-10-04: LinkedIn
            # keeps no draft once the tab closes, so the text being handed
            # over lives in this tab and nowhere else.
            br.keep_page = True
            br.page.bring_to_front()
            run.phase = DONE
            print("RESULT message staged left=true participant=%s via=%s url=%s chars=%d "
                  "lines=%d history=%d marked_read=true shot=%s seconds=%d note=%s"
                  % (json.dumps(who), run.via, run.shown_url(), len(text),
                     len(lines_of(text)), len(before), a.shot or "-", time.time() - t0,
                     json.dumps("THE TEXT IS LEFT TYPED, UNSENT, in a browser tab left open "
                                "for you. Pressing Send there sends it; closing that tab "
                                "discards it.")))
            return
        if not run.clear_quietly():
            run.fail("staged, and the composer could NOT be proven empty afterwards.")
        run.phase = OPEN
        st = run.state()
        if st["events"] != bubbles0:
            run.bubble_rise(bubbles0, before, me, "during a staged run")
        # Rule 0.1: a staged run PROVES nothing happened, after a reload.
        run.reload("to prove the staged run sent nothing")
        run.wait_composer()
        st = run.state()
        after = run.history(me, who, "after the staged run's reload")
        if before:
            last_before, last_after = before[-1]["urn"], (after[-1]["urn"] if after else None)
            if not last_before or last_after != last_before:
                run.fail("after the reload the last message is %r, not %r as before typing. "
                         "Something may have been SENT to %s." % (last_after, last_before, who))
            unchanged = "true"
        else:
            if after:
                run.fail("the conversation held no messages before typing and holds %d after "
                         "the reload. Something may have been SENT to %s." % (len(after), who))
            unchanged = "unproven-no-history"
        if not editor_is_empty(st):
            run.fail("after the reload the composer is not empty (LinkedIn kept a draft of %d "
                     "chars, Send disabled=%r). Nothing was sent; clear it in the browser."
                     % (len((st["editor_text"] or "").strip()), st["send_disabled"]))
        run.phase = DONE
        print("RESULT message staged left=false participant=%s via=%s url=%s chars=%d "
              "lines=%d history=%d cleared=true last_message_unchanged=%s "
              "marked_read=true shot=%s seconds=%d"
              % (json.dumps(who), run.via, run.shown_url(), len(text),
                 len(lines_of(text)), len(before), unchanged, a.shot or "-", time.time() - t0))
        return

    # ---- --submit. Wait out the outbound gap FIRST, then re-check
    # everything on the page, because the gap can be 90 seconds long.
    pace.before("message")
    st = run.state()
    if st["events"] != bubbles0:
        run.bubble_rise(bubbles0, before, me, "while waiting to send")
    who2 = run.participant(st)
    if not I.same_person(expect, who2):
        run.fail("just before Send the conversation reads %r, not %r." % (who2, expect))
    if st["editor_paras"] != lines_of(text):
        run.fail("just before Send the composer no longer holds exactly the text.")
    sends = br.page.locator(SEND)
    if (sends.count() != 1 or st["send_text"] != "Send"
            or st["send_disabled"] is not False):
        run.fail("Send is not one enabled button reading 'Send' (%d found, text %r, "
                 "disabled %r)." % (sends.count(), st["send_text"], st["send_disabled"]))
    # A hit-tested CLICK on the form's own Send button. Not Enter. The phase
    # moves FIRST: a click that raises may still have landed.
    run.phase = CLICKED
    sends.first.click(timeout=8000)
    pace.after("message")
    log("Send clicked")
    deadline = time.time() + 20
    while time.time() < deadline:
        if editor_is_empty(run.state()):
            break
        time.sleep(1)
    time.sleep(2)
    if I.is_conversation_url(br.page.url) and I.THREAD_PATH.match(br.page.url.split("?")[0]):
        run.url = br.page.url.split("?")[0]
    run.reload("to prove the message is there")
    after = run.history(me, who, "after Send, on the proving reload")
    why = send_proof(before, after, me, text)
    if why:
        run.fail("the send is not proven: %s." % why)
    sent = ours(after, me)[-1]
    run.phase = DONE
    print("RESULT message sent participant=%s via=%s url=%s urn=%s chars=%d lines=%d "
          "marked_read=true shot=%s seconds=%d"
          % (json.dumps(who), run.via, run.shown_url(), sent.get("urn") or "-",
             len(text), len(lines_of(text)), a.shot or "-", time.time() - t0))
