# -*- coding: utf-8 -*-
"""The refused Page post of 2026-11-11 (the Reposter's 99vc8LPphW0), reproduced
by a staged run and fixed in three places.

THE DEFECT. `post` died at the media editor with "expected exactly one file
input in the media editor, found [...]": the count took every file input on the
admin page, and four chat bubbles open in the messaging overlay carried eight
more. The clean-up then pressed Dismiss once, which in the media editor only
goes BACK to the composer, and died a second time with "composer still open
after Dismiss + Discard". That second FAIL was the last line, so the caller
read it as the cause. Pressing "Add media" also opened the native Open dialog,
which was left on the screen.

These tests use the exact inputs read off the page that day. No browser is
opened here: the Page is driven by a fake that behaves as the live page did.
"""
import contextlib
import io
import os
import shutil
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cc_linkedin as C

MEDIA = "image/gif,image/jpeg,video/*,video/mp4"
CHAT_IMG = "image/*"
CHAT_FILE = "image/*,.ai,.psd,.pdf,.doc,.docx,.mp4"

# What EDITOR_INPUTS returned on the DevThrottle admin page, 2026-11-11 15:31,
# with four chat bubbles open: the editor's own input and eight from the chats.
PAGE_INPUTS = [{"id": "media-editor-file-selector__file-input", "accept": MEDIA, "editor": True}] + [
    {"id": "attachment-input-ember%d" % n, "accept": CHAT_IMG if n % 4 == 0 else CHAT_FILE, "editor": False}
    for n in (156, 158, 198, 200, 236, 238, 274, 276)]


class EditorInputs(unittest.TestCase):
    def test_chat_bubble_inputs_are_not_counted(self):
        got = C.editor_inputs(PAGE_INPUTS)
        self.assertEqual([i["id"] for i in got], ["media-editor-file-selector__file-input"])

    def test_two_inputs_in_the_editor_still_refuse(self):
        two = PAGE_INPUTS + [{"id": "second", "accept": MEDIA, "editor": True}]
        self.assertEqual(len(C.editor_inputs(two)), 2)

    def test_no_editor_input_is_empty(self):
        self.assertEqual(C.editor_inputs([dict(i, editor=False) for i in PAGE_INPUTS]), [])

    def test_the_script_marks_the_editor_modal(self):
        # The page script must scope by the editor's own modal, not by the page.
        self.assertIn("closest('[role=dialog]')", C.EDITOR_INPUTS)
        self.assertIn("modal.contains(el)", C.EDITOR_INPUTS)


class FakeLocator(object):
    def __init__(self, n):
        self.n = n

    def count(self):
        return self.n


class FakePage(object):
    """Stands in for the live page. `state` is one of:
    editor    the media editor is open (no .share-creation-state, a live dialog)
    composer  the composer is open and empty
    gone      nothing open, the 'Start a post' box is back
    Dismiss moves editor -> composer -> gone, as measured on 2026-11-11."""

    def __init__(self, state, stuck=False):
        self.state = state
        self.stuck = stuck
        self.dismissed = 0


class FakeLinkedInPage(C.Page):
    def __init__(self, fake):
        # No browser: everything discard() reads goes through the fake.
        self.fake = fake
        self.choosers = 0

    def composer_open(self):
        return self.fake.state == "composer"

    def live_dialog(self):
        return FakeLocator(0 if self.fake.state == "gone" else 1)

    def editor_text(self):
        return ""

    def has_button(self, name):
        return False

    def buttons(self):
        return [] if self.fake.state == "gone" else ["Dismiss", "Add media", "Post"]

    def dismiss_button(self):
        return None if self.fake.state == "gone" else "Dismiss"

    def press(self, locator, what):
        if what == "Dismiss" and not self.fake.stuck:
            self.fake.dismissed += 1
            self.fake.state = {"editor": "composer", "composer": "gone"}[self.fake.state]

    def discard_prompt(self, timeout_ms):
        return None

    def closed(self, seconds):
        return self.fake.state == "gone"

    def start_box_back(self):
        return self.fake.state == "gone"


def run(fn):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        try:
            result = fn()
        except SystemExit as e:
            result = ("exit", e.code)
    return result, out.getvalue()


class DiscardFromTheMediaEditor(unittest.TestCase):
    def test_two_dismisses_close_a_composer_left_in_the_media_editor(self):
        fake = FakePage("editor")
        result, out = run(lambda: FakeLinkedInPage(fake).discard("clearing up after failure"))
        self.assertTrue(result, out)
        self.assertEqual(fake.dismissed, 2)
        self.assertIn("composer discarded, nothing kept", out)
        self.assertNotIn("FAIL", out)

    def test_an_empty_composer_takes_one(self):
        fake = FakePage("composer")
        result, out = run(lambda: FakeLinkedInPage(fake).discard("staged only"))
        self.assertTrue(result, out)
        self.assertEqual(fake.dismissed, 1)

    def test_a_composer_that_never_closes_fails_after_the_rounds(self):
        fake = FakePage("composer", stuck=True)
        result, out = run(lambda: FakeLinkedInPage(fake).discard("staged only"))
        self.assertEqual(result, ("exit", 1))
        self.assertIn("FAIL composer still open after 3 rounds", out)

    def test_clearing_up_after_a_failure_never_prints_a_second_fail(self):
        # The cause must stay the last FAIL line: the Reposter reads the last one.
        fake = FakePage("composer", stuck=True)
        result, out = run(lambda: FakeLinkedInPage(fake).discard("clearing up after failure", fatal=False))
        self.assertIs(result, False)
        self.assertNotIn("FAIL", out)
        self.assertIn("could not clear up: composer still open", out)


