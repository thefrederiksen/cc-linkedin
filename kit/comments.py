# -*- coding: utf-8 -*-
"""Phase 1 verbs: read a post, read and write comments, react, delete.

All of them act on ONE post, addressed by its permalink, and every control is
looked up inside that post's own container. The proofs are the presence of the
thing acted on: the comment row under our name, the reaction button's state,
the row gone after a reload.

MEASURED ON THE LIVE PAGE, 2026-09-09 (Soren's own post, classic rendering)
  * Comment box: textbox "Text editor for creating content" (classic) or
    "Text editor for creating comment" (new). Typing enables a button named
    "Comment"; keyboard Enter on it submits. The new row appears within a few
    seconds as `article.comments-comment-entity` with
    data-id="urn:li:comment:(ugcPost:...,...)".
  * Row controls: an UNLABELLED `button.artdeco-dropdown__trigger` (the "..."
    menu: Copy link to comment / Edit / Delete), "React Like to <name>'s
    comment", "Open reactions menu", "Reply to <name>'s comment".
  * Delete: menu item "Delete", then a dialog with Cancel / Delete. Confirm by
    keyboard. Proof: the row is gone after a reload.
  * Post reactions: "React Like" carries aria-pressed (classic); hovering it
    opens "React Celebrate/Support/Love/Insightful/Funny". The new rendering
    carries the state in the label "Reaction button state: ...".
  * Post menu: "Open control menu for post by <name>" -> Edit post / Delete post.
  * LinkedIn serves the permalink in two renderings at random. Comment rows are
    mapped on the classic one; when the new one is served for a verb that needs
    rows, the page is reloaded (up to 4 times) until the classic one comes.
"""
import json
import re
import time

from . import selectors as S
from .browser import Browser, Pace, log, die

ACTIVITY = re.compile(r"urn:li:(?:activity|ugcPost|share):\d+")


def urn_of(url):
    m = ACTIVITY.search(url)
    if not m:
        die("not a post permalink (no urn:li:activity in it): %s" % url)
    return m.group(0)


def permalink(urn):
    return "https://www.linkedin.com/feed/update/%s/" % urn


# ---------------------------------------------------------------- the post

