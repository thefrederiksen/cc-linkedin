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
