# Inspection slice 3: the read verbs

Inspected revision: `50583e465d7d909a20be0bcb0c15a00a34984719`.

This is a read-only static inspection of `kit/people.py`, `kit/account.py`,
`kit/search.py`, and `kit/browser.py`. I did not open LinkedIn, run a browser,
or use `kit/selftest.py`. Per the requested boundary, I did not re-review the
`search-posts --resolve` URN resolver. I treated the builders' reports as claims,
not evidence; quotations below are from the implementation.

`PROVED` means the result follows from the checked-in control flow. `SUSPECTED`
marks a live-page, browser, locale, or timing precondition that was not observed
because the page was deliberately not opened.

## Ranked findings

### 1. CRITICAL — PROVED: the browser lock is not released on every exit path

The normal `with Browser(...)` path is substantially sound, but the universal
claim is false. The lock is acquired before several fallible entry operations,
and only the CDP-connect failure has local cleanup:

```python
# kit/browser.py:256-271
def __enter__(self):
    if open_file_dialogs():
        die("a native 'Open' file dialog is already on screen; close it first")
    self.lock.__enter__()
    self._pw = sync_playwright().start()
    try:
        self.browser = self._pw.chromium.connect_over_cdp(...)
    except PWError as exc:
        self.lock.__exit__(None, None, None)
        die(...)
    ctx = self.browser.contexts[0]
    root = self.browser.new_browser_cdp_session()
    with ctx.expect_page(timeout=15000) as opened:
        root.send("Target.createTarget", ...)
```

Concrete breaking cases: `sync_playwright().start()` raises; the connected
browser has no context and `contexts[0]` raises; CDP session creation fails; or
`expect_page`/`Target.createTarget` times out. In each case acquisition at line
259 succeeded, `__enter__` never returned, and no `__exit__` is invoked by the
`with` statement. The lock file remains.

Cleanup also puts release after another fallible call:

```python
# kit/browser.py:274-285
def __exit__(self, *exc):
    try:
        if self.page and not self.page.is_closed():
            self.page.close()
    finally:
        try:
            self.browser.close()
        finally:
            self._pw.stop()
            self.lock.__exit__(None, None, None)
            if close_file_dialogs("the run"):
                die(...)
```

If `_pw.stop()` raises—for example after a renderer/browser/CDP crash—the lock
release on the next line is skipped. An interrupt arriving during entry or
before line 283 during cleanup has the same result. Lock removal errors are then
silenced:

```python
# kit/browser.py:130-134
def __exit__(self, *exc):
    try:
        os.remove(self.path)
    except OSError:
        pass
```

There is a second wedge path if the sentinel is created but its JSON is not
fully written. An unreadable lock becomes `{}`, which has no PID and is never
classified as dead:

```python
# kit/browser.py:98-103, 110-127
def _holder(self):
    try:
        ...
        return json.load(f)
    except Exception:
        return {}
...
self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
os.write(self.fd, json.dumps({...}).encode())
os.close(self.fd)
...
pid = holder.get("pid")
if pid and not _pid_alive(pid):
    os.remove(self.path)
...
if time.time() > deadline:
    die("gave up waiting ...")
```

A crash or write error between lines 110 and 113 can therefore leave a blank or
partial sentinel. Every later session waits 900 seconds, exits, and leaves it in
place again because `pid` is absent.

What is sound: an exception raised *inside an already-entered with-block*,
including `die()` (`SystemExit`) or a body-level `KeyboardInterrupt`, invokes
`Browser.__exit__` and normally releases the lock. A hard process crash after a
complete lock record is normally recovered on the next run by the dead-PID
branch at lines 118-121. Neither fact covers entry failures, cleanup failures,
or malformed sentinels.

### 2. HIGH — PROVED: stats can turn an empty or unreadable table body into a successful zero

The member-analytics trap itself is avoided correctly. Header and cells come
from the same local `table` object, not from later whole-page number locators:

