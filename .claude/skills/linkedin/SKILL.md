---
name: linkedin
description: Drive LinkedIn through the signed-in browser with cc-linkedin 1.0 - post to a Page (text, video, images, now or scheduled), comment, reply, react, delete, read profiles and companies, search people and posts, read notifications and Page stats, and withdraw an invitation we sent. Eighteen commands, no API. Stage first, read the RESULT line. Triggers on "/linkedin", "post to linkedin", "linkedin post", "schedule a linkedin post", "post the video to linkedin", "linkedin page post", "comment on linkedin", "read a linkedin profile", "search linkedin", "linkedin notifications", "page stats", "withdraw a linkedin invitation".
---

# LinkedIn posting

Use the tool. Do not hand-roll browser calls, do not use browser-harness for
posting, do not reach for the LinkedIn API. It encodes a day of measured failure
modes (see its docstring and the README).

**Version 1.0.0. Eighteen commands, listed in full below - and the list of what
does NOT exist is just as important, because the shape of the tool invites you
to assume verbs that are not there.**

Two ways to run it, both supported and both the same code:

```
cc-linkedin <command> ...                                the installed console script
py -3.11 D:\ReposFred\cc-linkedin\cc_linkedin.py <command> ...      the file, no install needed
```

The file form is how Soren's morning video job reaches it, through a shim
outside the repository. Never move or stub that file.

## The one flow

1. The signed-in Chrome must be up. For Center Consulting that is the `cencon`
   browser-harness profile on port 9224:
   `powershell -NoProfile -File "$LOCALAPPDATA/cc-director/connections/bh-profiles.ps1" up cencon`
2. Put the text in a UTF-8 file (max 3000 chars, no YouTube links in a video post).
3. STAGE first. Same command without `--submit`. It attaches, types, verifies,
   screenshots, then discards. Look at the screenshot.
4. Then run it again with `--submit` (post now) or `--schedule "YYYY-MM-DD HH:MM" --submit`.
5. Read the `RESULT` line. `posted` carries the permalink; `scheduled` carries the
   time; `already-posted` means it refused a duplicate. A `FAIL` line means
   nothing was posted and nothing was left behind; the reason names the step.

```
cc-linkedin post --page 107519091 --page-name "CenterConsulting, Inc." ^
    --media D:\path\clip.mp4 --text D:\path\clip.txt --shot D:\path\clip.png
cc-linkedin post ... --submit
cc-linkedin post ... --schedule "2026-09-12 08:30" --submit
cc-linkedin scheduled --page 107519091 --page-name "CenterConsulting, Inc."
cc-linkedin unschedule --page 107519091 --page-name "CenterConsulting, Inc." --match "opening words"
```

Images: repeat `--media` up to 20 times. A video is always alone.

Schedule times are the browser's local time, on LinkedIn's 15-minute grid, at
least 30 minutes out and at most three months. Scheduled posts are listed and
deleted through the composer's own dialog; there is no page for them.

`--shot` brings the tab to the front for the screenshot. Leave it off for a
quiet run; a failed run still writes `<shot>.fail.png` when it can.

## Comments, replies, reactions, deletes (Phase 1, live since 2026-09-09)

All take a POST PERMALINK (never a feed URL) and, for anything that writes,
`--expect "a phrase from the post"` so a wrong URL refuses instead of acting.
Reads print JSON, one record per line, then a RESULT line.

```
cc-linkedin read-post <permalink>
cc-linkedin read-comments <permalink>
cc-linkedin comment <permalink> --expect "phrase" --text "..."        (or --text-file f.txt)
cc-linkedin reply <permalink> --to "words in exactly one comment" --expect "phrase" --text "..."
cc-linkedin react <permalink> --expect "phrase" [--kind like|celebrate|support|love|insightful|funny]
cc-linkedin unreact <permalink>
cc-linkedin delete-comment <permalink> --match "words in exactly one of OUR comments"
cc-linkedin delete-post <permalink> --expect "phrase"                  (our own post only)
cc-linkedin selftest --post <one of Soren's posts> --page 107519091 --page-name "CenterConsulting, Inc." --other-profile <a 1st- or 2nd-degree /in/ URL>
```

Rules the tool enforces, so you do not have to: one run per browser at a time
(a second run waits and says so); 45-90 s between outbound actions and daily
caps, kept in `%LOCALAPPDATA%\cc-linkedin\pace.json` across sessions; a comment
is proven by its row appearing under our name, a reaction by the button's state,
a delete by the row being gone after a reload; `already-commented` /
`already-reacted` refuse duplicates.

Comments on OTHER people's posts are real outreach: the permalink-plus-phrase
guard stops the wrong-post mistake, the pacing stops the burst. Run the
selftest before changing the tool and whenever a verb fails in real use; it
comments on Soren's own post and posts/deletes a throwaway on the Page, and
ends with `RESULT selftest passed=N failed=0`.

## Reading: profiles, companies, search, notifications, Page stats (Phase 2, live since 2026-09-09)

Read-only, JSON out, one record per line then a RESULT line. Use these instead
of improvising browser automation for a one-off read.

```
cc-linkedin read-profile <profile URL or slug> [--expect "phrase"]
cc-linkedin read-company <company URL or slug>
cc-linkedin search-people "query" [--company X] [--title X] [--location X] [--limit N]
cc-linkedin search-posts "query" [--limit N] [--resolve]
cc-linkedin notifications [--limit N]
cc-linkedin stats --page 107519091 --page-name "CenterConsulting, Inc." [--days 30]
```

