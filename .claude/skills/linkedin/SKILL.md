---
name: linkedin
description: Post to a LinkedIn Page through the signed-in browser with cc-linkedin - text, video, images, now or scheduled. One command, stage first, read the RESULT line. Triggers on "/linkedin", "post to linkedin", "linkedin post", "schedule a linkedin post", "post the video to linkedin", "linkedin page post".
---

# LinkedIn posting

Use the tool. Do not hand-roll browser calls, do not use browser-harness for
posting, do not reach for the LinkedIn API. The tool is
`D:\ReposFred\cc-linkedin\cc_linkedin.py`, on PATH as `cc-linkedin`, and it
encodes a day of measured failure modes (see its docstring and the README).

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
is one of the top triggers for an account warning. `notifications` and `stats`
cost nothing - they are Soren's own screens. Over the cap the verb stops and
says "tomorrow".

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
