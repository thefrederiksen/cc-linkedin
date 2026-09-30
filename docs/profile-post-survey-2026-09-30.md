# Survey: the member's own composer (`post --profile`), 2026-09-30

Issue #10 asked for the surface to be measured before any code. These are the
measurements `post --profile` is built on, taken on the live feed in the cencon
profile. Nothing was posted: every run ended in Dismiss + Discard, or in a
hand-over where the person presses Post.

## The composer

* The feed's `Start a post` button opens `/sharing/compose`.
* The composer is a NATIVE `<dialog open aria-labelledby="dialog-header">`.
  `[role=dialog]` does not match it, so the Page composer's selectors are blind
  here, including its Dismiss.
* The header's text begins `Soren Frederiksen` then `Post to Anyone` then
  `Comments: Anyone`. That is the identity check: the header must START with
  the member's name and say `Post to`.
* The editor is a tiptap ProseMirror (`.ProseMirror`): one `<p>` per line, a
  blank line is an empty `<p>`. Joining the paragraphs' text with newlines
  reproduced the 1341-character approved post EXACTLY, hashtags included, when
  typed as insertText runs with one Enter per newline (the Page path's method).
* Buttons in the empty composer: Dismiss, Show Emoji Picker, Media, Expand
  content types, Post (disabled until there is content).

## Media

* `Media` opens the OS file chooser at once - there is no in-page editor first,
  unlike the Page composer. It is pressed only inside Playwright's
  `expect_file_chooser`, which answers the chooser from the page: measured, no
  native `Open` window appeared (the native-dialog guard found none).
* The chooser takes several files (`is_multiple` true).
* After the file is set a second native `<dialog>` opens: `Editor`, `1 of 1`,
  Edit / Tag / Alternative text / Duplicate / Delete / Add, Back, Next.
* Next returns to the composer, which now shows the picture (a `blob:` image,
  laid out at the composer's width) with Edit and Close buttons on it.

## Leaving

* Dismiss on a composer with content raises a THIRD native `<dialog>`: `Save
  this post as a draft?` with Discard and Save as draft. Discard (keyboard)
  closes both.

## Two things that bit the build

* A `Start a post` clicked when the feed is at `domcontentloaded` is visible
  but not wired up: the click is swallowed, no composer, no error. The feed is
  now loaded to `load` and given three seconds first.
* An unresponsive `chrome://newtab/` tab in the shared profile hangs the
  Playwright attach for the full 90 seconds (every other target answered a raw
  CDP evaluate; that one did not). Closing it fixed the attach at once. Not
  fixed in code here - see the pull request.

## Not measured, so not built

* Pressing Post, and finding the published post afterwards on the member's
  activity. `--profile --submit` refuses until that has been measured.
* Video, scheduling, and @mentions on this composer.
