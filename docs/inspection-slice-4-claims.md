# Inspection slice 4: claims, safety, and what leaked

Independent static inspection updated through committed HEAD
`782885c3838fae855683d6a2f324ddce3ba0e62a` on 2026-09-09. I did not open
LinkedIn or run a verb. I inspected the current 58-file tracked tree and all 47
commits reachable from the local refs. Per the brief, I
did not assess the URN resolver, `kit/selftest.py`, or the read verbs' extraction
logic; I did inspect their side effects and the claims made about them.

R15 was committed while this review was being updated. Section 1 therefore
audits the reservation/atomic-write implementation now at HEAD, not the earlier
unlocked implementation that first triggered the ruling.

No Python interpreter was available (`py -3.11` returned exit 112), so I did
not execute the new unit tests. The Git/history sweeps and positive controls in
this report were run directly; code-path conclusions are static.

`PROVED` means the result follows from committed code, artifacts, or Git
history. `SUSPECTED` means the code creates the opportunity but the external
effect was not observed here.

## Ranked findings

| Rank | Consequence | Status | Finding |
|---:|---|---|---|
| 1 | HIGH - caps or gaps can reset while the file still looks usable | PROVED | R15 fixes the ordinary lost-update/cap race, but malformed state and local-date/timezone changes still reset caps, and concurrent writers can still collapse the required gap. |
| 2 | HIGH - data meant to be anonymous was pushed publicly and remains in reachable history | PROVED | The tip redacts almost all exposed headline/URL/URN data, but history retains it and the new leak test itself contains one real third-party company ID. |
| 3 | MEDIUM - “read-only” can still destroy non-text clipboard state | PROVED conditional path | `search-posts` now restores readable text and resets permissions, but proceeds when the original clipboard is unreadable/non-text or restoration/reset fails. |
| 4 | MEDIUM - “MEASURED” and ruling language is stronger than its evidence or code | PROVED | The renderer classifier demonstrably mislabels classic pages; repeated-load and fixture claims have no committed repeat evidence; `share_url` and signed-in invariants are not enforced as claimed. |
| 5 | MEDIUM - some reads can be visible to other people or counted by LinkedIn | PROVED navigation; external result partly SUSPECTED | `read-profile` deliberately opens another person's profile, which the accepted design says leaves a “viewed your profile” trace. Notification-seen and content-impression effects were not measured. |

## 1. `pace.json`: R15 fixes the lost-count race, but the safety boundary still fails open - PROVED

### Two writers: cap fixed, gap not fixed

The code adds one `pace.json.lock`, makes `_reserve()` check and
increment under it, and atomically replaces the JSON file
(`kit/browser.py:303-340`). A reservation happens after waiting but before the
external action (`kit/browser.py:356-369`). Therefore two writers
at 59 cannot both take the last cap slot, and updates to different fields no
longer overwrite one another. The old 61-actions-recorded-as-60 interleaving is
closed.

The required gap is still not cross-process safe. Both writers read the same
old `last_outbound` outside the lock and finish `_wait()` independently. They
then reserve successive cap slots under the lock and can act at nearly the same
time. `last_outbound` is written only by `after()` after each action
(`kit/browser.py:342-369`). Thus the count can be right while the claimed 45-90
second separation is zero. The same applies to `last_view`. A per-port
`BrowserLock` serializes same-port callers, but different ports share the pacing
file and have different browser locks.

### Crash and damaged-file cases

Reservation changes a crash from undercounting to conservative overcounting. A
crash after `before()` reserves but before the action leaves a used slot even if
no action occurred. A crash after the action but before `after()` still leaves
the reservation counted, so the daily cap does not fail open; however, it leaves
the last-action timestamp stale, allowing the next process to skip the gap.

Atomic replacement means a normal process crash during `_save()` leaves either
the prior complete file or the new complete file. But `_load()` still catches
every exception and returns `{}` (`kit/browser.py:308-313`). A malformed file,
permission/read error, or externally damaged file is treated as a clean zero;
the next reservation can overwrite it and reset every cap and timestamp. The
new lock does not turn an unreadable safety record into a refusal.

### Midnight and local-time changes

Day buckets still use the process's current local date with no stored timezone.

* A reservation immediately before midnight can authorize an action just after
  midnight against yesterday's count.
