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
  * no organisation id on an organisation PATH - `/company/<digits>` and the
    three sibling paths that carry the same thing - unless the id is on the
    explicit allowlist below. RULING R19, 2026-09-10.

WHY R19 EXISTS. The digit-run rule above has a floor of fifteen, chosen so that
the owner's own nine-digit Page id survives it. A LinkedIn ORGANISATION id is
six to nine digits, so it passes under that floor by construction - every one of
them, the owner's and a stranger's alike. `tools/survey.py` already redacts
these (ORG_PATH, with its own OWN allowlist), but nothing TESTED THE ARTEFACT
for them, which is the exact gap R18 was written about: the redactor knew the
form and the check did not, so a dump that skipped the redactor, or a path
handwritten into a docstring, would have carried one out of here unnoticed.

A shape rule cannot work here - no shape separates a real organisation id from a
fabricated one - so this rule is an ALLOWLIST OF EXACT VALUES, and that is its
weakness as well as its design. Adding a value to it is how this check would be
silenced, so every entry carries the reason it is there, and an id that is not
obviously the owner's or obviously made up does not go in the list: it comes out
of the file.

NOT COVERED, said plainly: an organisation id that appears somewhere OTHER than
one of these paths - `urn:li:organization:<id>`, a `fsd_company` parameter, a
bare number in prose. The urn form is redacted by shape in `tools/survey.py`;
the others are not detected by anything here. This rule is the path form only.

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
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

# THE RULES ARE IMPORTED, NOT RETYPED. Ruling 2026-09-10, and it is the whole
# point of the second test class in this file.
#
# On 2026-09-10 tools/survey.py learned `vanityName` - a query parameter carrying
# a profile slug, found live in dumps already on main in this PUBLIC repository -
# and THIS FILE did not. That is R18's gap reopening one layer up: the redactor
# knows the form, the artefact check cannot see it, the next dump leaks and the
# suite stays green. Writing one assertion per parameter here would have
# reproduced the defect exactly - teach the redactor a seventh parameter and the
# check silently keeps passing without it.
#
# So nothing below enumerates a parameter, a path, or a urn spelling. Each rule
# LOOPS over the list tools/survey.py builds its own regexes from. Adding a form
# there arms the check here in the same edit, and there is no second list to
# forget. This is the fifth time this coupling defect has appeared here.
from survey import (SENSITIVE_QUERY_PARAMS, QUERY_PLACEHOLDER, PATH_FORMS,
                    ORG_PATH_NAMES, URN_FORMS)
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

# R19, 2026-09-10. An organisation id sitting on an organisation path. The four
# path names are the ones tools/survey.py's ORG_PATH already knows, taken from
# the same list on purpose: two lists of paths drift apart, one does not.
ORG_ID_PATH = re.compile(r"/(company|school|showcase|organization)/(\d+)", re.I)

# Organisation ids this repository is allowed to contain. EVERY entry needs the
# reason it is here. This allowlist is the only thing standing between a real
# third party's id and a public repository, so growing it to make a red check go
# green is not a fix - it is the defect, performed deliberately.
ALLOWED_ORG_IDS = {
    # The owner's own Page. Public, in these documents by intent, and a dump of
    # his own Page's analytics that cannot say which Page it is has lost the
    # thing it was taken for. Ruling R13.3.
    "107519091": "the owner's own Page",
    # Fabricated controls. Made up at the keyboard, not lifted from any page,
    # and used by tests that need an id which is NOT the owner's.
    "12345678": "fabricated, tests/test_no_leak.py negative control",
    "999999": "fabricated, tests/test_stats_table.py wrong-Page control",
}


