# Inspection slice 4: claims, safety, and what leaked

Independent static inspection of `47d836b47dd1a02bedb78a83fbbd4a697c179b02`
on 2026-09-09. I did not open LinkedIn or run a verb. I inspected the current
tracked tree and all 34 commits reachable from the local refs. Per the brief, I
did not assess the URN resolver, `kit/selftest.py`, or the read verbs' extraction
logic; I did inspect their side effects and the claims made about them.

`PROVED` means the result follows from committed code, artifacts, or Git
history. `SUSPECTED` means the code creates the opportunity but the external
effect was not observed here.

## Ranked findings

| Rank | Consequence | Status | Finding |
|---:|---|---|---|
| 1 | HIGH - outbound caps can be exceeded while the file says they were obeyed | PROVED | `pace.json` has an unlocked, non-atomic check/action/account sequence and fails open on read or write damage. |
| 2 | HIGH - a public repository can identify people and content that were meant to be anonymous | PROVED | The redactor removed profile slugs and names but left a distinctive third-party headline, organization/content URLs, post IDs/URNs, a job ID, and an address. |
| 3 | HIGH - an accepted operational-safety ruling is not in the implementation | PROVED | The current browser lock still has every defect accepted in inspection ruling R3: early acquisition, non-atomic contents, and release paths that fallible cleanup can skip. |
| 4 | MEDIUM - a command advertised as read-only overwrites user state and changes browser permissions | PROVED | `search-posts` clears/replaces the system clipboard and grants clipboard permissions to the default browser context without resetting them. |
| 5 | MEDIUM - “MEASURED” and ruling language is stronger than its evidence or code | PROVED | The renderer classifier demonstrably mislabels classic pages; repeated-load and fixture claims have no committed repeat evidence; `share_url` and signed-in invariants are not enforced as claimed. |
| 6 | MEDIUM - some reads can be visible to other people or counted by LinkedIn | PROVED navigation; external result partly SUSPECTED | `read-profile` deliberately opens another person's profile, which the accepted design says leaves a “viewed your profile” trace. Notification-seen and content-impression effects were not measured. |

## 1. `pace.json` is not a cross-process safety boundary - PROVED

`Pace` says its file makes caps hold “across sessions and agents”
(`kit/browser.py:152-159`). It does not provide that property.

### Two writers

`before()` loads and checks (`kit/browser.py:202-209`), the caller performs the
external action, and `after()` separately reloads, increments, and saves
(`kit/browser.py:211-216`). There is no reservation, file lock, compare-and-swap,
or atomic update. `_save()` truncates the live file and writes JSON directly
(`kit/browser.py:187-192`).

Concrete interleaving at a comment count of 59:

1. writers A and B both load 59 in `before()` and both pass the cap check;
2. both publish a comment;
3. both load 59 in `after()`, increment their private copy to 60, and save 60.

There have been 61 comments, but the durable counter says 60. Updates to
different fields can also erase each other: A can save a view increment based
on an old snapshot after B saved a comment increment. `last_outbound` and
`last_view` are subject to the same lost-update race, so spacing can fail too.

The per-browser lock is only an incidental partial defence. `BrowserLock` is
keyed by CDP port (`kit/browser.py:89-95`) and is held around a normal `Browser`
run (`kit/browser.py:246-283`). Two cooperative commands on the same port are
serialized. Different ports have different locks while all `Pace` instances use
the same `pace.json`; a direct/out-of-band writer is also outside that lock.
Nothing in `Pace` itself serializes its global file.

The cap check also occurs before the randomized wait. Even if two writers do not
check simultaneously, another writer can consume the last slot while the first
is sleeping; the first does not recheck before acting.

### Crash and damaged-file cases

The outbound callers perform the real action before `Pace.after()`
(`kit/comments.py:285-287`, `303-305`, `332-345`). Profile/company/search
navigations likewise occur between `before_view()` and `after_view()`. A crash,
timeout, process kill, or exception in that interval leaves a real action or
view uncounted. Restarting can repeat it without encountering the cap.

A crash or competing write after the `"w"` open can leave `pace.json` empty or
partial. `_load()` catches every exception and returns `{}`
(`kit/browser.py:180-185`), treating corruption, permission failure, and missing
data alike as a clean zero. The next successful `after()` overwrites the damaged
file with reset counters. This is a fail-open safety instrument.

