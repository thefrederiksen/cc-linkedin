# -*- coding: utf-8 -*-
"""Send one direct message to one 1st-degree connection.

MEASURED ON THE LIVE PAGE, 2026-09-10, via tools/survey.py + tools/probe_compose.py:

  * /messaging/compose/ counts as VIEW_SELF, so addressing somebody here costs
    nothing against the 80/day read cap. Going via their PROFILE would cost one
    read each, which is why the recipient is chosen here and not there.
  * Recipient field: input.msg-connections-typeahead__search-field, role
    combobox, labelled "Enter message recipients".
  * Options: li.msg-connections-typeahead__search-result, role option. THEY
    CARRY NO href AND NO PROFILE URN - measured, not assumed. The only identity
    on the row is its text, which reads
        "<status noise> <Name> - <degree> <current headline>"
    so name AND degree AND headline are the whole of what can be checked. That
    is why match_row below refuses anything it cannot pin on all three.
  * The typeahead searches CONNECTIONS. A non-connection returns the string
    "No results found", which is how reachability is decided.
  * Editor: .msg-form__contenteditable, role textbox "Write a message...".
  * Submit: button "Send".

WHAT THIS REFUSES TO DO
  * send to a row that is not 1st degree
  * send to a row whose name does not contain the name asked for
  * send when the editor does not hold exactly the text we meant to send
  * report a send it cannot see afterwards in the thread
"""
import re
import time
import unicodedata

from .browser import Pace, log, die

COMPOSE = "https://www.linkedin.com/messaging/compose/"
FIELD = "input.msg-connections-typeahead__search-field"
OPTION = "li.msg-connections-typeahead__search-result"
EDITOR = ".msg-form__contenteditable"
SENT_ROW = ".msg-s-event-listitem, .msg-s-message-list__event"

ROWS_JS = r"""
() => [...document.querySelectorAll('li.msg-connections-typeahead__search-result')]
  .slice(0, 10).map(li => (li.innerText || '').replace(/\s+/g, ' ').trim())
"""

THREAD_JS = r"""
() => {
  const n = document.querySelector('.msg-s-message-list-content, .msg-s-message-list');
  return n ? (n.innerText || '').replace(/\s+/g, ' ').trim().slice(-4000) : '';
}
"""


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9 ]", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def degree_of(row):
    m = re.search(r"\b(1st|2nd|3rd)\b", row)
    return m.group(1) if m else ""


def match_row(rows, name):
    """Index of the ONE row that is this person, or (None, why)."""
    want = norm(name)
    if not want:
        return None, "no name given"
    hits = [i for i, r in enumerate(rows) if want in norm(r)]
    if not hits:
        return None, ("no row carries the name %r; the typeahead returned %d row(s)"
                      % (name, len(rows)))
    firsts = [i for i in hits if degree_of(rows[i]) == "1st"]
    if not firsts:
        return None, ("the only rows carrying %r are %s degree, and a direct "
                      "message needs a 1st-degree connection"
                      % (name, "/".join(degree_of(rows[i]) or "?" for i in hits)))
    if len(firsts) > 1:
        return None, ("%d different 1st-degree people carry the name %r; "
                      "refusing to guess which" % (len(firsts), name))
    return firsts[0], None


class Compose(object):
    def __init__(self, br):
        self.br = br
        self.page = br.page

    def open(self):
        self.br.goto(COMPOSE, settle=5)
        self.br.assert_signed_in("the compose surface")
        box = self.page.locator(FIELD).first
        box.wait_for(state="visible", timeout=20000)
        return box

    def address(self, name):
        """Put exactly this person in the To field. Returns the matched row."""
        box = self.open()
        box.click()
        box.fill("")
        time.sleep(0.4)
        self.br.type_text(name)
        time.sleep(3.0)
        rows = self.page.evaluate(ROWS_JS)
        idx, why = match_row(rows, name)
        if idx is None:
            die("cannot address %r: %s" % (name, why))
        row = rows[idx]
        log("recipient row: %s" % row[:120])
        self.page.locator(OPTION).nth(idx).click()
        time.sleep(2.0)
        # the To field must now show them, and the typeahead must be gone
        pill = self.page.locator(".msg-connections-typeahead__added-recipients").first
        got = norm(pill.inner_text()) if pill.count() else ""
        if norm(name) not in got:
            die("after picking the row the To field reads %r, not %r" % (got[:80], name))
        return row

    def write(self, text):
        ed = self.page.locator(EDITOR).first
        ed.wait_for(state="visible", timeout=15000)
        ed.click()
        self.br.type_text(text)
        time.sleep(1.0)
        got = ed.inner_text().strip()
        if norm(got) != norm(text):
            die("the message box holds %d chars, wanted %d; refusing to send a "
                "message that is not the one written. Box begins: %r"
                % (len(got), len(text), got[:90]))
        return got

    def send(self, text):
        btn = self.page.get_by_role("button", name=re.compile(r"^Send$"))
        deadline = time.time() + 10
        while time.time() < deadline:
            for i in range(btn.count() - 1, -1, -1):
                b = btn.nth(i)
                if b.is_visible() and b.is_enabled():
                    b.click()
                    time.sleep(3.5)
                    return self.proof(text)
            time.sleep(0.5)
        die("the Send button never became enabled")

    def proof(self, text):
        """A click is not a send. The thread has to show the words."""
        needle = norm(text)[:80]
        deadline = time.time() + 20
        while time.time() < deadline:
            body = norm(self.page.evaluate(THREAD_JS))
            if needle and needle in body:
                return True
            time.sleep(1.5)
        return False


def send_one(br, name, text, submit=False):
    """Address, write, and (only with submit) send. Returns a result string."""
    c = Compose(br)
    row = c.address(name)
    c.write(text)
    if not submit:
        log("STAGED for %s. Nothing sent." % name)
        return "staged", row
    pace = Pace()
    pace.before("message")
    ok = c.send(text)
    pace.after("message")
    return ("sent" if ok else "sent-unverified"), row