* `_reserve()` chooses the bucket and `_save()` recomputes `today`; if midnight
  falls between them, `_save()` deletes the reservation as an old key
  (`kit/browser.py:317-339`).
* Moving the OS clock/timezone forward selects a new empty date bucket early and
  deletes the earlier bucket on save. Moving it backward normally selects a
  previously deleted bucket while retaining but ignoring the future-dated key.
  Either direction can reset the effective cap inside 24 hours.

DST changes that stay on the same calendar date do not reset the bucket; gap
timestamps use epoch seconds. The unsafe boundary is the local date, not a DST
offset by itself.

## 2. Public-repository leak audit - PROVED

At the original inspection point, the claim “No third party's name, profile URL
or headline appears here or in the code” was false in the same file that made
it. The current `docs/phase-2-fixes.md:10-35` now admits and describes the
redaction. The narrower statement that the first profile-URL leak was caught
before commit is supported by Git history.

### What was present in reachable public branch history

The following coordinates identify representative reachable revisions; later
tip commits redact most of them. The old objects remain reachable from the
branch history, as accepted ruling R14 itself notes.

| Historical committed location | Data left public | Why redaction did not cover it |
|---|---|---|
| `7817011:docs/phase-2-fixes.md:36-45`, `200-216` | Profile D's distinctive HR/job-search headline plus 205 connections, identified as a measured third-party profile | This is prose outside the survey redactor. It directly contradicted that file's lines 10-13. |
| `7817011:kit/search.py:38-42` | Three exact `lnkd.in` post short links copied from three measured cards | The links were handwritten into a module docstring. Following one can recover the content and author. |
| `47d836b:kit/search.py:68-74` and `7817011:docs/inspection-slice-1-urn.md:48-67` | Exact measured post IDs in `share`/`ugcPost` URL shapes | The IDs were retained as examples and later copied into inspection evidence. |
| `7817011:tests/test_identity.py:20-45`, `89-103` and `7817011:docs/evidence/watched-failing-identity.txt:4-20` | The same real measured post IDs copied into regression fixtures and watched-failure output | These copies arrived after the first inspection pass; redacting only the original prose would have left the identifiers. |
| `1173f45:docs/surveys/search-posts-2026-09-09.txt:381-400`, `495`, `732-737`, `797-825`, `887-918` | Organization slugs, three encoded `lnkd.in` links, a job ID, article paths, and a quoted-post URN | Query-value redaction hid selected parameters, not identifiers embedded inside a parameter or path. |
| `1173f45:docs/surveys/notifications-2026-09-09.txt:492-497`, `552-588` | Numeric organization IDs, event post URNs, and an identifying article slug | Company/content paths were outside the three redacted identifier forms. |
| `1173f45:docs/surveys/stats-2026-09-09.txt:3-4`, `244-269`, `573-586` | The administered Page ID and its exact post/activity identifiers | These appear to be owner/project fixtures rather than third-party data, but the “safe dump” preserved stable identifiers. |
| `1173f45:docs/surveys/company-member-2026-09-09.txt:277`, `304` | Owner business website and a precise Toronto postal-code map URL | This appears to be owner/business data, not an anonymous third party; it was nevertheless unredacted location data. |

At the inspection baseline, attribute redaction recognized only `/in/` slugs,
`ACoA...` member IDs, and a fixed query-parameter list. That is why the table's
other forms survived. Current `tools/survey.py:20-40`, `106-184` no longer calls
the output safe, adds the named forms, and adds a catch-all for 15-or-more digit
content IDs. That materially improves the tip; it cannot retract the history.

Some identifiers above may point to owner-affiliated material. Profile D is
explicitly a third party, and the search/notification identifiers are paired
with redacted actors, so ownership cannot be established from the public dump.
That uncertainty does not make the links anonymous: they are stable lookup keys
to the hidden content and actors.

### What remains at the current tip - PROVED

R13, R17, and R18 removed the distinctive headline/count, the three real short
links, the real post IDs copied into tests and evidence, the organization and
article paths, the job ID, and the postal-code map URL. Current survey dumps use
shape placeholders, and the module docstring uses a short-link shape instead of
a resolvable link.