```javascript
// kit/account.py:137-140, 165-167
const heads = [...document.querySelectorAll('h1,h2,h3')];
const ce = heads.find(h => /Content engagement/i.test(h.innerText || ''));
const sec = ce ? ce.closest('section, div[class*="card"]') : null;
const table = sec ? sec.querySelector('table') : null;
...
header: table ? [...table.querySelectorAll('th')].map(...) : null,
rows: table ? [...table.querySelectorAll('tbody tr')].map(tr =>
        [...tr.querySelectorAll('td')].map(...)) : null
```

The Python assertion checks that exact table's headers:

```python
# kit/account.py:304-317
if not d["hasSection"]:
    die(...)
if d["header"] is None:
    die("the 'Content engagement' section has no table in it")
header = d["header"]
missing = [c for c in REQUIRED_COLUMNS if c not in header]
if missing:
    die(...)
```

Thus, for the measured shape described in the source—the member widget is a
`.member-analytics-addon-summary__list-item` list, not this table—the header
assertion cannot pass and then fetch an engagement number from that widget. The
specific 5-versus-48 mix-up is not present. This part is sound.

`followers` is the deliberate numeric exception: it is not an engagement-table
metric and is read from the Page header. Its scope is weaker than the comment
claims, because it can climb eight ancestors from the `h1` and search every leaf
below each ancestor:

```javascript
// kit/account.py:141-158
const h1 = document.querySelector('h1');
let followers = '';
if (h1) {
  let node = h1;
  for (let up = 0; up < 8 && node && !followers; up++) {
    node = node.parentElement;
    ...
    for (const e of node.querySelectorAll('*')) {
      if (e.children.length === 0 && /^\s*[\d,]+\s+followers?\s*$/i.test(e.innerText || '')) {
        followers = e.innerText.trim();
        break;
      }
    }
  }
}
```

SUSPECTED breaking case: an A/B layout removes the Page's nearby follower leaf,
while an outer ancestor reached within eight steps contains another card's
`"12,345 followers"`. The first such descendant becomes the Page follower
count. This cannot import the member widget's *impressions*—the text must say
followers—but it can import a follower count from the wrong card. The broad
ancestor behavior is PROVED; whether the live hierarchy reaches such a card is
not.

The assertion proves only schema presence, however. It does not prove that a
data row or a number is present:

```python
# kit/account.py:332-355
posts = []
for row in d["rows"] or []:
    if len(row) < len(header):
        continue
    ...
    rec[col.lower()] = None if raw in ("-", "") else to_int(...)
    posts.append(rec)
...
sum_of_posts[key] = {"value": sum((p.get(key) or 0) for p in posts),
                     "source": SUM_SOURCE}
```

Finally the human result line manufactures a zero when the aggregate is absent:

```python
# kit/account.py:367-369
print("RESULT stats ... posts=%d impressions=%d"
      % (..., len(posts),
         sum_of_posts.get("impressions", {}).get("value", 0)))
```

Concrete breaking cases:

- The correct table and headers render but `tbody` is empty after the range
  refresh. The verb exits successfully with `posts: []`, no impressions entry in
  `sum_of_posts`, and `RESULT ... impressions=0`.
- Every row is temporarily short while the renderer hydrates. Lines 335-336
  silently discard all of them and reach the same successful result.
- A post's Impressions cell is `"-"` or `""`. It becomes `None`, then `(None or
  0)` contributes a literal zero to the aggregate.

These are precisely empty reads being certified by a header presence that
covers the wrong property. A malformed non-empty numeric string does fail via
`to_int`; empty numeric data does not.

### 3. HIGH — PROVED control flow; SUSPECTED live triggers: `can_connect` can guess false or true

Positive invite identification uses only a particular URL fragment or an
English accessible label:

```python
# kit/people.py:324-331
def _invite(controls):
    for c in controls:
        if S.INVITE_HREF in (c.get("href") or "") or S.INVITE_ARIA.match(c.get("aria") or ""):
            return c
    return None
