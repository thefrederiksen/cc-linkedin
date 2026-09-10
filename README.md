# cc-linkedin

Post to a LinkedIn Page through your own signed-in browser. Text, one video or
up to twenty images, post now or schedule. No LinkedIn API, no app review, no
token: it clicks the same buttons you click, in a Chrome that is already
running and already logged in.

## Install

Python 3.11 or newer, on Windows.

```
pip install .                      from a clone
pip install -e .                   working on it
```

That puts a `cc-linkedin` command on your PATH. Playwright comes with it; you do
NOT need `playwright install`, because it drives the Chrome you already have.

`cc_linkedin.py` at the root of this repository stays directly runnable, and
that is a supported way to use the tool, not a leftover:

```
py -3.11 path\to\cc_linkedin.py post ...
```

Both forms run the same code. The file form matters because scheduled jobs call
it by path, with no install and no virtual environment in the picture.

## The 18 commands

Grouped by what they touch. Every writing verb takes `--expect` or an equivalent
guard and refuses rather than guesses; every reading verb prints JSON and treats
an empty result as a failure rather than an answer.

| | |
|---|---|
| **Posting** | `post`, `scheduled`, `unschedule` |
| **Comments and reactions** | `read-post`, `read-comments`, `comment`, `reply`, `delete-comment`, `react`, `unreact`, `delete-post` |
| **Reading and search** | `read-profile`, `read-company`, `search-people`, `search-posts`, `notifications`, `stats` |
| **Invitations** | `withdraw` |

A nineteenth, `selftest`, runs the others against things we own; it is for
developing the tool, not for using it. `cc-linkedin --help` lists them all and
`cc-linkedin <command> --help` explains one.

## What is NOT in 1.0

These commands **do not exist**. They are not hidden, not experimental and not
behind a flag - running one prints an argparse error and stops. They are listed
here because the shape of the tool invites you to assume otherwise.

| Not present in 1.0 | Where it stands |
|---|---|
| `connect`, `message`, `read-inbox`, `read-thread`, `invitations`, `follow`, `unfollow`, `invite-to-follow` | designed, and surveyed against the live site, but not built - [issue #9](https://github.com/thefrederiksen/cc-linkedin/issues/9) |
| `post --profile` (posting as the person rather than as the Page), `edit-post`, `repost` | designed, never surveyed - [issue #10](https://github.com/thefrederiksen/cc-linkedin/issues/10) |

`withdraw` is the only invitation verb in 1.0, and it withdraws only - there is
no way to send an invitation with this tool.

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
cc-linkedin selftest --post <our post> --page ID --page-name NAME \
    --other-profile <a /in/ URL> --other-expect "name=...; headline=...; location=..." \
    --menu-profile <a /in/ URL whose invitation sits behind More> \
    --menu-expect "...; company=none; ..." \
    --pending-profile <a /in/ URL we have already invited who has not answered>
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
holds. Some surfaces are counted on a second counter, `view_self`, which is reported
and NOT capped.

**The test for that is not "is this surface mine". It is "can loading it change
something another person can see."** A read receipt is visible to somebody else,
so a surface that can raise one stays capped however plainly it belongs to you.
Uncapped: your own profile, a Page you administer, notifications, the invitation
manager, and `/messaging/compose/`, which opens no conversation. Capped:
everything else - including your own `/messaging/` inbox, because the list is
the route believed to select a conversation into the reading pane, and that
marks it read. An unrecognised surface is capped, always: a classifier that
guesses generously buys a day of stranger-views the safety number never saw.

**The counter counts views taken through this toolkit, and nothing else.** It is
a floor under the day's real total, not the total. A profile you open by
hand-driving a browser - browser-harness, Playwright by hand, or clicking in
Chrome yourself - spends exactly the same real-world budget against the account
and appears nowhere in `pace.json`. That happened twice on 2026-09-09, to two
different people, neither of whom noticed. If you are surveying a page, run it
through `tools/survey.py`, which registers its view like every read verb here;
if you open one any other way, the number in `pace.json` is short by that many.

`read-profile` answers the connection question in four fields, never one:
`can_connect` (true only where an invite control was positively seen, null where
the page disabled one), `can_connect_reason` in words, `connect_via` and
`connect_url`, plus `invitation_pending` - true where the card carries
LinkedIn's own Pending control, which means an invitation of ours is outstanding
and another cannot be sent. `invitation_pending: false` means this run read the
card and saw no such control; it is not a promise that nothing is outstanding.

Three things worth knowing before you use them:

* `search-posts` gives you `share_url` (a `lnkd.in` link) and `permalink` (the
  real `urn:li:activity` URL, or null). There is no field called `url`, because
  a content-search card genuinely carries no permalink - see `cc_linkedin_kit/search.py` for
  what was measured. `--resolve` follows each short link in the browser to fill
  `permalink`, capped at 10 rows, and that is what feeds a result straight into
  the comment and reaction verbs above.
* `stats` reports `followers` and one row per post, plus `sum_of_posts` - which
  is what it says it is, the sum of the rows in the Page's Content engagement
  table, not LinkedIn's own aggregate. `--days` drives the window control and
  then checks the range the page states, because LinkedIn's own default is
  fifteen days, not thirty.

## Invitations we sent

```
cc-linkedin withdraw <profile URL or slug> [--older-than-months N] [--dump out.json]
cc-linkedin withdraw <profile URL or slug> --expect-name "Their Name" --submit
```

Withdraws ONE outstanding invitation, from the invitation manager's Sent tab.
Staged by default: without `--submit` it finds the row, names the person twice,
reports the age the page displays, and presses nothing.

**It spends something you cannot get back.** LinkedIn restricts inviting the
same person again after a withdrawal, and the RESULT line carries what the live
surface said about that - including saying that it said nothing, which is what
was measured on 2026-09-10. `--expect-name` is required with `--submit`, and
`--older-than-months` refuses unless the age the page DISPLAYS proves at least
that many whole months; an age it cannot parse refuses rather than guesses.

The control is an anchor whose `href` is the feed, so a click the page does not
swallow navigates away and withdraws nothing, silently. The verb therefore
asserts afterwards that it is still on the invitation manager and that the list
is exactly one shorter, with the page's own count agreeing.

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
* Python 3.11 or newer. Playwright arrives with the install above; you do not
  need `playwright install`, because it drives your existing Chrome.
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

## License

MIT. See [LICENSE](LICENSE).