One known third-party identifier remains: `tests/test_no_leak.py:104` repeats
the exact eight-digit company ID that the notification dump exposed. It appears
as a negative control proving only that the 15-digit content-ID detector does
not match an organization ID. The source-tree tests inventory real short links
and 15-or-more digit runs, not shorter numeric company paths, so they cannot
catch the identifier they have reintroduced. The test's pass would prove its
two shapes absent, not that the tree contains no third-party identifiers.

### What I did not find

Apart from that company ID, in the current 58 tracked files I found no
unredacted third-party `/in/` slug, `ACoA...` member ID, email address,
LinkedIn-style `@handle`, personal name, headline, real message body, real
invitation note, resolvable short link, or real post/content ID. The only
concrete profile URL is the owner's; `/in/someone/` and ellipses are examples.
Candidate capitalized two-word names were manually reviewed rather than treated
as automatically personal. The scan also covered `href`/`aria-label`,
company/content paths, URNs, job/article paths, and location URLs.

The absence checks were tested with positive controls: a fabricated profile
URL, email address, and two-word name each matched its intended detector. This
does not prove that every possible encoding was covered; it proves the reported
zeroes did not come from detectors that never ran or could not match their basic
target.

### Did the retaken surveys replace the first leak?

All eight survey files were introduced together in commit
`1173f451a8dd2633a4fd0ac21e840f15cb86c30d`; the later R13/R17/R18 commits
redact those same files in place. No commit in the current 47-commit reachable
history contains an earlier dump with the reported ten raw profile URLs. This
supports `docs/phase-2-report.md:183-187`'s specific claim that the first pass was
caught before commit.

That proof does not cover untracked scratch files, reflog-only/unreachable
objects, or refs not present locally. The retake fixed the specific
profile/member/query leak, but its first committed “redacted” version still
contained the historical identifiers catalogued above. Tip redaction does not
remove them from reachable history.

## 3. “Read-only” in fact

The code contains no direct click on Connect, Follow, Like, Send, or a
notification card in these six verbs. That negative result came from an
inventory of their click/press sites, not from looking only for known-dangerous
button names.

| Verb | PROVED local/browser action | Externally visible possibility |
|---|---|---|
| `read-profile` | Navigates to the requested profile; may click only the top-card More menu and About expansion (`kit/people.py:408-431`, `463-482`). | The accepted mission explicitly says other-profile reads leave the ordinary “viewed your profile” trace (`docs/MISSION.md:41-44`). I did not independently exercise that platform effect. |
| `read-company` | Navigation and DOM reads; no direct write control found. | Server-side access logging is inherent. No person-facing effect is established here. |
| `search-people` | Navigation and DOM reads; no direct write control found. | No person-facing effect is established here. |
| `search-posts` | Grants permissions, saves readable clipboard text, opens each card menu, clears/replaces the clipboard, then attempts restoration and permission reset (`kit/search.py:195-300`, `320-338`). Optional resolving adds post navigations. | Readable text is restored on the success path. Non-text/unreadable content and restore/reset failures are reported but do not fail the command. Whether loads count an impression is SUSPECTED. |
| `notifications` | Navigates and evaluates card DOM; it does not click a card (`kit/account.py:93-130`). The captured post-load DOM still contains two `nt-card--unread` cards (`docs/surveys/notifications-2026-09-09.txt:188-210`, `242`). | Marking a page/card as “seen,” clearing a badge, or sending a server acknowledgement on load remains SUSPECTED. A single after-load dump is not a before/after or network trace. |
| `stats` | Opens the range control, selects a preset, and can press the first page-global visible button named Update (`kit/account.py:285-344`). | No social write is shown. Persistence of the selected analytics range/account preference is SUSPECTED and unmeasured. |

“Read-only” is therefore defensible only in the narrow sense “does not
intentionally publish/connect/react/message.” The CLI now discloses the
clipboard side effect (`cc_linkedin.py:741-753`), but the README's blanket “All
read-only” still does not convey the conditional state loss or profile trace.

### Clipboard and permission cleanup is conditional - PROVED