```

If it is not found on the top card, the menu gets a fixed 1.5 seconds and one
item is taken as proof of the whole menu:

```python
# kit/people.py:357-385
more = br.page.locator(S.PROFILE_TOPCARD).first.get_by_role(
    "button", name=S.PROFILE_MORE_NAME)
...
time.sleep(1.5)
items = br.page.evaluate(MENU_JS, S.PROFILE_MENU_ITEM)
proof = any(S.PROFILE_MENU_PROOF.lower() in (i["text"] or "").lower() for i in items)
if not proof:
    ...
    die(...)
item = _invite(items)
...
if item:
    return True, ...
return (False, "no invite control ...", None, None)
```

The menu query itself is page-global, not scoped to the menu opened from this
top card:

```javascript
// kit/people.py:180-186
(sel) => {
  ...
  return [...document.querySelectorAll(sel)].filter(vis).map(e => ({
      text: clean(e.innerText), aria: e.getAttribute('aria-label') || '',
      href: e.getAttribute('href') || ''}));
}
```

Concrete cases implied by that control flow:

- An A/B rendering keeps a visible Connect control but changes both the
  `custom-invite` URL and `Invite <name> to connect` aria-label. `_invite` misses
  it. If More renders `About this member` and no recognized invite, the verb
  returns `can_connect: false` even though Connect is on the card.
- A lazy menu renders `About this member` at 1.5 seconds and its Connect item at
  1.8 seconds. The proof passes, the incomplete absence is believed, and the
  verb returns false. Presence of one stable item proves that *a* menu rendered;
  it does not prove every menu item rendered.
- A disabled or busy Connect control retains either recognized marker. The code
  never checks `disabled`, `aria-disabled`, or enabled state and returns true.
- Another visible menu contributes `About this member` while the target menu is
  incomplete; the global query lets the unrelated item satisfy `proof`.

SUSPECTED: those precise DOM/timing states were not observed live. PROVED: if
any occurs, the stated false/true result follows.

What is sound: no More button, zero items, or a menu without the English proof
item fails loudly instead of returning false. Consequently a straightforward
locale change (`More` or `About this member` translated) and a wholly lazy menu
usually fail closed. The unsafe lazy case is the split render where the proof
item arrives before the invite item.

### 4. HIGH — PROVED control flow; SUSPECTED redirect: stats does not prove it read the requested Page

The only final-URL check is for the generic analytics path, and page-name
matching is optional:

```python
# kit/account.py:285-303
def stats(a):
    ...
    final = br.read(ANALYTICS_URL % a.page, "the analytics for Page %s" % a.page, settle=10)
    if "/admin/analytics" not in final:
        die(...)
    ...
    if a.page_name and d["pageName"] != a.page_name:
        die(...)
```

The output then copies the requested value rather than a value read back from
the page:

```python
# kit/account.py:357-363
rec = {
    "kind": "page_stats", "page": str(a.page), "name": d["pageName"],
    ...
}
```

Concrete breaking case: a bad or unauthorized `--page A` is redirected to
`/company/B/admin/analytics/...`, or to the default administered Page's analytics
screen. With no `--page-name`, the generic path, non-empty `h1`, table, and range
all pass, and the record labels B's numbers as page A. The redirect behavior is
SUSPECTED; the absence of a Page-ID/slug assertion and the resulting
mislabeling are PROVED.

### 5. HIGH — PROVED guard gaps: not every relevant transition reasserts identity, and the assertion is not nav-scoped

All six implemented initial page loads are guarded by `read()`:

```python
# kit/browser.py:324-329
def read(self, url, where, settle=6):
    self.goto(url, settle=settle)
    self.assert_signed_in(where)
    return self.page.url
```

The call sites are `kit/people.py:466` (profile), `kit/people.py:584` (company
member view), `kit/search.py:124` (people search), `kit/search.py:222` (content
search), `kit/account.py:99` (notifications), and `kit/account.py:289` (Page
analytics). In particular, read-company does not make an unguarded second hop:

```python
# kit/people.py:580-587
url = S.COMPANY_MEMBER_VIEW % key
...
final = br.read(url, "the company page %s" % key, settle=7)
...
if "viewAsMember=true" not in final:
    die(...)