### Midnight and local-time changes

Day buckets use the process's current local date, recomputed at several points;
no timezone is recorded.

* An action just before midnight can be charged after midnight because accounting
  happens after the action.
* If midnight falls after `after()` creates yesterday's bucket but before
  `_save()` recomputes `today`, `_save()` deletes the increment it is about to
  persist as an old key (`kit/browser.py:188-190`).
* A wait can cross midnight without another cap check on the day in which the
  action actually occurs.
* Moving the OS clock/timezone forward produces a new empty date bucket early
  and deletes the earlier one on save. Moving it backward normally selects a
  previously deleted bucket while retaining, but ignoring, the future-dated
  key. Either direction can reset an effective daily cap within 24 hours.

DST changes that do not change the calendar date do not reset the bucket; the
gap timestamps use epoch seconds. The unsafe boundary is the local date, not
the one-hour DST offset by itself.

## 2. Public-repository leak audit - PROVED

The claim “No third party's name, profile URL or headline appears here or in the
code” (`docs/phase-2-fixes.md:10-13`) is false. The narrower statement that the
first profile-URL leak was caught before commit is supported by Git history.

### What is present

| Committed location | Data left public | Why redaction did not cover it |
|---|---|---|
| `docs/phase-2-fixes.md:36-45`, `205-216` | Profile D's distinctive HR/job-search headline plus 205 connections, identified as a measured third-party profile | This is prose outside the survey redactor. It directly contradicts the file's lines 10-13. |
| `kit/search.py:38-42` | Three exact `lnkd.in` post short links copied from three measured cards | The links are handwritten into a module docstring. Following one can recover the content and author. |
| `kit/search.py:68-74` and `docs/inspection-slice-1-urn.md:48-67` | Exact measured post IDs in `share`/`ugcPost` URL shapes | The IDs were retained as examples and later copied into inspection evidence. |
| `docs/surveys/search-posts-2026-09-09.txt:381-400`, `495`, `732-737`, `797-825`, `887-918` | Organization slugs, three encoded `lnkd.in` links, a job ID, article paths, and a quoted-post URN | Query-value redaction hides selected parameters, not identifiers embedded inside a parameter or path. |
| `docs/surveys/notifications-2026-09-09.txt:492-497`, `552-588` | Numeric organization IDs, event post URNs, and an identifying article slug | Company/content paths are outside the three redacted identifier forms. |
| `docs/surveys/stats-2026-09-09.txt:3-4`, `244-269`, `573-586` | The administered Page ID and its exact post/activity identifiers | These appear to be owner/project fixtures rather than third-party data, but the “safe dump” still preserves stable identifiers. |
| `docs/surveys/company-member-2026-09-09.txt:277`, `304` | Owner business website and a precise Toronto postal-code map URL | This appears to be owner/business data, not an anonymous third party; it is nevertheless unredacted location data. |

The survey text filter is broad, but attribute redaction recognizes only `/in/`
slugs, `ACoA...` member IDs, and a fixed list of query parameters
(`tools/survey.py:78-95`). It has no rule for company paths/IDs, post or event
URNs, jobs, articles, short links nested in `url=`, or map addresses. The claim
that `--out` is the safe public dump (`tools/survey.py:20-26`, `302-303`) is
therefore not supported by its implementation.

Some identifiers above may point to owner-affiliated material. Profile D is
explicitly a third party, and the search/notification identifiers are paired
with redacted actors, so ownership cannot be established from the public dump.
That uncertainty does not make the links anonymous: they are stable lookup keys
to the hidden content and actors.

### What I did not find

In the current 40 tracked files I found no unredacted third-party `/in/` slug,
`ACoA...` member ID, email address, LinkedIn-style `@handle`, personal name, real
message body, or real invitation note. The only concrete profile URL is the
owner's; `/in/someone/` and ellipses are examples. Candidate capitalized
two-word names were manually reviewed rather than treated as automatically
personal. The scan also covered `href`/`aria-label`, company/content paths,
URNs, short links, job/article paths, and location URLs.

The absence checks were tested with positive controls: a fabricated profile
URL, email address, and two-word name each matched its intended detector. This
does not prove that every possible encoding was covered; it proves the reported
zeroes did not come from detectors that never ran or could not match their basic
target.

### Did the retaken surveys replace the first leak?

