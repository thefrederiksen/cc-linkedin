# cc-linkedin

Post to a LinkedIn Page through your own signed-in browser. Text, one video or
up to twenty images, post now or schedule. No LinkedIn API, no app review, no
token: it clicks the same buttons you click, in a Chrome that is already
running and already logged in.

```
cc-linkedin post --page 107519091 --page-name "CenterConsulting, Inc." ^
    --media D:\clips\one.mp4 --text D:\clips\one.txt --shot D:\clips\one.png            (stage only)
cc-linkedin post ... --submit                                                            (post now)
cc-linkedin post ... --schedule "2026-09-12 08:30" --submit                              (schedule)
cc-linkedin scheduled --page 107519091 --page-name "CenterConsulting, Inc."
cc-linkedin unschedule --page 107519091 --page-name "CenterConsulting, Inc." --match "opening words"
```

## Comments, reactions, deletes

```
cc-linkedin read-post <permalink>                       JSON: author, text, media, counts
cc-linkedin read-comments <permalink>                   JSON per comment: id, author, url, text, when, is_reply
cc-linkedin comment <permalink> --expect "phrase" --text "..."
cc-linkedin reply <permalink> --to "words in one comment" --expect "phrase" --text "..."
cc-linkedin react <permalink> --expect "phrase" --kind like|celebrate|support|love|insightful|funny
cc-linkedin unreact <permalink>
cc-linkedin delete-comment <permalink> --match "words in one of our comments"
cc-linkedin delete-post <permalink> --expect "phrase"
cc-linkedin selftest --post <our post> --page ID --page-name NAME \n    --other-profile <a /in/ URL> --other-expect "name=...; headline=...; location=...; \n        company=...; degree=...; primary=...; can_connect=...; connections=..." \n    --menu-profile <a /in/ URL whose invitation is behind More and whose top card states \n        no employer> --menu-expect "...; company=none; ..."
```

Every writing verb refuses unless `--expect` is found in the post, waits its
turn for the browser (one run per Chrome, lock in `%LOCALAPPDATA%\cc-linkedin`),
paces itself (45-90 s between outbound actions, daily caps), and proves the
result before printing RESULT. `selftest` runs the whole chain on our own post
and a throwaway Page post; three consecutive clean runs is the bar for a change.
See `docs/PLAN.md` for the full toolkit plan and `docs/plan.html` for the same
with mock-ups.

## Reading people, companies, search, notifications, Page stats

```
cc-linkedin read-profile <profile URL or slug> [--expect "phrase"]
cc-linkedin read-company <company URL or slug>
cc-linkedin search-people "query" [--company X] [--title X] [--location X] [--limit N]
cc-linkedin search-posts "query" [--limit N] [--resolve]
cc-linkedin notifications [--limit N]
cc-linkedin stats --page ID [--page-name NAME] [--days 7|15|30|0]
```

All read-only, all JSON. The rule the whole block hangs on: **a read that comes
back empty is a failure, never a result.** Every verb asserts the signed-in
identity control is PRESENT before it reads, asserts it landed on the entity it
was asked for, and names its required fields; zero rows from a search or from
notifications is a FAIL, because a broken selector and an empty result set look
identical from here and the broken selector is far more likely.

Reads are paced on their OWN clock - 3 to 8 seconds apart, 80 a day - so a
profile read never makes the next comment wait 90 seconds. One view is a profile
or a company page opened, or one page of search results however many cards it
holds. `notifications` and `stats` cost nothing: they are our own screens.

Two things worth knowing before you use them:

* `search-posts` gives you `share_url` (a `lnkd.in` link) and `permalink` (the
  real `urn:li:activity` URL, or null). There is no field called `url`, because
  a content-search card genuinely carries no permalink - see `kit/search.py` for
  what was measured. `--resolve` follows each short link in the browser to fill
  `permalink`, capped at 10 rows, and that is what feeds a result straight into
  the comment and reaction verbs above.
* `stats` reports `followers` and one row per post, plus `sum_of_posts` - which
  is what it says it is, the sum of the rows in the Page's Content engagement
  table, not LinkedIn's own aggregate. `--days` drives the window control and
  then checks the range the page states, because LinkedIn's own default is
  fifteen days, not thirty.

## How it works

Playwright, used as a library, attaches to Chrome over its remote debugging
port (default 9224) and opens one background tab. In that tab it opens the
Page's composer directly (`/admin/page-posts/published/?share=true`), proves the
composer names the right Page and is empty, sets the file on the composer's own
file input, waits until the media editor names that file, presses Next, proves
the media survived (Remove media, and Play for a video), inserts the text and
reads it back character for character, then presses Post or fills the schedule
dialog and presses Schedule. It then waits for the page's own upload traffic to
finish before reloading and finding the post by its opening line.

Without `--submit` all of that happens and the composer is then discarded.
That is the recommended first run for any new text or media.

Every step is a presence check that names what it expects. A missing thing is a
`FAIL` line and exit 1, after the composer is discarded and the tab is closed.
Nothing is left behind: no draft, no extra tab, no native file dialog.

## Output contract

```
RESULT staged file=<names> shot=<png> seconds=<n>
RESULT posted file=<names> urn=urn:li:activity:<id> url=https://www.linkedin.com/feed/update/urn:li:activity:<id>/ seconds=<n>
RESULT scheduled file=<names> when="YYYY-MM-DD HH:MM" listed="<as LinkedIn shows it>" seconds=<n>
RESULT already-posted file=<names>
RESULT unscheduled when="<as LinkedIn shows it>"
FAIL <reason>                       exit code 1
```

`already-posted` means the text's opening line is already on the published
list; the tool refuses to post it twice.

## Requirements

* Windows (the native-dialog watchdog uses Win32; everything else is portable).
* Python 3.11 and `pip install playwright` (no `playwright install` needed, it
  drives your existing Chrome).
* A Chrome started with `--remote-debugging-port=9224 --user-data-dir=<its own dir>`
  and signed in to LinkedIn as an admin of the Page. Chrome 136+ refuses remote
  debugging on its default profile directory, so use a dedicated one.

## Things that were learned the hard way

All measured on the live page on 2026-09-09. They are the reason the tool is
shaped the way it is; the module docstring in `cc_linkedin.py` carries the
detail.

* The video is uploaded AFTER the Post click, from inside the page. Navigate away
  and nothing is posted. The published list does not update live either.
* The composer's "Upload from computer" button opens a native OS dialog that no
  browser automation can close. The file goes on the hidden input instead, which
  is what every browser-based LinkedIn poster does (Selenium `send_keys`,
  Playwright `set_input_files`, Puppeteer `uploadFile`: all the same CDP call).
* The discard prompt's Discard button sits exactly over the admin page's Photo
  button. A mouse click that lands late opens Photo's file chooser. Dismiss and
  Discard are therefore pressed with the keyboard.
* A Page keeps one server-side draft per admin and puts it back into the next
  composer. The tool discards a restored draft once and stops if it comes back.
* Scheduled posts have no page of their own. They live in a dialog reached from
  the composer (Schedule post, then "View all scheduled posts"), each row with an
  actions menu: Post now, Modify schedule, Edit post, Delete post. `scheduled`
  and `unschedule` go through that dialog. The date field is a datepicker that
  throws typed text away; the calendar's day buttons are the control.
* Media first, then text. Leaving the media editor remounts the text editor.
* One `insertText` with newlines inside multiplies them. Text goes in as runs
  with one Enter per newline.

## Skill

`.claude/skills/linkedin/SKILL.md` tells an agent how to use this. Point your
global `linkedin` skill at it.