```

Notifications likewise has no later navigation after its guarded `read()`.
Those two requested surfaces are sound.

The stats time-range drive is the additional transition that has no subsequent
identity check:

```python
# kit/account.py:232, 258, 274-278, 294-298
br.page.locator(RANGE_TRIGGER).first.click(timeout=10000)
...
option.click(timeout=8000)
...
update = br.page.get_by_role("button", name=re.compile(r"^\s*Update\s*$")).first
...
br.press(update, "Update (time range)")
...
_set_window(br, days)
time.sleep(2)
d = br.page.evaluate(STATS_JS)
```

PROVED: neither the preset click nor the fallback Update press is followed by
`assert_signed_in`. SUSPECTED: whether either action performs a document
navigation, or an auth-expiry transition in the current LinkedIn rendering.
The empty-table path in finding 2 means later extraction is not by itself an
adequate substitute for the missing identity assertion.

The assertion also does not actually scope its claimed presence to global
navigation:

```python
# kit/browser.py:36-37, 315-322
# the signed-in identity control, both renderings
ME_BUTTON = re.compile(r"(^|\s)Me$")
...
n = self.page.get_by_role("button", name=ME_BUTTON).count()
...
if n == 0:
    die(...)
return n
```

Concrete constructed case: a signed-out/error page containing an ordinary
accessible button named `Message Me` satisfies the regex and page-global role
query even though no global-nav identity control exists. This is a PROVED hole
in the assertion. Whether LinkedIn currently serves such a signed-out page is
SUSPECTED.

### 6. MEDIUM — PROVED: search paging does not miss the guard; it does not exist

The accepted limit promises a range that can exceed one results page:

```python
# kit/search.py:95-101
n = int(getattr(a, "limit", None) or 25)
...
if n > 100:
    die("--limit is %d; the hard cap for %s is 100 results in one run" % (n, what))
return n
```

But each search performs one guarded navigation, one DOM extraction, and one
slice of the currently rendered rows:

```python
# kit/search.py:121-130
with Browser(a.port) as br:
    pace.before_view("a people search")
    final = br.read(url, "the people search for %r" % q, settle=8)
    pace.after_view()
    ...
    rows = br.page.evaluate(PEOPLE_JS, ...)
    rows = [r for r in rows if r["name"] and "/in/" in r["url"]][:limit]
```

Content search has the same shape at `kit/search.py:221-232`. There is no Next
control, page-number loop, scroll-until-limit loop, or further `before_view` /
`after_view` pair. Thus there is no paging navigation on which
`assert_signed_in` could be missing.

Concrete breaking case: a query has more results beyond the currently rendered
first page and the caller requests `--limit 100`. The command prints the current
page only and reports success; it does not say the requested ceiling could not
be reached. The existence of such a multi-page result is SUSPECTED for any
particular query, but the one-page control flow is PROVED.

The row census also fails open on partial extraction. `PEOPLE_JS` drops cards
without its name anchor (`kit/search.py:79-91`), `POSTS_JS` drops list items
without its menu (`kit/search.py:152-165`), and notifications filters out empty
card readings before checking only whether anything remains:

```python
# kit/account.py:103-106
rows = br.page.evaluate(NOTIFICATIONS_JS, S.NOTIFICATION)
rows = [r for r in rows if r["text"]][:limit]
if not rows:
    die(...)
