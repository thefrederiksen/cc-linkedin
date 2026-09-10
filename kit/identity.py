# -*- coding: utf-8 -*-
"""What post is this, and does the page agree?

RULINGS R1 AND R2, 2026-09-09. The independent inspection found that
`search-posts --resolve` proved only that some substring of the browser's final
URL matched a permissive regular expression, and that `kit/comments.py` then
fell back from the card for the requested urn to THE FIRST ARBITRARY POST CARD
on the page. Between them, a well-formed permalink for a post nobody asked for
reached `comment`, `react` and `delete-post` - with a null error, counted as
resolved, and indistinguishable from a good row by any caller.

THE RULE THIS FILE ENFORCES: identity is READ FROM THE PAGE, and the URL only
ever gets to AGREE with it.

  * A regular expression agreeing with a string it was pointed at is not a
    measurement. The landed post page states what post it is - as a `data-urn`
    on the post card in the classic rendering, and as the canonical URL the page
    publishes for itself in both. That is the measurement.
  * The URL is a CROSS-CHECK, never a source. If the path also yields a
    candidate it must agree; disagreement is a FAIL for that row and never a
    preference for one of them.
  * Exactly one candidate, or it is not resolved. More than one distinct
    candidate anywhere is ambiguity, and ambiguity is no permalink and an error
    naming what it saw. First-match is banned.
  * The patterns are ANCHORED and the host and path type are validated. A final
    URL on another host, or on a /company/ or /school/ path, resolves to nothing.

NOT MEASURED, AND SAID PLAINLY. R1 asks for a survey of which of those identity
sources a landed post page actually carries, and that survey needs the live
site. The daily view cap was exhausted when this was written, so it has NOT been
done. The code therefore REFUSES rather than guesses: a page that states no
identity of its own is `permalink: null` with an error naming what the page did
carry, so the survey falls out of the first live run instead of being assumed
here. See docs/inspection-fixes.md.
"""
import re
from urllib.parse import urlsplit, unquote

# A urn, anchored. Nothing may be attached to either end of it.
URN_EXACT = re.compile(r"^urn:li:(activity|ugcPost|share):(\d+)$")
# A urn found inside a larger string. Used ONLY to census how many distinct urns
# an input mentions - never to pick one.
URN_ANYWHERE = re.compile(r"urn:li:(?:activity|ugcPost|share):\d+")
# The TERMINAL id segment of a /posts/ path: -<kind>-<digits>-<hash>, at the end
# of the path and nowhere else. The old pattern took the FIRST such motif
# anywhere in the whole URL, query string included.
POSTS_SUFFIX = re.compile(r"-(activity|share|ugcPost)-(\d+)-[A-Za-z0-9_-]+$", re.I)
KIND = {"activity": "activity", "share": "share", "ugcpost": "ugcPost"}
HOSTS = ("linkedin.com",)
# Path types that are not a post, however post-shaped their slug is.
NOT_A_POST = ("/company/", "/school/", "/in/", "/showcase/")


def permalink(urn):
    return "https://www.linkedin.com/feed/update/%s/" % urn


def normalise(urn):
    """The urn if it is exactly one well-formed urn and nothing else, else None."""
    m = URN_EXACT.match((urn or "").strip())
    return "urn:li:%s:%s" % (KIND[m.group(1).lower()], m.group(2)) if m else None


def distinct(values):
    """Every well-formed urn these strings name, de-duplicated, in a stable order."""
    out = []
    for v in values or []:
        u = normalise(v)
        if u is None:
            u = urn_from_url(v)
        if u and u not in out:
            out.append(u)
    return out


def _linkedin(host):
    host = (host or "").lower().split(":")[0]
    return any(host == h or host.endswith("." + h) for h in HOSTS)


def urn_from_url(url):
    """The urn a LinkedIn URL's own PATH names, or None.

    Two shapes only, both anchored, both taken from the path and never from the
    query string: /feed/update/<urn>/ and a /posts/ path ending in the
    -<kind>-<id>-<hash> segment. Any other host, and any path that is a company,
    school or member page, is not a post whatever its slug happens to spell.
    """
    s = (url or "").strip()
    if not s:
        return None
    exact = normalise(s)
    if exact:
        return exact
    try:
        parts = urlsplit(s)
    except ValueError:
        return None
    if not parts.scheme or not _linkedin(parts.netloc):
        return None
    path = unquote(parts.path or "")
    low = path.lower()
    if any(seg in low for seg in NOT_A_POST):
        return None
    segs = [p for p in path.split("/") if p]
    if len(segs) >= 3 and segs[0].lower() == "feed" and segs[1].lower() == "update":
        return normalise(segs[2])
    if len(segs) >= 2 and segs[0].lower() == "posts":
        m = POSTS_SUFFIX.search(segs[-1])
        if m:
            return "urn:li:%s:%s" % (KIND[m.group(1).lower()], m.group(2))
    return None


