# -*- coding: utf-8 -*-
"""R18: the redaction needs a check that can FAIL, not just an implementation.

This repository is PUBLIC. The fourth inspection pass found third-party
identifiers in the committed survey dumps; the first fix taught the redactor the
named forms it had missed, and the Architect then found the SAME post id still
sitting in a dump one level down, written `shareId=<19 digits>` inside a DOM
element id rather than as `urn:li:share:...`. Running this check for the first
time found seven more of the same kind that nobody had looked for: the whole urn
percent-encoded, `li%3Aactivity%3A<19 digits>`, inside a notification href.

That is the entire defect repeating itself: a redactor that knows N forms always
loses to form N+1, and an implementation with no failing check behind it is a
claim, not a guarantee.

So this file does not test the redactor. It tests THE ARTEFACT - the committed
dumps themselves - and it does it by SHAPE rather than by enumerating syntax:

  * no run of 15 or more consecutive digits, anywhere, in any surrounding
    punctuation. LinkedIn content ids are 19 digits, so this catches every one
    of them whatever wraps it. The owner's Page id is 9 digits and his
    organisation ids are shorter, so they survive - which is what R13.3 wants.
  * no lnkd.in link with a real code on the end, plain or percent-encoded.

WHY THE DUMPS AND THE CODE, AND NOT THE DOCUMENTS. A shape rule cannot tell the
owner's own content id from a stranger's, and the documents name one of his own
posts on purpose - it is the selftest fixture. The dumps need no content id at
all to be useful, and neither does the code, so on those two the rule is free
and absolute. On the documents it would have to be a judgement, and a judgement
belongs to a person: the leak in the prose was found by reading, and R13 records
what was taken out and why.

A failure here is not a style complaint. It means an identifier that resolves to
a real person's content is in a public repository.
"""
import glob
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DUMPS = sorted(glob.glob(os.path.join(ROOT, "docs", "surveys", "*.txt")))

LONG_NUMBER = re.compile(r"\d{15,}")
# Ids this repository is allowed to contain, because they were made up. They are
# 19 digits on purpose - a test of a shape has to use that shape - and they are
# allowed BY THEIR VALUE, not by which file they appear in. Assembled rather than
# written out so that this line does not itself contain a 15-digit run.
FABRICATED_PREFIX = "7" + "0" * 15
FABRICATED_ID = FABRICATED_PREFIX + "111"
FABRICATED_CODE = "AaAaAaAa"
FABRICATED = re.compile(r"^" + FABRICATED_PREFIX + r"\d{3}$")
# lnkd.in/<code>, plain or with the dot and slash percent-encoded, where <code>
# is an actual code rather than the placeholder the redactor leaves behind.
REAL_SHORT_LINK = re.compile(r"lnkd(?:\.|%2E)in(?:/|%2F)(?!<shortlink>)[A-Za-z0-9_%/-]{4,}", re.I)


class TheCommittedDumpsCarryNoIdentifiers(unittest.TestCase):

    def test_there_are_dumps_to_check(self):
        # The instrument first. A sweep whose pass condition is an absence
        # certifies a run that never happened, so this asserts the PRESENCE of
        # the thing being swept before any absence below is believed.
        self.assertTrue(DUMPS, "no survey dumps found under docs/surveys - this suite would "
                               "then pass by examining nothing")
        self.assertGreaterEqual(len(DUMPS), 8, "only %d dumps found; there were eight"
                                % len(DUMPS))

    def test_no_run_of_fifteen_or_more_digits(self):
        bad = []
        for path in DUMPS:
            with open(path, encoding="utf-8") as f:
                for n, line in enumerate(f, 1):
                    for m in LONG_NUMBER.finditer(line):
                        bad.append("%s:%d %s" % (os.path.basename(path), n,
                                                 line.strip()[max(0, m.start() - 40):m.end() + 20]))
        self.assertEqual(bad, [], "a LinkedIn content id is 19 digits and resolves to a real "
                                  "person's content:\n  " + "\n  ".join(bad[:10]))

    def test_no_short_link_with_a_real_code(self):
        bad = []
        for path in DUMPS:
            with open(path, encoding="utf-8") as f:
                for n, line in enumerate(f, 1):
                    for m in REAL_SHORT_LINK.finditer(line):
                        bad.append("%s:%d %s" % (os.path.basename(path), n, m.group(0)))
        self.assertEqual(bad, [], "following a short link recovers the post and its author:\n  "
                                  + "\n  ".join(bad[:10]))

    def test_the_detectors_can_actually_match(self):
        """Positive controls. A zero from a detector that cannot match its own
        target is not a clean result, it is a broken instrument.

        The controls are built from a FABRICATED id and a FABRICATED short-link
        code. Writing a real one here to prove the detector works would put the
        identifier back in the repository to prove it is not in the repository,
        which is how the first pass of this fix failed."""
        fake = FABRICATED_ID
        self.assertTrue(LONG_NUMBER.search("shareId=" + fake))      # the form that got through
        self.assertTrue(LONG_NUMBER.search("urn:li:activity:" + fake))
        self.assertTrue(LONG_NUMBER.search("x" + fake + "x"))
        self.assertTrue(LONG_NUMBER.search("id=expanded" + fake + "FeedType"))
        self.assertFalse(LONG_NUMBER.search("/company/107519091"))   # the owner's Page: 9 digits
        self.assertFalse(LONG_NUMBER.search("/company/37553728"))    # an org id: 8 digits
        self.assertTrue(REAL_SHORT_LINK.search("https://lnkd.in/" + FABRICATED_CODE))
        self.assertTrue(REAL_SHORT_LINK.search(
            "url=https%3A%2F%2Flnkd%2Ein%2F" + FABRICATED_CODE))
        self.assertFalse(REAL_SHORT_LINK.search("https://lnkd.in/<shortlink>"))


class TheSourceTreeCarriesNoShortLinks(unittest.TestCase):
    """The leak was not only in the dumps: three exact short links were
    handwritten into a module docstring, where no redactor was ever going to
    look at them."""

    def _tracked_text(self):
        out = []
        for pattern in ("kit/*.py", "tools/*.py", "tests/*.py", "*.py"):
            out += glob.glob(os.path.join(ROOT, pattern))
        return sorted(set(out))

    def test_there_are_source_files_to_check(self):
        self.assertGreaterEqual(len(self._tracked_text()), 10)

    def test_no_short_link_with_a_real_code_in_the_source(self):
        bad = []
        for path in self._tracked_text():
            with open(path, encoding="utf-8") as f:
                for n, line in enumerate(f, 1):
                    for m in REAL_SHORT_LINK.finditer(line):
                        bad.append("%s:%d %s" % (os.path.relpath(path, ROOT), n, m.group(0)))
        self.assertEqual(bad, [], "\n  ".join(bad[:10]))

    def test_no_run_of_fifteen_or_more_digits_in_the_source(self):
        bad = []
        for path in self._tracked_text():
            with open(path, encoding="utf-8") as f:
                for n, line in enumerate(f, 1):
                    for m in LONG_NUMBER.finditer(line):
                        if FABRICATED.match(m.group(0)):
                            continue
                        bad.append("%s:%d %s" % (os.path.relpath(path, ROOT), n, m.group(0)))
        self.assertEqual(bad, [], "\n  ".join(bad[:10]))


if __name__ == "__main__":
    unittest.main()