**An empty read is a FAILURE, never a result.** Every verb checks it is signed
in, checks it landed on the entity asked for, and fails loudly rather than
printing an empty record with a zero exit. If one of these prints FAIL, believe
it - do not go and do the same thing by hand and assume the tool was wrong.

**Reads have their own budget: 80 a day, 3-8 seconds apart.** A profile read
leaves the ordinary "viewed your profile" trace, and high-volume profile viewing
is one of the top triggers for an account warning. Some surfaces cost nothing against that
80 and are counted instead on a separate uncapped `view_self` line in
`pace.json`, so a runaway loop is still visible.

**The test for which is NOT "is this surface Soren's". It is "can loading it
change something another person can see."** A read receipt is visible to
somebody else. So: his profile, his Pages, `notifications`, `stats`, the
invitation manager and `/messaging/compose/` are uncapped - but his own
`/messaging/` inbox is CAPPED, because the list is the route believed to select
a conversation into the reading pane, and that marks it read. Ownership was
never what cost anything. Over the cap the verb stops and says
"tomorrow". The cap is never raised to get a run finished
(`docs/ruling-view-cap-2026-09-09.md`).

**A profile you open by hand is invisible to that counter, and it still costs
the account.** The 80 covers views taken through this toolkit and nothing else.
If you go and read a profile by hand-driving a browser - browser-harness,
Playwright by hand, clicking in Chrome - LinkedIn sees an ordinary profile view
and `pace.json` sees nothing. It has happened twice, to two different agents,
both of whom were being careful. So: use `read-profile` for a profile, and
`py -3.11 tools/survey.py <label> <url>` when you need the raw DOM. Both
register the view. If you do open one by hand anyway, say so out loud - the
number in `pace.json` is now short by that many.

**`read-profile` tells you whether you can invite this person, and whether you
already have.** `can_connect` is true only where an invite control was
positively seen, false where the page offers none, and null where LinkedIn has
disabled one - which is not a no. `can_connect_reason` says which, in words;
`connect_via` and `connect_url` say where the invitation lives. And
`invitation_pending` is true when the card carries LinkedIn's own Pending
control, meaning an invitation of ours is already outstanding and another cannot
be sent. False there means the run read the card and saw no such control - not
that nothing is outstanding.

**`search-posts` does not give you a permalink by default.** A content-search
card carries none - this was measured, not assumed. You get `share_url` (a
`lnkd.in` link) and `permalink: null`. Add `--resolve` (capped at 10 rows) to
follow each short link in the browser and fill `permalink`, which is what you
need before passing a result to `comment`, `react` or `read-post`.

**`stats` numbers come from the Page's Content engagement table.** `sum_of_posts`
is the sum of those rows, NOT LinkedIn's own aggregate - do not report it to
anyone as "the Page's impressions". `--days` defaults to 30 and drives the
window control; LinkedIn's own default is 15, so a screenshot taken by hand may
not be comparable.

## Invitations we sent (withdraw)

The ONLY invitation verb in 1.0. It withdraws; it cannot send.

```
cc-linkedin withdraw <profile URL or slug> [--older-than-months N] [--dump out.json]
cc-linkedin withdraw <profile URL or slug> --expect-name "Their Name" --submit
```

Staged by default: without `--submit` it finds the row in the invitation
manager's Sent tab, names the person twice, reports the age the page displays,
and presses nothing. Stage first, every time.

**A withdrawal spends something that cannot be got back.** LinkedIn restricts
inviting the same person again afterwards. The RESULT line carries whatever the
live surface said about that, INCLUDING saying that it said nothing - which is
what was measured on 2026-09-10. Do not tell Soren the person can be re-invited.

`--expect-name` is required with `--submit`. `--older-than-months N` refuses
unless the age the page DISPLAYS proves at least N whole months; LinkedIn rounds
down, so "3 months ago" proves three, and an age the tool cannot parse refuses
rather than guesses.

The withdraw control is an anchor whose `href` is the feed, so a click the page
does not swallow navigates away and withdraws nothing, SILENTLY. The verb
asserts afterwards that it is still on the invitation manager and that the list
is exactly one shorter with the page's own count agreeing - so trust the RESULT
line, not the fact that the click happened.

## Commands that DO NOT EXIST - do not attempt them

Running one prints an argparse error. Do not improvise them with
browser-harness either: they were left out because they are unproven against
the live site, and two of them send to real people.

| Not present | Where it stands |
|---|---|
| `connect`, `message`, `read-inbox`, `read-thread`, `invitations`, `follow`, `unfollow`, `invite-to-follow` | designed and surveyed, not built - issue #9 |
| `post --profile` (posting as Soren rather than as the Page), `edit-post`, `repost` | designed, never surveyed - issue #10 |

If Soren asks for one of these, say it does not exist and point at the issue.
Do not build a one-off workaround for it.

## Pages this machine posts to

| Page | `--page` | `--page-name` | profile / port |
|------|----------|---------------|----------------|
| CenterConsulting, Inc. | 107519091 | `CenterConsulting, Inc.` | cencon / 9224 |

Soren's personal profile is NOT a Page and is reserved for mindzie content; this
tool does not post there.

## Rules

* Never claim a post went out without the `RESULT posted` line and its URN. The
  composer closing proves nothing; the tool reloads and finds the post by its
  opening line.
* Never run it in the background. Let the log stream.
* If it prints `FAIL`, read the reason and the `.fail.png`. Fix the cause in the
  tool; do not work around it in a wrapper.
* A native "Open" dialog on screen means a click fell through to something that
  opens a file chooser. The tool cancels it and fails the run; report it.