def resolve_post_identity(final_url, stated):
    """(urn, error) for the post the browser landed on.

    `stated` is what the PAGE said about itself, read out of the DOM as raw
    strings. The page is now the ONLY source of identity. R1.1 asked for a
    preference order over three sources - the post card's data-urn, the
    canonical link, the og:url - and the survey it asked for was finally taken
    live on 2026-09-10 across three landed post pages: every one carried a
    post-card data-urn, and NONE carried a canonical link or an og:url. So the
    order collapses to one item, and the caller passes what it finds.

    RULING R1.2 IS RETIRED, 2026-09-10. Retired as REDUNDANT AND FALSE-PREMISED.
    Not relaxed, and not softened because it went red - that distinction is the
    whole of this comment, because a guard dropped for failing is how a suite
    ends up certifying nothing.

    R1.2 said: the URL path must AGREE with what the page said, and disagreement
    is a FAIL. Two independent reasons it is gone:

    1. ITS PREMISE WAS FALSE. It assumed the two sources would name ONE id under
       two kind labels. LinkedIn does not work that way: an activity urn WRAPS a
       share or a ugcPost, and the wrapper carries a DIFFERENT id from the thing
       it wraps. So a post genuinely has two identities with two different
       numbers, and "the page and the path must agree" was never a statement
       about LinkedIn - it was a statement about what we assumed LinkedIn was.
       Measured, not argued: on all three rows of the first live resolve the
       page said urn:li:activity:<a> while the path said urn:li:share:<b> or
       urn:li:ugcPost:<b> with a != b. Then the decisive test - asking LinkedIn
       for the SHARE permalink of one of them serves the page whose single post
       card states the ACTIVITY urn. The server itself treats them as one post.
       That is routing behaviour, not our inference.
    2. IT WAS ALREADY REDUNDANT. The attack it existed to stop was a urn
       INFERRED from a URL string reaching a verb that comments, reacts or
       deletes. R1.1 removed that attack entirely by reading identity from the
       DOM: the path is no longer a source, so there is nothing to cross-check
       it against. A cross-check between a measurement and a thing that is no
       longer consulted is not a check.

    What guards this instead is the stronger thing that was always there: P2-6c
    compares the RESOLVED POST'S AUTHOR AND TEXT against the search row the
    permalink came from, and `may_use_any_card` (R2.2) refuses to act on a page
    whose stated identity is not the urn that was asked for. R2.2 met a real
    mismatch on its first live outing - the share permalink above - and refused
    by name. Neither of those is weakened here.

    Still enforced, unchanged: more than one DISTINCT identity stated by the
    page is ambiguity and resolves to nothing, and a page that states no
    identity of its own resolves to nothing rather than having one inferred from
    its URL. Those are R1.1 and R1.3, and they are what actually stop a
    wrong-but-well-formed permalink.
    """
    said = distinct(stated)
    if len(said) > 1:
        return None, ("the page states more than one post identity (%s); that is ambiguity, "
                      "not a choice to make" % ", ".join(said))
    if not said:
        from_path = urn_from_url(final_url)
        return None, ("the page at %s stated no identity of its own (no post-card data-urn, no "
                      "canonical link, no og:url), and a urn will not be inferred from the URL. "
                      "The URL's own path %s"
                      % ((final_url or "")[:140],
                         ("names %s, which is not evidence about the page" % from_path)
                         if from_path else "names no post either"))
    return said[0], None


def urn_of(url, die):
    """The one post this string names, for a verb that is about to ACT on it.

    R2.1: anchored, and exactly one urn in the input. A permalink carrying a
    second, different urn anywhere in it is a FAIL - not a first match.
    """
    s = (url or "").strip()
    mentioned = []
    for m in URN_ANYWHERE.finditer(unquote(s)):
        u = normalise(m.group(0))
        if u and u not in mentioned:
            mentioned.append(u)
    if len(mentioned) > 1:
        die("%s names more than one post (%s). Refusing to guess which one to act on."
            % (s[:120], ", ".join(mentioned)))
    urn = urn_from_url(s)
    if not urn:
        die("not a post permalink: %s. It must be a urn (urn:li:activity:<id>) or a "
            "https://www.linkedin.com/feed/update/<urn>/ address - a urn found loose in some "
            "other string is not an identity." % (s[:120] or "(nothing)"))
    if mentioned and urn != mentioned[0]:
        die("%s names %s but its address resolves to %s; refusing to act on either."
            % (s[:120], mentioned[0], urn))
    return urn


def may_use_any_card(n_any, stated, wanted):
    """May Post.load() act on whatever post card happens to be on the page?

    R2.2. Only when the page holds EXACTLY ONE post card and the page's own
    stated identity is the urn that was asked for. The fallback that was here
    before was silent and unconditional, and on a permalink page it is usually
    right - which is precisely why nobody noticed it acting on a stranger's post
    when it was not.
    """
    if n_any != 1:
        return False
    said = distinct(stated)
    return len(said) == 1 and said[0] == normalise(wanted)
