# Inspection slice 1: URN reconstruction

Inspected commit `376b2811ec370da0382e895219b68a5a60092693`. This was a static inspection only; I did not open LinkedIn or exercise the browser.

## Verdict

**Yes. `search-posts --resolve` can emit a well-formed permalink for a different post from the one named by the landed URL, and it can emit a post permalink when the browser did not land on a post at all.**

Severity: **critical if one of the ambiguous URL shapes reaches this code**, because ambiguity is reported as a successful resolution and the result feeds mutating verbs. Confidence: **very high (0.99) in the parser defect and caller-visible behavior**; **medium in which of the demonstrated ambiguous shapes LinkedIn currently emits**, because the repository contains no evidence for those edge shapes and I deliberately did not visit LinkedIn.

The code proves only that some substring of `page.url` matches a permissive regular expression. It does not prove that the extracted URN identifies the page landed on.

## What is proved by the code

The two accepted patterns are unanchored (`kit/search.py:67,74-75`):

```python
ACTIVITY = re.compile(r"urn:li:(?:activity|ugcPost|share):\d+")
POSTS_PATH = re.compile(r"-(activity|share|ugcPost)-(\d+)", re.I)
URN_KIND = {"activity": "activity", "share": "share", "ugcpost": "ugcPost"}
```

Resolution reads the browser's final URL, searches the **entire string** for a full URN first, then takes the first `-kind-digits` occurrence anywhere (`kit/search.py:256-272`):

```python
br.goto(r["share_url"], settle=5)
dest = br.page.url
...
m = ACTIVITY.search(dest)
if m:
    urn = m.group(0)
else:
    m = POSTS_PATH.search(dest)
    if m:
        urn = "urn:li:%s:%s" % (URN_KIND[m.group(1).lower()], m.group(2))
if urn:
    r["permalink"] = "https://www.linkedin.com/feed/update/%s/" % urn
    resolved += 1
```

There is no check here for the LinkedIn host, `/posts/` path, terminal `-kind-id-hash` structure, exactly one candidate, a canonical element, a DOM URN, post identity, HTTP status, or post content. The code also does not always rebuild `urn:li:activity`; it preserves the matched kind and can emit `urn:li:share` or `urn:li:ugcPost`.

### Concrete breaking input 1: a query value wins over the landed post path

Given this final `page.url`:

```text
https://www.linkedin.com/posts/example_topic-share-7503446054340755456-987654321?quoted=urn:li:activity:7409603631332831232
```

the terminal path shape names `urn:li:share:7503446054340755456`, but `ACTIVITY.search(dest)` runs first and finds the query value. The emitted result is therefore:

```text
https://www.linkedin.com/feed/update/urn:li:activity:7409603631332831232/
```

That is a well-formed permalink for B derived from a URL whose `/posts/` path names A. `resolve_error` remains null and `resolved` is incremented. This is a deterministic counterexample to correspondence; whether LinkedIn currently emits an unescaped quoted-URN query parameter is not established by this repository.

### Concrete breaking input 2: a slug/word fragment wins over the terminal suffix

Given:

```text
https://www.linkedin.com/posts/example-activity-7409603631332831232_topic-share-7503446054340755456-987654321
```

there is no full URN, so `POSTS_PATH.search(dest)` returns the **first** match, `-activity-7409603631332831232`. It never reaches the terminal `-share-7503446054340755456-987654321`. It again emits B while the prescribed terminal path shape names A.

A bare numeric run in the slug or words does **not** break this regex by itself: it must occur in a `-activity-<digits>`, `-share-<digits>`, or `-ugcPost-<digits>` motif. The all-digit trailing hash `987654321` also does not by itself confuse the capture; the preceding hyphen ends `\d+`. These are useful controls, but neither rescues the unanchored first-match parser. The regex also fails to require a hyphen or end-of-string after the digits, so even `-share-123abc` is accepted as share `123`.

## Required edge cases

| Case | What the code establishes | What remains unproved |
|---|---|---|
| Numeric run in slug/words | Bare digits are harmless. A kind-plus-digits motif before the real suffix is selected first and can produce the wrong URN, as shown above. | The repo does not show whether LinkedIn's current slug generator can emit that exact motif. |
| All-digit trailing hash | With one otherwise valid terminal suffix, `...-share-222-999999` yields share `222`, not the hash. | The code does not validate that the captured digits are the ID segment or that the remaining suffix is a hash. |
| Repost or quoted post | No repost/quote distinction is made. A full URN in a query string overrides the outer post path; nothing is read from the page to decide outer versus quoted identity. | With exactly one clean suffix, the code alone cannot establish whether LinkedIn assigns that ID to the wrapper/repost, the original, or another entity. |
| Document, newsletter, video, or article under `/posts/` | There is no content-type branch. Any accepted motif anywhere is treated as a post URN; a URL with no such motif gets no permalink. | The repository has no examples proving the ID semantics for each of these page types. A video can be detected only later, after navigation (`kit/comments.py:113-119`); that does not validate the reconstructed identity. |
| Login wall or interstitial | The resolve path calls `goto`, not `read` (`kit/search.py:256-259`). `goto` checks only three security-check phrases (`kit/browser.py:289-295`); the signed-in presence check exists in `read` (`kit/browser.py:297-329`) and is not invoked here. A login/interstitial URL containing a nested post path or raw URN in its query is accepted. | A clean login/interstitial URL with no matching substring is reported as unresolved. The exact redirect parameter encoding LinkedIn currently uses was not measured. |
| 404 | The `page.goto` response/status is discarded. If a 404 remains at a post-shaped URL, the regex accepts it solely from `page.url`. | No 404 was opened, so current LinkedIn 404 routing is unknown. |
| Company page | A clean `/company/acme/` URL is unresolved. A company slug or query containing `-activity-<digits>`, `-share-<digits>`, `-ugcPost-<digits>`, or a full raw URN is accepted because neither host nor path type is checked. | Whether a real copied short link currently redirects to such a company URL is not established. |
| Locale and query suffixes | A locale prefix does not matter if the terminal post suffix is otherwise clean. Query strings are dangerous because both regexes scan them, and the full-URN regex has precedence over the path regex. | Benign tracking queries do not create a mismatch unless they contain one of the accepted motifs. |