class Post(object):
    """One post on its permalink page."""

    def __init__(self, br, url, expect=None, need_rows=False):
        self.br = br
        self.page = br.page
        self.urn = urn_of(url)
        self.url = permalink(self.urn)
        self.load(need_rows)
        if expect:
            text = self.text()
            if expect.lower() not in text.lower():
                die("the post does not contain %r; refusing to act on it. It begins: %r"
                    % (expect, text[:100]))
            log("post verified: contains %r" % expect)

    def load(self, need_rows=False):
        for attempt in range(1, 5):
            self.br.goto(self.url, settle=0)
            box = self.page.get_by_role("textbox", name=S.COMMENT_EDITOR_NAME).first
            try:
                box.wait_for(state="attached", timeout=45000)
            except Exception:
                die("no comment box on %s (is the post deleted, or comments off?)" % self.url)
            time.sleep(3)
            self.variant = "ember" if self.page.locator("[data-urn]").count() else "react"
            if self.variant == "ember" or not need_rows:
                break
            log("LinkedIn served the new rendering (attempt %d); reloading for the classic one, "
                "where comment rows are mapped" % attempt)
        else:
            die("LinkedIn kept serving the new rendering; comment rows are not mapped there yet")
        if self.variant == "ember":
            self.card = self.page.locator(S.EMBER["card"].format(urn=self.urn)).first
            if self.card.count() == 0:
                self.card = self.page.locator(S.EMBER["card_any"]).first
        else:
            self.card = self.page.locator("main")
        log("post loaded (%s rendering)" % self.variant)

    # -- reading -------------------------------------------------------------

    def author(self):
        menu = self.page.get_by_role("button", name=S.POST_MENU_NAME).first
        label = menu.get_attribute("aria-label") if menu.count() else ""
        m = re.search(r"post by (.+)$", label or "")
        return m.group(1).strip() if m else ""

    def text(self):
        if self.variant == "ember":
            more = self.card.locator(S.EMBER["more"])
            if more.count():
                try:
                    more.first.click(timeout=3000)
                    time.sleep(0.5)
                except Exception:
                    pass
            el = self.card.locator(S.EMBER["text"]).first
            return (el.inner_text() if el.count() else "").strip()
        parts = self.page.locator(S.REACT["text"]).all_inner_texts()
        return "\n".join(p.strip() for p in parts).strip()

    def media(self):
        scope = self.card
        if scope.locator("video").count():
            return "video"
        if scope.locator(S.EMBER["image"] if self.variant == "ember" else "img[src*='media']").count():
            return "image"
        return "none"

    def counts(self):
        if self.variant != "ember":
            return ""
        el = self.card.locator(S.EMBER["counts"]).first
        return el.inner_text().replace("\n", " ").strip() if el.count() else ""

    # -- comments ------------------------------------------------------------

    def editor(self):
        return self.page.get_by_role("textbox", name=S.COMMENT_EDITOR_NAME).first

    def load_all_comments(self):
        for _ in range(40):
            more = self.card.locator(S.EMBER["comment_load_more"])
            replies = self.card.locator(S.EMBER["comment_show_replies"])
            if more.count() and more.first.is_visible():
                more.first.click(timeout=5000)
                time.sleep(1.5)
                continue
            if replies.count() and replies.first.is_visible():
                replies.first.click(timeout=5000)
                time.sleep(1.5)
                continue
            break

    def rows(self):
        return self.card.locator(S.EMBER["comment_item"])

    def comments(self):
        out = []
        for item in self.rows().all():
            data = item.evaluate("""e => {
              const NL = String.fromCharCode(10);
              const link = e.querySelector('a[href*="/in/"], a[href*="/company/"]');
              const name = e.querySelector('.comments-comment-meta__description-title, .comments-post-meta__name-text, .comments-comment-meta__name');
              const body = e.querySelector('.comments-comment-item__main-content, .update-components-text');
              const time = e.querySelector('time, .comments-comment-meta__data');
              return {id: e.getAttribute('data-id') || '', author: name ? name.innerText.trim().split(NL)[0] : '',
                      url: link ? link.getAttribute('href').split('?')[0] : '',
                      text: body ? body.innerText.trim() : '', when: time ? time.innerText.trim() : '',
                      is_reply: !!e.closest('.comments-replies-list, [class*="replies-list"]')};
            }""")
            out.append(data)
        return out

    def find_row(self, needle):
        """The INNERMOST comment rows holding the text. A parent comment's
        article contains its replies' articles, so without this a reply also
        matches its parent (measured 2026-09-09: reply returned the parent id)."""
        # Match on the comment BODY, not the article's whole text: while a reply
        # is being typed, the parent's article also contains the reply editor's
        # text and would match its own child's words.
        body = self.page.locator(".comments-comment-item__main-content").filter(has_text=needle)
        inner = self.page.locator(S.EMBER["comment_item"]).filter(has=body)
        return self.rows().filter(has=body).filter(has_not=inner)

    def write_comment(self, text, into=None):
        """Type into the comment box (or a reply box inside `into`) and submit.
        Proof: a row holding exactly that text."""
        box = (into.locator("form.comments-comment-box__form").get_by_role("textbox", name=S.COMMENT_EDITOR_NAME).last
               if into is not None else self.editor())
        box.wait_for(state="visible", timeout=15000)
        box.click(timeout=10000)
        self.br.type_text(text)
        time.sleep(1)
        got = box.inner_text().strip()
        # A reply box comes pre-filled with the @mention of the comment's author
        # (LinkedIn inserts it; the memory rule "never start a reply with the
        # commenter's name" exists because of it). The typed text must END the
        # box; whatever precedes it is that mention.
        if got != text.strip() and not (into is not None and got.endswith(text.strip())):
            die("comment box holds %r, wanted %r" % (got[:80], text[:80]))
        if got != text.strip():
            log("reply box carries the auto-mention %r before the text" % got[: len(got) - len(text.strip())].strip())
        # The submit lives in the comment FORM. An article holds a second button
        # also named "Reply" (the action that opens the box), so the form scope
        # is what keeps the press on the right one (measured 2026-09-09 15:50).
        scope = (into if into is not None else self.card).locator("form.comments-comment-box__form")
        submit = scope.get_by_role("button", name=S.COMMENT_SUBMIT_NAME)
        enabled = None
        deadline = time.time() + 10
        while time.time() < deadline:
            for i in range(submit.count() - 1, -1, -1):
                b = submit.nth(i)
                if b.is_visible() and not b.is_disabled():
                    enabled = b
                    break
            if enabled is not None:
                break
            time.sleep(0.5)
        if enabled is None:
            die("no enabled Comment/Post button appeared after typing")
        self.br.press(enabled, "Comment (submit)")
        deadline = time.time() + 25
        while time.time() < deadline:
            row = self.find_row(text[:60])
            if row.count():
                rid = row.last.get_attribute("data-id") or ""
                return rid
            time.sleep(1.5)
        die("the comment was submitted but no comment row with that text appeared within 25s")

    def delete_row(self, row, what):
        trig = row.locator("button.artdeco-dropdown__trigger").first
        trig.click(timeout=10000)
        item = self.page.locator(S.EMBER["menu_item"]).filter(has_text=re.compile(r"^\s*Delete\s*$"))
        item.first.wait_for(state="visible", timeout=10000)
        item.first.click(timeout=10000)
        confirm = self.page.locator("[role=dialog], [role=alertdialog]").get_by_role("button", name=S.CONFIRM_DELETE)
        confirm.first.wait_for(state="visible", timeout=10000)
        self.br.press(confirm.first, "Delete (%s)" % what)
        time.sleep(3)

    # -- reactions -----------------------------------------------------------

    def like_button(self):
        # On the permalink page the social bar sits OUTSIDE the post card
        # (measured 2026-09-09: card = div.feed-shared-update-v2, bar = a
        # sibling). The post's Like is the one labelled exactly "React Like";
        # comment likes are "React Like to <name>'s comment", so exact wins.
        return self.page.locator(S.LIKE_ANY).first

    def reaction_state(self):
        b = self.like_button()
        label = b.get_attribute("aria-label") or ""
        if label.startswith("Reaction button state"):
            state = label.split(":", 1)[1].strip()
            return None if state == "no reaction" else state
        if b.get_attribute("aria-pressed") == "true":
            m = re.match(r"Unreact (\w+)", label)          # "Unreact Like", "Unreact Celebrate", ...
            return m.group(1) if m else ((b.inner_text() or "Like").strip() or "Like")
        return None