`search-posts` sends `Browser.grantPermissions` for the LinkedIn origin with
`clipboardReadWrite` and `clipboardSanitizedWrite`, without a
`browserContextId` (`kit/search.py:279-287`). In the Chrome DevTools Protocol,
omitting that ID targets the default browser context; the command grants the
listed permissions and rejects the others for the origin. Permission reset is
a separate `Browser.resetPermissions` operation. See the official
[CDP Browser domain](https://chromedevtools.github.io/devtools-protocol/tot/Browser/).

R16 now sends that reset in a `finally` (`kit/search.py:288-300`). That closes
the unconditional persistence defect. If reset raises, however, the code logs
and exits successfully, leaving the override's lifetime uncontrolled. The CDP
operation resets permission management for all origins in the default context,
not merely the two permissions just granted; the code does not snapshot any
pre-existing CDP overrides.

The normal Clipboard API is permission-controlled, and `writeText()` writes to
the system clipboard; see the [W3C Clipboard API](https://www.w3.org/TR/clipboard-apis/).
The code treats the grant as required by aborting if it fails. Whether this
browser profile would allow the API without the grant was not tested. R16 saves
clipboard text and restores it in `finally`. If the original cannot be read as
text, or restoration fails, `_restore_clipboard()` returns false but the verb
continues and prints `clipboard=NOT-RESTORED` (`kit/search.py:205-234`,
`320-338`, `373-379`). Thus ordinary text is preserved on success, while an
image, file, unreadable value, or restore error still ends with a successful
read that may have destroyed the original clipboard state.

## 4. Claims and accepted rulings versus current evidence/code

### Renderer classification is a broken instrument - PROVED

`tools/survey.py:299-300` labels a surface `ember` when `[data-urn]` is nonzero
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

* `share_url` is documented and ruled “always present” (`kit/search.py:54-55`,
  `docs/rulings-phase-2.md:25-29`), and the ruling requires every row to have a
  non-empty author and `share_url` (`docs/rulings-phase-2.md:43-49`). Production
  code emits `author: None` and/or `share_url: None` per row and fails only when
  every row lacks a share URL (`kit/search.py:329-342`). The self-test ruling is
  outside this slice; the production/output claim is still false.
* `assert_signed_in` claims its matching button is the global navigation's
  identity control and exists only when signed in (`kit/browser.py:533-550`),
  but the locator is page-global and not scoped to a navigation element
  (`kit/browser.py:551-558`). Any visible role=button with the same accessible
  name satisfies it. The phase report itself says the broken-selector test
  proved only that the guard fires, not that an authwall lacks the assumed
  control (`docs/phase-2-report.md:172-175`).
* The stats ruling says headers are asserted before any cell is read
  (`docs/rulings-phase-2.md:85-90`). The single page evaluation reads the header
  and all body cells together (`kit/account.py:159-168`); Python validates the
  header later (`kit/account.py:387-403`). The code does validate before parsing
  or reporting rows, and both header and cells come from the same table, so the
  intended wrong-table protection exists. The literal “before any cell is read”
  claim does not.
* Accepted inspection ruling R3 now matches committed code. `BrowserLock`
  prepares a complete sentinel and atomically links it into place, and treats an
  unreadable sentinel as broken (`kit/browser.py:116-183`). `Browser.__enter__`
  starts local Playwright work before taking the lock and tears down on every
  `BaseException` (`kit/browser.py:452-490`); `_teardown()` releases in its outer
  `finally` (`kit/browser.py:492-521`). This clears the R3 mismatch present at
  the original inspection point. It does not lock `pace.json`; the locks solve
  different problems.

### Accepted slice-4 ruling status - PROVED

* R13/R17/R18: implemented at tip for the headline, short links, long content
  IDs, organization/article/job/map paths, plus positive artifact checks. The
  original objects remain in reachable public history, and the shorter company
  ID in `tests/test_no_leak.py:104` is outside the new source detectors.
* R16: implemented for readable text and successful cleanup. Unreadable/non-text
  clipboard state and restore/reset failures remain successful conditional
  loss paths, as section 3 shows.
* R15: committed at HEAD with a shared reservation lock and atomic replace,
  closing the lost-update and last-cap-slot races. It does not close the
  concurrent gap, malformed-state, midnight, or timezone cases in section 1.

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
profile URLs was not committed. The current tip is substantially cleaner than
the inspected tip, but reachable public history still contains the leaked data
and one third-party company ID remains in the new leak test. “Read-only” is now
honest in CLI help but still conditional in implementation and broad README
language. The pending pacing code makes cap reservations cross-process safe for
a valid, stable-date file; gaps, malformed state, midnight, and timezone changes
remain fail-open. Several facts labelled MEASURED are still not reproducible
from the committed evidence.