```

Ten selected notification cards of which one has hydrated text and nine are
temporarily blank become one successful notification, not a failed nine-card
read. The all-empty case fails correctly; partial emptiness is silently erased.

### 7. MEDIUM — PROVED: European decimal commas are silently inflated; other requested forms are handled explicitly

The parser removes every comma and every plus sign before deciding what the
number means:

```python
# kit/people.py:103-115
def to_int(raw, what):
    if raw is None:
        die(...)
    t = str(raw).strip().replace(",", "").replace("+", "")
    m = re.match(r"^(\d+(?:\.\d+)?)\s*([KMB])?$", t, re.I)
    if not m:
        die(...)
    n = float(m.group(1))
    if m.group(2):
        n *= {"K": 1e3, "M": 1e6, "B": 1e9}[m.group(2).upper()]
    return int(round(n))
```

Applying those transformations gives:

| Input | Result | Disposition |
|---|---:|---|
| `1.2K` | `1200` | correct |
| `1.2M` | `1200000` | correct |
| `12.5K` | `12500` | correct |
| `1,234` | `1234` | correct |
| `1 234` (internal NBSP) | exit 1 through `die()` | fails closed; it does not become null |
| `1,2K` (European decimal comma) | `12000` | silently wrong; intended `1200` is inflated 10x |
| `1,234+` | `1234` | accepted; the lower-bound marker survives only in callers' `_raw` field |
| `1.2K+` | `1200` | accepted |

The European-comma behavior is not an ambiguous failure: `replace(",", "")`
turns `1,2K` into `12K`, which matches. Also, because plus removal is global
rather than trailing-only, malformed `12+3` becomes `123` silently. Apart from
those normalization collisions, unparseable values fail rather than returning
null. The stats caller separately converts `"-"` and `""` to null before this
function sees them, as covered in finding 2.

### 8. LOW — PROVED fail-closed behavior; SUSPECTED false-positive shape: `primary_button` is brittle but usually loud

Every visible top-card anchor/button is called filled if *any descendant* has
one exact computed background color:

```javascript
// kit/people.py:156-168
const controls = [...card.querySelectorAll('a, button')].filter(vis).map(e => {
  ...
  return {...,
          filled: [e, ...e.querySelectorAll('*')]
              .some(n => getComputedStyle(n).backgroundColor === cfg.fill), ...};
}).filter(c => c.text || c.aria);
```

The decision then requires exactly one:

```python
# kit/people.py:297-317
filled = [c for c in card["controls"] if c["filled"]]
if len(filled) != 1:
    die("expected exactly one control painted %s ..." % ...)
...
return _label(p), [_label(c) for c in row]
```

What breaks it and how it behaves:

- A theme/restyle/A-B change from `rgb(10, 102, 194)` to another color, a
  gradient, or a different element outside the control subtree normally yields
  zero matches and a loud failure. Multiple matches also fail. This is brittle
  availability, but it does not guess.
- Locale alone does not affect the color comparison. It changes the reported
  label and can break the English `More`/menu proof logic in finding 3.
- A disabled or busy control is not checked for enabled state. If its color and
  label/aria remain, it is still reported as primary; if a spinner removes the
  label/aria or the disabled style changes the color, the likely result is a
  loud zero-match failure.
- SUSPECTED false-positive case: a theme changes the real primary fill while
  exactly one non-primary control retains the old blue on an inner badge/icon.
  The descendant-wide test marks that one control, `len(filled) == 1`, and the
  code reports the wrong primary without failing. The consequence follows from
  the code; existence of that rendering was not measured.

Overall, the ordinary restyle case is soundly fail-closed. The stronger claim
that the exact RGB identifies the semantic primary in every rendering is not
proved.

## Bottom line

The measured member-widget mix-up is genuinely blocked: engagement headers and
cells share one table scope. The most consequential remaining quiet reads are
elsewhere: empty analytics rows/cells become zero-like success, a partially
rendered More menu can become `can_connect: false`, stats can label a redirected
Page with the requested ID, partial search/notification cards are filtered out,
and a European decimal comma is accepted with the wrong magnitude. Initial
navigations are guarded, including notifications and the company member-view
URL; the stats range transition is not re-guarded, and search paging is absent
rather than guarded. The lock is safe on normal with-block unwinding but not on
all entry and cleanup failures, so it cannot support the claim that every exit
path leaves the shared browser available.