All eight current survey files were introduced together in commit
`1173f451a8dd2633a4fd0ac21e840f15cb86c30d`; no other reachable commit changes
`docs/surveys` or `tools/survey.py`. The current dumps use `<slug>`, `<memberid>`,
and `<value>` where those three patterns apply. Thus, in the 34-commit local
reachable history, there is no committed earlier dump containing the reported
ten profile URLs. This supports `docs/phase-2-report.md:183-187`'s specific claim
that the first pass was caught before commit.

That proof does not cover untracked scratch files, reflog-only/unreachable
objects, or refs not present locally. More importantly, the retake fixed the
specific profile/member/query leak but did not make the dumps generally safe;
the table above is the residual leak.

## 3. “Read-only” in fact

The code contains no direct click on Connect, Follow, Like, Send, or a
notification card in these six verbs. That negative result came from an
inventory of their click/press sites, not from looking only for known-dangerous
button names.

| Verb | PROVED local/browser action | Externally visible possibility |
|---|---|---|
| `read-profile` | Navigates to the requested profile; may click only the top-card More menu and About expansion (`kit/people.py:357-380`, `420-431`). | The accepted mission explicitly says other-profile reads leave the ordinary “viewed your profile” trace (`docs/MISSION.md:41-44`). I did not independently exercise that platform effect. |
| `read-company` | Navigation and DOM reads; no direct write control found. | Server-side access logging is inherent. No person-facing effect is established here. |
| `search-people` | Navigation and DOM reads; no direct write control found. | No person-facing effect is established here. |
| `search-posts` | Grants permissions, clears the clipboard, opens each card menu, clicks “Copy link to post,” and reads the clipboard (`kit/search.py:177-219`). Optional resolving adds post navigations. | Clipboard loss is direct. Whether search/result/post loads count an impression is SUSPECTED; the repository supplies no network or before/after measurement. |
| `notifications` | Navigates and evaluates card DOM; it does not click a card (`kit/account.py:93-130`). The captured post-load DOM still contains two `nt-card--unread` cards (`docs/surveys/notifications-2026-09-09.txt:188-210`, `242`). | Marking a page/card as “seen,” clearing a badge, or sending a server acknowledgement on load remains SUSPECTED. A single after-load dump is not a before/after or network trace. |
| `stats` | Opens the range control, selects a preset, and can press the first page-global visible button named Update (`kit/account.py:225-278`). | No social write is shown. Persistence of the selected analytics range/account preference is SUSPECTED and unmeasured. |

“Read-only” is therefore defensible only in the narrow sense “does not
intentionally publish/connect/react/message.” It is false as a statement that
the commands do not alter state or create an externally visible trace.

### Clipboard permission and persistence - PROVED