class LaggingPage(FakePage):
    """The composer is still closing when the 4 s check runs out, and has gone
    by the time the next round looks for Dismiss (review of #39, finding 1)."""

    def __init__(self):
        FakePage.__init__(self, "composer")


class LaggingLinkedInPage(FakeLinkedInPage):
    def press(self, locator, what):
        if what == "Dismiss":
            self.fake.dismissed += 1
            self.fake.state = "closing"

    def composer_open(self):
        return self.fake.state in ("composer", "closing")

    def closed(self, seconds):
        if self.fake.state == "closing":
            # LinkedIn finishes the teardown just after this check gives up.
            self.fake.state = "gone"
            return False
        return self.fake.state == "gone"


class DiscardRace(unittest.TestCase):
    def test_a_composer_that_closes_late_is_a_clean_discard_not_a_fail(self):
        fake = LaggingPage()
        result, out = run(lambda: LaggingLinkedInPage(fake).discard("staged only"))
        self.assertTrue(result, out)
        self.assertEqual(fake.dismissed, 1)
        self.assertNotIn("FAIL", out)
        self.assertIn("composer discarded, nothing kept", out)

    def test_no_dismiss_button_on_a_page_still_open_still_fails(self):
        # The control: a composer that is open and has no Dismiss is still refused.
        class NoDismiss(FakeLinkedInPage):
            def dismiss_button(self):
                return None
        result, out = run(lambda: NoDismiss(FakePage("composer")).discard("staged only"))
        self.assertEqual(result, ("exit", 1))
        self.assertIn("FAIL composer is open but has no Dismiss button", out)


class ChooserCountPage(C.Page):
    """A Page for cmd_post with no browser. `stray` file choosers are opened by
    keystrokes that should never open one (the mis-click the OS dialog used to
    prove); each "Add media" opens one, as measured on 2026-11-11."""

    def __init__(self, stray):
        self.choosers = stray
        self.admin = ""
        self.page = self
        self.attached = False

    def evaluate(self, script, *args):
        return ""

    def ensure_empty_composer(self):
        pass

    def attach(self, files):
        self.choosers += 1
        self.attached = True
        return False

    def media_still_attached(self):
        return self.attached

    def type_text(self, text):
        pass

    def discard(self, why, fatal=True):
        return True

    def composer_open(self):
        return False

    def live_dialog(self):
        return FakeLocator(0)

    def close(self):
        pass


class ChooserCount(unittest.TestCase):
    """Review of #39, finding 2: an intercepted chooser beyond one per Add media
    is a keystroke that landed on the wrong thing, and fails the run."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.text = os.path.join(self.tmp, "post.txt")
        with open(self.text, "w", encoding="utf-8") as f:
            f.write("Opening line of the post\n\nBody.")
        self.video = os.path.join(self.tmp, "clip.mp4")
        with open(self.video, "wb") as f:
            f.write(b"0")
        self.saved = (C.sync_playwright, C.attach_page, C.release, C.close_file_dialogs)
        C.sync_playwright = lambda: contextlib.nullcontext(None)
        C.release = lambda: None
        C.close_file_dialogs = lambda where, port: False

    def tearDown(self):
        C.sync_playwright, C.attach_page, C.release, C.close_file_dialogs = self.saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def post(self, stray, media):
        class Browser(object):
            def close(self):
                pass
        C.attach_page = lambda p, a, shot: (Browser(), ChooserCountPage(stray))
        a = types.SimpleNamespace(media=media, text=self.text, schedule=None, submit=False, shot="",
                                  port=9224, page="144093416", page_name="DevThrottle")
        return run(lambda: C.cmd_post(a))

    def test_a_stray_chooser_fails_the_run(self):
        result, out = self.post(stray=1, media=[])
        self.assertEqual(result, ("exit", 1), out)
        self.assertIn("FAIL", out)
        self.assertIn("file chooser", out)

    def test_a_stray_chooser_beside_the_one_add_media_opens_fails_the_run(self):
        result, out = self.post(stray=1, media=[self.video])
        self.assertEqual(result, ("exit", 1), out)
        self.assertIn("file chooser", out)

    def test_one_chooser_from_add_media_passes(self):
        # The control: the one chooser Add media opens is expected.
        result, out = self.post(stray=0, media=[self.video])
        self.assertNotIn("FAIL", out)
        self.assertIn("RESULT staged", out)

    def test_no_media_and_no_chooser_passes(self):
        result, out = self.post(stray=0, media=[])
        self.assertNotIn("FAIL", out)
        self.assertIn("RESULT staged", out)


class FileChooserIsIntercepted(unittest.TestCase):
    def test_every_page_session_listens_for_file_choosers(self):
        calls = []

        class Tab(object):
            def on(self, event, fn):
                calls.append(event)

        orig = C.open_working_tab
        C.open_working_tab = lambda browser: Tab()
        try:
            C.Page(object(), "144093416", "DevThrottle", "", 9224)
        finally:
            C.open_working_tab = orig
        self.assertEqual(calls, ["filechooser"])


if __name__ == "__main__":
    unittest.main()
