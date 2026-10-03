# Ruling: the Unread filter's draft route is uncapped

The owner's, 2026-10-03, on the question the review of `read-inbox` left open.

## The question

`read-inbox --unread` presses the conversation list's own Unread filter. Measured
on 2026-10-03, that moves the address to

```
https://www.linkedin.com/messaging/thread/new/?filter=unread
```

`surface_kind` did not recognise that path, so it fell to the capped `view`
counter - the safe default for anything unrecognised. The verb registered the
navigation there, one capped view per `--unread` run, and said why: nothing had
ruled the route uncapped, and a verb does not get to rule it.

## The ruling

**The route is `view_self`: counted, not capped.** It is the same decision, by the
same test, as the compose route in `ruling-view-cap-2026-09-09.md` and the A2
correction recorded in `cc_linkedin_kit/browser.py`.

The test is not "is this surface the owner's". It is **"can loading it change
something another person can see."** Measured on the live page, 2026-10-03, on
three separate runs:

* the reading pane holds an empty new-message draft, with its recipient field
  present and no message list;
* no conversation row is selected;
* the address carries no conversation id - `new` is not one;
* every row that was unread before the filter was pressed is still unread, and
  still on the list, at the end of the run.

Nothing is marked read, so no read receipt can be shown to anyone. Loading it
tells nobody anything.

## What it covers, exactly

The path `/messaging/thread/new/` and nothing else, matched EXACTLY on the
parsed path, like the compose route. A prefix match would swallow
`/messaging/thread/<id>/`, which opens a conversation and stays capped. The
query string is not part of the match, so the ruling covers the draft whatever
filter LinkedIn puts on it - all of them render the same empty draft.

Pinned in `tests/test_messaging_surface_views.py`, including the cases that must
stay capped: a real thread, a thread id that merely begins with `new`, and the
draft path hidden under another path.

## What it does not change

* `/messaging/` (the bare list) stays capped until somebody measures that
  loading it opens no conversation.
* A thread stays capped. `read-thread` costs one capped view, always.
* No cap was raised. This moves one measured surface to the counter its effect
  belongs on.