The same issue applies beyond LinkedIn: a final URL such as `https://example.invalid/x-share-123/` passes `POSTS_PATH`. The extractor is a whole-string pattern recognizer, not a LinkedIn post-permalink parser.

## The landing is not verified before or after reconstruction

`Browser.goto` returns body text after checking for a small set of security phrases, but the resolver ignores that body and takes only `page.url` (`kit/browser.py:289-295`; `kit/search.py:256-259`). Unlike `Browser.read`, it does not call `assert_signed_in` (`kit/browser.py:297-329`). Thus a normal login wall, interstitial, company page, or 404 is not rejected based on page identity.

Phase 1 then throws away the landed URL and re-canonicalizes whatever matching URN it is given (`kit/comments.py:35-46,54-59`):

```python
ACTIVITY = re.compile(r"urn:li:(?:activity|ugcPost|share):\d+")

def urn_of(url):
    m = ACTIVITY.search(url)
    if not m:
        die(...)
    return m.group(0)
...
self.urn = urn_of(url)
self.url = permalink(self.urn)
self.load(need_rows)
```

That is another unanchored substring check, not an identity check. On load, Phase 1 waits for a comment box, and in the classic rendering it falls back from the card for the requested URN to the first arbitrary post card (`kit/comments.py:67-89`):

```python
self.card = self.page.locator(S.EMBER["card"].format(urn=self.urn)).first
if self.card.count() == 0:
    self.card = self.page.locator(S.EMBER["card_any"]).first
```

Nothing compares the loaded post with the original `search-posts` row. The optional `--expect` guard checks only whether a phrase occurs in whichever post was loaded (`kit/comments.py:60-65`). It is not required by the CLI (`cc_linkedin.py:691-714`), and `delete-comment` and `unreact` do not even accept it. A common phrase or quote would not uniquely identify a post in any case.

The self-test covers the wrong property. It calls a permalink resolved if it merely matches a URN pattern (`kit/selftest.py:529-534`), then feeds the first one to `read-post` and requires only a non-empty author (`kit/selftest.py:536-541`). It never compares that author or post text with the originating search row. A valid but wrong post therefore satisfies both assertions.

## What reaches the caller on failure or ambiguity

Each row starts with `permalink: None` and `resolve_error: None` (`kit/search.py:234-240`). The outcomes are:

- No short link: the row remains, `permalink` is null, and `resolve_error` says there was no short link (`kit/search.py:249-252`). If every card lacks a copied link, the command fails earlier (`kit/search.py:241-245`).
- Navigation exception: the row remains, `permalink` is null, and `resolve_error` contains the first 120 characters of the exception (`kit/search.py:256-261`).
- Final URL with no matching substring: the row remains, `permalink` is null, and `resolve_error` names the destination (`kit/search.py:273-275`).
- Multiple, misplaced, or otherwise ambiguous matches: **there is no ambiguity outcome**. The first match becomes a non-null permalink, `resolve_error` stays null, and the row counts as resolved (`kit/search.py:262-272`).

All rows are printed, followed by `RESULT ... resolved=<n>/<m>` (`kit/search.py:277-282`). Resolution shortfalls do not make the command exit non-zero. A careful caller that checks every row's `permalink` and `resolve_error`, or reconciles `resolved` with the row count, can recognize an explicit failure. A caller that treats exit zero or the presence of a `RESULT` line as success can mistake a failed resolution run for a successful command. More seriously, **no caller can distinguish an ambiguous/wrong resolution from a good one using these fields**: it is deliberately presented as `permalink != null`, `resolve_error == null`, and included in `resolved`.

## Impact

The bad value is precise and plausible, so downstream validation does not contain it. `comment` and `react` act on the post loaded from that value (`kit/comments.py:276-288,324-349`); `delete-post` does likewise (`kit/comments.py:368-386`). Their post-action checks prove that an action occurred on the loaded target, not that this was the search result originally landed on. A wrong stranger's post can therefore receive a comment or reaction. Deleting a stranger's post should fail if LinkedIn omits the Delete command, but a wrong post owned by the signed-in account can reach the delete flow; deleting a matching own comment from the wrong post is also possible.

**Proved:** the parser admits the two wrong-target counterexamples above, does not validate the landing, reports ambiguous extraction as success, and downstream code/tests do not compare the target with the originating result.

**Suspected, not proved here:** current LinkedIn redirects may expose nested post URLs or quoted URNs in query parameters; current slug generation may produce an earlier kind-plus-digits motif; and repost/document/newsletter/video/article URL IDs may have semantics that differ from the assumed `URN_KIND` mapping. Those require live examples or authoritative fixtures, neither of which was available without violating the no-LinkedIn instruction.