def _org_ids_not_allowed(line):
    """Every organisation id on an organisation path in this line that is not on
    the allowlist. Returns (path, id) pairs."""
    return [(m.group(1), m.group(2)) for m in ORG_ID_PATH.finditer(line)
            if m.group(2) not in ALLOWED_ORG_IDS]


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

    def test_no_third_party_organisation_id_on_an_organisation_path(self):
        """R19. An organisation id is six to nine digits, so the fifteen-digit
        rule above cannot see one - the owner's or anybody else's."""
        bad = []
        for path in DUMPS:
            with open(path, encoding="utf-8") as f:
                for n, line in enumerate(f, 1):
                    for kind, oid in _org_ids_not_allowed(line):
                        bad.append("%s:%d /%s/%s" % (os.path.basename(path), n, kind, oid))
        self.assertEqual(bad, [], "an organisation id names a real company page and is a stable "
                                  "key to it; put it on ALLOWED_ORG_IDS only if it is the "
                                  "owner's own or was made up:\n  " + "\n  ".join(bad[:10]))

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
        # A SYNTHETIC 8-digit id, not one lifted from the dumps. The line below
        # used to carry a real third-party organization id, put back into the
        # repository by the very test that exists to keep such ids out of it -
        # exactly the failure this test class's docstring warns about, committed
        # in the same file that warns about it.
        self.assertFalse(LONG_NUMBER.search("/company/12345678"))    # 8 digits: below the rule
        self.assertTrue(REAL_SHORT_LINK.search("https://lnkd.in/" + FABRICATED_CODE))
        self.assertTrue(REAL_SHORT_LINK.search(
            "url=https%3A%2F%2Flnkd%2Ein%2F" + FABRICATED_CODE))
        self.assertFalse(REAL_SHORT_LINK.search("https://lnkd.in/<shortlink>"))
        # R19's detector. A fabricated id that is deliberately NOT on the
        # allowlist - if this one ever has to be added to make a check pass,
        # something is wrong with the check and not with the id.
        stranger = "88888888"
        self.assertNotIn(stranger, ALLOWED_ORG_IDS)
        self.assertEqual(_org_ids_not_allowed("/company/" + stranger),
                         [("company", stranger)])
        for kind in ("school", "showcase", "organization"):
            self.assertEqual(_org_ids_not_allowed("https://www.linkedin.com/%s/%s/about/"
                                                  % (kind, stranger)), [(kind, stranger)])
        # and the three things it must NOT flag
        self.assertEqual(_org_ids_not_allowed("/company/107519091/admin/"), [])
        self.assertEqual(_org_ids_not_allowed("/company/centerconsulting-inc"), [])
        self.assertEqual(_org_ids_not_allowed("/company/%s"), [])
        # every entry on the allowlist carries the reason it is there
        for oid, why in ALLOWED_ORG_IDS.items():
            self.assertTrue(why and why.strip(), "%s is allowlisted with no reason" % oid)