# ---------------------------------------------------------------- verbs

def read_post(a):
    with Browser(a.port) as br:
        p = Post(br, a.url)
        rec = {"urn": p.urn, "url": p.url, "author": p.author(), "text": p.text(),
               "media": p.media(), "counts": p.counts(), "rendering": p.variant}
        print(json.dumps(rec, ensure_ascii=True))
        print("RESULT read-post urn=%s author=%r media=%s chars=%d" % (p.urn, rec["author"], rec["media"], len(rec["text"])))


def read_comments(a):
    with Browser(a.port) as br:
        p = Post(br, a.url, need_rows=True)
        p.load_all_comments()
        rows = p.comments()
        for r in rows:
            print(json.dumps(r, ensure_ascii=True))
        print("RESULT read-comments urn=%s rows=%d" % (p.urn, len(rows)))


def comment(a):
    text = _text_arg(a)
    pace = Pace()
    with Browser(a.port) as br:
        p = Post(br, a.url, expect=a.expect, need_rows=True)
        p.load_all_comments()
        if p.find_row(text[:60]).count():
            print("RESULT already-commented urn=%s" % p.urn)
            return
        pace.before("comment")
        rid = p.write_comment(text)
        pace.after("comment")
        print("RESULT commented urn=%s id=%s" % (p.urn, rid))