`search-posts` sends `Browser.grantPermissions` for the LinkedIn origin with
`clipboardReadWrite` and `clipboardSanitizedWrite`, without a
`browserContextId` (`kit/search.py:211-219`). In the Chrome DevTools Protocol,
omitting that ID targets the default browser context; the command grants the
listed permissions and rejects the others for the origin. Permission reset is
a separate `Browser.resetPermissions` operation. See the official
[CDP Browser domain](https://chromedevtools.github.io/devtools-protocol/tot/Browser/).

The code never sends that reset. It attaches to an existing browser's default
context (`kit/browser.py:246-280`), closes the created page, and disconnects; it
does not terminate the signed-in Chrome process or destroy its default context.
The permission override is therefore left in that context for later work. This
inspection does not establish survival across a full Chrome restart.

The normal Clipboard API is permission-controlled, and `writeText()` writes to
the system clipboard; see the [W3C Clipboard API](https://www.w3.org/TR/clipboard-apis/).
The code treats the CDP grant as required by aborting if it fails. Whether this
particular browser profile would have allowed the same operation without the
grant was not tested. After the grant, `_copy_link()` first attempts
`writeText('')` and swallows failure, then the menu action replaces the clipboard
with a post URL. The prior clipboard value is never saved or restored.

## 4. Claims and accepted rulings versus current evidence/code

### Renderer classification is a broken instrument - PROVED

`tools/survey.py:210-211` labels a surface `ember` when `[data-urn]` is nonzero
and `react` when it is zero. All eight dumps say `react`. Yet the code's own
measured descriptions call company member view, notifications, and stats
classic surfaces (`kit/people.py:72-81`, `kit/account.py:7-10`, `22-38`), and
their dumps visibly contain Ember/classic selectors. Therefore zero
`[data-urn]` proves only “this probe found no data-urn,” not React rendering.

This does not prove the search/profile surfaces are not React/SDUI: for example,
the content-search dump has a `data-sdui-screen` node
(`docs/surveys/search-posts-2026-09-09.txt:364`). It proves the dump header and
any argument that relies on its binary rule cannot establish “React ONLY.”

### Repetition and semantic measurements are not reproducible - PROVED coverage gap

`kit/search.py:31-49` and `docs/rulings-phase-2.md:51-55` claim four loads and
specific raw-document/token results. `kit/selectors.py:70` says every surface
was measured twice. The repository contains one timestamped dump per surface.
The content-search dump proves one state with six list items, zero activity
links, one feed-update link, six menu buttons, and one SDUI marker
(`docs/surveys/search-posts-2026-09-09.txt:355-364`); it does not contain a
`[data-id]` probe, the six embedded raw-document URNs, or token-distance data.

Likewise, the two people-search dumps prove 10 rows versus 1 row
(`docs/surveys/search-people-2026-09-09.txt:214-216` and
`search-people-self-2026-09-09.txt:107-109`), but the redacted queries, names,
locations, and URLs cannot prove “ten people of the same name,” “first is a
Winnipeg realtor,” or “the owner is absent.” These observations may have
happened; the committed evidence does not let another reader verify them.

### Claimed invariants are not the implemented invariants - PROVED

* `share_url` is documented and ruled “always present” (`kit/search.py:51-52`,
  `docs/rulings-phase-2.md:25-29`), and the ruling requires every row to have a
  non-empty author and `share_url` (`docs/rulings-phase-2.md:43-49`). Production
  code emits `author: None` and/or `share_url: None` per row and fails only when
  every row lacks a share URL (`kit/search.py:234-245`). The self-test ruling is
  outside this slice; the production/output claim is still false.
* `assert_signed_in` claims its matching button is the global navigation's
  identity control and exists only when signed in (`kit/browser.py:297-313`),
  but the locator is page-global and not scoped to a navigation element
  (`kit/browser.py:315-322`). Any visible role=button with the same accessible
  name satisfies it. The phase report itself says the broken-selector test
  proved only that the guard fires, not that an authwall lacks the assumed
  control (`docs/phase-2-report.md:172-175`).
* The stats ruling says headers are asserted before any cell is read
  (`docs/rulings-phase-2.md:85-90`). The single page evaluation reads the header
  and all body cells together (`kit/account.py:159-168`); Python validates the
  header later (`kit/account.py:311-317`). The code does validate before parsing
  or reporting rows, and both header and cells come from the same table, so the
  intended wrong-table protection exists. The literal “before any cell is read”
  claim does not.
* The accepted inspection ruling R3 requires last/exception-safe lock
  acquisition and release plus atomic lock-file creation. Current code acquires
  the lock before Playwright/CDP setup (`kit/browser.py:256-270`), writes the
  lock body directly after `O_EXCL` (`kit/browser.py:105-114`), treats unreadable
  contents as `{}` and waits (`kit/browser.py:98-128`), and can skip release if
  cleanup raises (`kit/browser.py:274-285`). The ruling is accepted but not
  implemented at this revision.

### Claims with direct support found

The stats “member analytics” trap is present in the dump: four matching member
widget items and a 5-impression value are separate from the Content engagement
table and its 48-impression cell (`docs/surveys/stats-2026-09-09.txt:128`,
`233`, `303-325`, `484-590`). The current extraction scopes header and cells to
the same local table object (`kit/account.py:138-168`). Within this slice, I
found no evidence that this particular 5-versus-48 claim was fabricated or that
the member widget can leak into the returned Page numbers.

## Bottom line

The repository can substantiate the narrow claim that the first set of raw
profile URLs was not committed. It cannot substantiate the broader claims that
the committed surveys are public-safe, that all six commands are read-only in
fact, that the pacing file holds caps across agents, or that every fact labelled
MEASURED is reproducible from committed evidence. The highest safety defect is
the pacing state: it is used as an enforcement boundary but treats concurrent,
late, lost, and corrupt state as permission to proceed.