class TheCommittedDumpsCarryNoIdentifierTheRedactorKnows(unittest.TestCase):
    """Every form tools/survey.py knows how to redact, checked ON THE ARTEFACT.

    The class above tests three SHAPES - a run of digits, a short link, an
    organisation id on a path - and it is deliberately independent of the
    redactor, so that it still fires when the redactor is the thing that is
    wrong. This class is the other half: it tests that everything the redactor
    CLAIMS to remove is in fact absent from the committed files, and it reads the
    claim from the redactor itself so that the two cannot drift apart.

    A failure here means one of two things and both matter: an identifier is in a
    public repository, or a dump was written by something that skipped the
    redactor.

    WHAT THIS DOES NOT COVER, and it is one of the four forms found on
    2026-09-10: an identifier written into a DOM ELEMENT ID, with no path, no urn
    and no parameter around it - `div#ProfilePostConnectDrawer_<slug>` and five
    siblings. It is arbitrary text in an arbitrary attribute. No shape separates
    it from an ordinary identifier, and enumerating the element-id prefixes is
    the losing game R17 is about. What guards it instead is survey.py's
    SUBJECT_TOKENS pass, which redacts the literal slugs and organisation keys
    the LIVE PAGE names wherever they appear, plus a person reading the dump
    before committing it. In practice a page that writes somebody's slug into an
    element id also links to them, so the profile-path rule below usually catches
    the same person by another route - that is a reason to expect the guard to
    hold, NOT a proof, and it says nothing about a third party whom no link on
    the page names.
    """

    def test_there_are_dumps_to_check(self):
        # Same reason as the class above: a sweep whose pass condition is an
        # absence certifies a run that never happened.
        self.assertTrue(DUMPS, "no survey dumps found under docs/surveys - every absence "
                               "asserted below would then be the absence of files")

    def test_every_sensitive_query_parameter_carries_only_the_placeholder(self):
        """ONE rule over SENSITIVE_QUERY_PARAMS. This is the check that was not
        there when vanityName was taught to the redactor alone."""
        self.assertTrue(SENSITIVE_QUERY_PARAMS, "the parameter list is empty, so this rule "
                                                "would examine nothing")
        rule = re.compile(r"[?&](%s)=([^&\"\s]*)" % "|".join(SENSITIVE_QUERY_PARAMS), re.I)
        bad = []
        for path in DUMPS:
            with open(path, encoding="utf-8") as f:
                for n, line in enumerate(f, 1):
                    for m in rule.finditer(line):
                        if m.group(2) and m.group(2) != QUERY_PLACEHOLDER:
                            bad.append("%s:%d %s=%s" % (os.path.basename(path), n,
                                                        m.group(1), m.group(2)[:40]))
        self.assertEqual(bad, [], "a sensitive query parameter is carrying a real value, and "
                                  "each of these resolves to a person, a company or a private "
                                  "conversation:\n  " + "\n  ".join(bad[:10]))

    def test_every_identifier_path_carries_only_its_placeholder(self):
        """ONE rule over PATH_FORMS: the profile path in both spellings, the
        conversation path, the job path."""
        self.assertTrue(PATH_FORMS, "PATH_FORMS is empty, so this rule would examine nothing")
        bad = []
        for name in sorted(PATH_FORMS):
            prefix, tail, placeholder = PATH_FORMS[name]
            rule = re.compile("(%s)(%s)" % (prefix, tail), re.I)
            for path in DUMPS:
                with open(path, encoding="utf-8") as f:
                    for n, line in enumerate(f, 1):
                        for m in rule.finditer(line):
                            if m.group(2) != placeholder.strip("<>"):
                                bad.append("%s:%d [%s] %s%s"
                                           % (os.path.basename(path), n, name,
                                              m.group(1), m.group(2)[:40]))
        self.assertEqual(bad, [], "an identifier is sitting on a path in a public "
                                  "repository:\n  " + "\n  ".join(bad[:10]))

    def test_every_organisation_path_carries_a_placeholder_or_an_allowed_key(self):
        """ONE rule over ORG_PATH_NAMES, in both spellings.

        The R19 rule in the class above covers NUMERIC organisation ids on the
        four literal paths. This one covers the SLUG form and the percent-encoded
        spelling, neither of which that rule can see."""
        self.assertTrue(ORG_PATH_NAMES, "ORG_PATH_NAMES is empty")
        allowed = set(ALLOWED_ORG_IDS) | {"company", "centerconsulting-inc"}
        rule = re.compile(r"(?:/|%%2F)(?:%s)(?:/|%%2F)([A-Za-z0-9._%%-]+)"
                          % "|".join(ORG_PATH_NAMES), re.I)
        bad = []
        for path in DUMPS:
            with open(path, encoding="utf-8") as f:
                for n, line in enumerate(f, 1):
                    for m in rule.finditer(line):
                        if m.group(1) not in allowed:
                            bad.append("%s:%d %s" % (os.path.basename(path), n, m.group(1)[:40]))
        self.assertEqual(bad, [], "an organisation is named on a path. Only the owner's own "
                                  "Page survives redaction, by ruling R13.3:\n  "
                                  + "\n  ".join(bad[:10]))

    def test_every_urn_carries_only_its_placeholder(self):
        """ONE rule over URN_FORMS - plain and percent-encoded. The encoded
        spelling is how a urn arrives inside a query value, and the literal-only
        rule walked past it until 2026-09-10."""
        self.assertTrue(URN_FORMS, "URN_FORMS is empty")
        bad = []
        for prefix, tail, placeholder in URN_FORMS:
            rule = re.compile("(%s)(%s)" % (prefix, tail), re.I)
            for path in DUMPS:
                with open(path, encoding="utf-8") as f:
                    for n, line in enumerate(f, 1):
                        for m in rule.finditer(line):
                            if m.group(2) != placeholder.strip("<>"):
                                bad.append("%s:%d %s%s" % (os.path.basename(path), n,
                                                           m.group(1), m.group(2)[:40]))
        self.assertEqual(bad, [], "a urn is a stable key to a post, a profile or an "
                                  "organisation:\n  " + "\n  ".join(bad[:10]))

    def test_these_rules_can_actually_fail(self):
        """Positive controls, built from FABRICATED values.

        Every rule above passes by finding nothing, and a rule that cannot match
        its own target passes that way forever. Each is therefore pointed at a
        made-up identifier of the right shape and watched matching it, and the
        query rule is exercised once per parameter, so a parameter the regex
        cannot actually match is caught here rather than by a leak.

        Nothing real is written here. Putting a genuine identifier in this file
        to prove identifiers are not in this repository is how the first pass of
        the R18 fix failed, in this very file.
        """
        fake = "a-fabricated-value-1234"

        rule = re.compile(r"[?&](%s)=([^&\"\s]*)" % "|".join(SENSITIVE_QUERY_PARAMS), re.I)
        for param in SENSITIVE_QUERY_PARAMS:
            m = rule.search("/x?%s=%s&next=1" % (param, fake))
            self.assertIsNotNone(m, "%s is on the redactor's list but this rule cannot "
                                    "match it" % param)
            self.assertEqual(m.group(2), fake)
            clean = rule.search("/x?%s=%s&next=1" % (param, QUERY_PLACEHOLDER))
            self.assertEqual(clean.group(2), QUERY_PLACEHOLDER,
                             "%s: a redacted value must read as the placeholder" % param)

        samples = {"profile": "/in/" + fake,
                   "thread": "/messaging/thread/2-AbCdEf1234",
                   "job": "/jobs/view/1234567890"}
        for name in sorted(PATH_FORMS):
            prefix, tail, placeholder = PATH_FORMS[name]
            r = re.compile("(%s)(%s)" % (prefix, tail), re.I)
            self.assertIn(name, samples, "PATH_FORMS gained %r and this control did not - the "
                                         "rule above is running unproven on it" % name)
            m = r.search(samples[name])
            self.assertIsNotNone(m, "%s: the path rule cannot match its own form" % name)
            self.assertNotEqual(m.group(2), placeholder.strip("<>"))
            redacted = samples[name].replace(m.group(2), placeholder.strip("<>"))
            self.assertEqual(r.search(redacted).group(2), placeholder.strip("<>"),
                             "%s: a redacted path must read as the placeholder" % name)

        # The form that defeated the path rule and the literal-token rule at the
        # same time: percent-encoded AND truncated by a probe's own slice.
        prefix, tail, _ = PATH_FORMS["profile"]
        profile_rule = re.compile("(%s)(%s)" % (prefix, tail), re.I)
        self.assertIsNotNone(
            profile_rule.search("body=https%3A%2F%2Fwww.linkedin.com%2Fin%2Fa-cut-slug-"),
            "a percent-encoded, truncated profile path must still match - that exact string "
            "is what got through on 2026-09-10")
        # A BARE path prefix carries no identifier and must NOT be flagged: it is
        # what a CSS selector inside a recorded probe expression looks like, and
        # an earlier version of these rules rewrote one.
        self.assertIsNone(profile_rule.search('a[href*="/in/"]'))
        t_prefix, t_tail, _ = PATH_FORMS["thread"]
        self.assertIsNone(re.compile("(%s)(%s)" % (t_prefix, t_tail), re.I)
                          .search('a[href*="/messaging/thread/"]'))

        org = re.compile(r"(?:/|%%2F)(?:%s)(?:/|%%2F)([A-Za-z0-9._%%-]+)"
                         % "|".join(ORG_PATH_NAMES), re.I)
        for name in ORG_PATH_NAMES:
            self.assertEqual(org.search("/%s/%s" % (name, fake)).group(1), fake)
            self.assertEqual(org.search("%%2F%s%%2F%s" % (name, fake)).group(1), fake)
        self.assertIsNone(org.search("/company/<company>"))

        urn_samples = ("urn:li:activity:" + FABRICATED_ID,
                       "urn%3Ali%3Afsd_profile%3AACoAABfabricated")
        self.assertEqual(len(urn_samples), len(URN_FORMS),
                         "URN_FORMS changed and these controls did not")
        for (prefix, tail, placeholder), sample in zip(URN_FORMS, urn_samples):
            r = re.compile("(%s)(%s)" % (prefix, tail), re.I)
            m = r.search(sample)
            self.assertIsNotNone(m, "the urn rule cannot match its own form: %s" % prefix)
            self.assertNotEqual(m.group(2), placeholder.strip("<>"))


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

    def test_no_third_party_organisation_id_on_an_organisation_path_in_the_source(self):
        """R19, on the source tree. The leak that started all of this was three
        short links handwritten into a module docstring, where no redactor was
        ever going to look; an organisation path written into a selector, a test
        fixture or a comment is the same act."""
        bad = []
        for path in self._tracked_text():
            with open(path, encoding="utf-8") as f:
                for n, line in enumerate(f, 1):
                    for kind, oid in _org_ids_not_allowed(line):
                        bad.append("%s:%d /%s/%s" % (os.path.relpath(path, ROOT), n, kind, oid))
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