def reply(a):
    text = _text_arg(a)
    pace = Pace()
    with Browser(a.port) as br:
        p = Post(br, a.url, expect=a.expect, need_rows=True)
        p.load_all_comments()
        target = p.find_row(a.to)
        if target.count() != 1:
            die("expected exactly one comment matching %r, found %d" % (a.to, target.count()))
        row = target.first
        row.get_by_role("button", name=re.compile(r"^Reply")).first.click(timeout=10000)
        time.sleep(1.5)
        pace.before("comment")
        rid = p.write_comment(text, into=row)
        pace.after("comment")
        print("RESULT replied urn=%s to=%r id=%s" % (p.urn, a.to, rid))


def delete_comment(a):
    with Browser(a.port) as br:
        p = Post(br, a.url, need_rows=True)
        p.load_all_comments()
        rows = p.find_row(a.match)
        if rows.count() != 1:
            die("expected exactly one comment containing %r, found %d" % (a.match, rows.count()))
        p.delete_row(rows.first, "comment")
        p.load(need_rows=True)
        p.load_all_comments()
        if p.find_row(a.match).count():
            die("the comment containing %r is still there after Delete" % a.match)
        print("RESULT deleted-comment urn=%s match=%r" % (p.urn, a.match))


def react(a):
    kind = a.kind.capitalize()
    pace = Pace()
    with Browser(a.port) as br:
        p = Post(br, a.url, expect=a.expect)
        if p.reaction_state():
            print("RESULT already-reacted urn=%s state=%r" % (p.urn, p.reaction_state()))
            return
        pace.before("react")
        btn = p.like_button()
        if kind == "Like":
            btn.click(timeout=10000)
        else:
            btn.hover(timeout=10000)
            tray = p.page.get_by_role("button", name=S.REACTION_NAME.format(kind=kind), exact=True)
            tray.first.wait_for(state="visible", timeout=10000)
            tray.first.click(timeout=10000)
        deadline = time.time() + 15
        while time.time() < deadline:
            state = p.reaction_state()
            if state:
                pace.after("react")
                print("RESULT reacted urn=%s kind=%s state=%r" % (p.urn, kind, state))
                return
            time.sleep(1)
        die("the reaction button never reported a reaction")


def unreact(a):
    with Browser(a.port) as br:
        p = Post(br, a.url)
        if not p.reaction_state():
            print("RESULT not-reacted urn=%s" % p.urn)
            return
        p.like_button().click(timeout=10000)
        deadline = time.time() + 15
        while time.time() < deadline:
            if not p.reaction_state():
                print("RESULT unreacted urn=%s" % p.urn)
                return
            time.sleep(1)
        die("the reaction button still reports a reaction")


def delete_post(a):
    with Browser(a.port) as br:
        p = Post(br, a.url, expect=a.expect)
        t0 = time.time()
        p.page.get_by_role("button", name=S.POST_MENU_NAME).first.click(timeout=10000)
        log("post menu opened (%.0fs)" % (time.time() - t0))
        item = p.page.locator(S.EMBER["menu_item"]).filter(has_text=re.compile(r"^\s*Delete post\s*$"))
        item.first.wait_for(state="visible", timeout=10000)
        item.first.click(timeout=10000)
        confirm = p.page.locator("[role=dialog], [role=alertdialog]").get_by_role("button", name=S.CONFIRM_DELETE)
        confirm.first.wait_for(state="visible", timeout=10000)
        br.press(confirm.first, "Delete post (confirm)")
        time.sleep(4)
        log("confirmed (%.0fs); reloading the permalink to prove it is gone" % (time.time() - t0))
        br.goto(p.url, settle=6)
        log("permalink reloaded (%.0fs)" % (time.time() - t0))
        if p.page.get_by_role("button", name=S.POST_MENU_NAME).count():
            die("the post is still on its permalink after Delete")
        print("RESULT deleted-post urn=%s" % p.urn)


def _text_arg(a):
    if a.text_file:
        text = open(a.text_file, encoding="utf-8").read().strip()
    else:
        text = (a.text or "").strip()
    if not text:
        die("no text given (--text or --text-file)")
    if len(text) > 1250:
        die("comment is %d chars; LinkedIn's limit is 1250" % len(text))
    return text
