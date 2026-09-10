# Phase 3 survey, second pass: the surfaces section 10 said were unmeasured

Measured 2026-09-10, between 07:22 and 07:30 local, against the signed-in
account, through `tools/survey.py`. **NOTHING WAS SENT.** No invitation, no
message, no follow, no accept, no withdraw. The dumps are
`docs/surveys/custom-invite-2026-09-10.txt`,
`docs/surveys/custom-invite-add-a-note-2026-09-10.txt` and
`docs/surveys/messaging-compose-send-options-2026-09-10.txt`.

`docs/phase-3-survey.md` section 10 lists eleven things it did not measure. This
pass takes the three the Architect named as blocking - the custom-invite page,
the Add-a-note dialog and its character limit, and `Open send options` - and one
more that fell out of the same page load: whether the messaging list can be
reached without marking anybody's conversation read.

## 0. STATUS, and read this before anything below

**These four surfaces are MEASURED. What was built against them is on a branch,
is not on `main`, and has never been run against a live page.**

The mission was stopped mid-flight on 2026-09-10: the owner is releasing what is
on `main` as version 1.0 and everything unbuilt becomes a GitHub issue. This
document and its dumps are the part that lands.

* **Measured here:** the custom-invite page, the Add-a-note dialog and its
  character limit, `Open send options`, and the bare `/messaging/compose/` route
  to the inbox list.
* **Built against them, on branch `phase-3-reach` only:** `connect`, `message`,
  `read-inbox`, `read-thread`, `invitations`, `follow`/`unfollow` and
  `invite-to-follow`, with 388 offline tests. **NOT ON MAIN. NOT LIVE-PROVEN.**
  Not one of those seven verbs has ever been run against LinkedIn - not staged,
  not submitted, not once. `docs/phase-3-report.md` is the honest inventory of
  what that leaves unproven.
* **The only live contact this pass made** was five read-only page loads through
  `tools/survey.py`. Nothing was sent: no invitation, no message, no follow, no
  accept, no withdraw.

## 0.1 What it cost

Three capped views, from a day that had six left when this seat sat down. The
counter is at 77 of 80 and the cap has not been raised and will not be. Two
further uncapped views of the owner's own invitation manager were spent on the
before-and-after check in section 1.

## 1. Navigating to the custom-invite URL sends NOTHING - measured, not assumed

Survey section 10.1 refused to open `/preload/custom-invite/?vanityName=<slug>`
because it was not known "whether it opens the note dialog or does something
more". It opens the note dialog and does nothing more.

That is stated as a MEASUREMENT and not as a reassurance, because the way to be
sure was a count and not an argument:

| | |
|---|---|
| The Sent tab's own `People (N)` pill, before | 39 |
| ... after navigating to the custom-invite page | 39 |
| ... after clicking **Add a note** on it | 39 |

A GET that sent an invitation would have moved that number. It did not move, on
either load. The reasoning available beforehand - "LinkedIn would not put a
state-changing action behind a plain link" - is exactly the kind of confident
premise this mission keeps finding to be wrong, so it was not relied on.

## 2. The custom-invite page: two dialogs, one after the other

**Landing state.** The page renders one dialog, and it is NOT the same kind of
element as the withdraw confirmation:

```
div[role="dialog"]  aria-labelledby="send-invite-modal"    <- a DIV with an
                                                              EXPLICIT role
  text     "Add a note to your invitation? Personalize your invitation to
            <Name> by adding a note. LinkedIn members are more likely to
            accept invitations that include a note. You have unlimited notes
            with Premium"
  buttons  Dismiss | "Add a note" | "Send without a note"
```

**This matters, and it is a trap in the opposite direction from the last one.**
The withdraw confirmation is a NATIVE `<dialog>` with an implicit role, which is
why `[role="dialog"]` found nothing there and a probe reported "no confirmation
appeared" three times while one sat on screen. Here `[role="dialog"]` matches
and `dialog[open]` does not. **Two Phase 3 surfaces, two different dialog
implementations, and a selector written for either one is blind on the other.**
Anything in this toolkit that looks for a dialog looks for BOTH forms.

**There is no `Send` on the landing dialog.** The two actions are `Add a note`,
which reveals the note box, and `Send without a note`, which sends immediately
with no further confirmation. The second is one click from an irreversible act
and it is never touched by anything on the reveal-only list.

## 3. The Add-a-note dialog, and THE LIMIT IS 300, NOT 200

Design 4.1 says "limit 200 characters for a free account; measure it and enforce
what the page says, not what we remember". Measured, on the page, in two places
at once:

```
text     "Add a note to your invitation
          Please limit personal note to 300 characters.
          LinkedIn members are more likely to accept invitations that include
          a personal note.
          0/300"
box      textarea#custom-message   name="message"
          placeholder "Ex: We know each other from..."
          maxlength = NULL
buttons  Dismiss | "Cancel adding a note" (Cancel) | "Send invitation" (Send)
Send is disabled=true while the box is empty
```

Three things follow, and all three are the difference between a verb that works
and one that fails on a real person's invitation.

* **The number is 300.** The design remembered 200. It is the one design
  statement that predicted its own wrongness, which is why it said to measure it.
* **The browser does not enforce it.** `maxlength` is null, so the box accepts a
  400-character note and the page rejects it - or truncates it - at submit time.
  The TOOL has to enforce the limit, and it enforces the number it read off THIS
  page on THIS run, never a constant.
* **The counter `N/300` is a readback.** After typing, the page states how many
  characters it believes are in the box. That is an independent check on what
  was typed actually arriving, and it is free.

`Send invitation` being disabled on an empty box is a usable pre-flight: a run
that finds it enabled before typing is not looking at an empty note dialog.

## 4. `Open send options`: the Enter-sends setting exists, and it is a radio pair

Survey section 10.3 named this as the likeliest home of the setting design rule
0.2 hangs on. It is:

```
group "Choose a send option"
  radio  "Press Enter to Send - Pressing Enter will send message"
  radio  "Click Send - Clicking Send will send message"
```

It is a `group`, not a `[role=menu]` - a probe looking for menu items finds zero
here, which is the third selector-shape surprise on these surfaces.

**WHICH OF THE TWO IS CURRENTLY SELECTED WAS NOT READ, and rule 0.2 does not
depend on it.** The rule is absolute: the composer never presses Enter, whatever
the setting says. Reading the account's current value would cost a capped view
and would change no line of code - the only thing it changes is how loudly the
Enter-sends guard would fire if it were ever broken on purpose (design row
P3-8), and that row is blocked for other reasons. It is recorded here as a gap
rather than guessed at.

## 5. The messaging list is reachable without marking anything read

Survey section 10.7 records that `/messaging/` itself was never loaded, because
the list is believed to select a conversation into its reading pane on load -
which marks it read, irreversibly. That belief is still untested and this pass
did not test it either; opening somebody's conversation to find out is the one
experiment whose failure cannot be undone.

What was measured is that the safe route needs no `profileUrn` - a bare
`/messaging/compose/` renders the whole list with nothing selected:

```
https://www.linkedin.com/messaging/compose/        <- bare, no recipient

  .msg-conversation-card                                    10
  .msg-conversation-card__convo-item-container--unread       4
  li.msg-s-message-list__event                               0   <- no thread open
  li.msg-s-message-list__quick-replies-container             0   <- and so no
                                                                    quick-reply
                                                                    hazard
  [data-test-messaging-inbox-filters__filter-pill]           5
  ul.msg-conversations-container__conversations-list         1
  div[role=textbox].msg-form__contenteditable                1
  button.msg-form__send-button   type=submit  disabled=true  inForm=true
```

Ten cards and four unread - the same numbers the first survey recorded through
the `?profileUrn=` route seven hours earlier, and unchanged after this load.
Nothing was marked read.

**The empty composer holds one character, not zero.** `innerText.length` on an
empty `.msg-form__contenteditable` is 1. A guard that treats "the box is empty"
as length zero is wrong before anybody types.

**This raises a question for the Architect**, carried in `docs/phase-3-report.md`:
amendment A2 made `/messaging/` (exactly) `view_self` because it is the owner's
own inbox and notifies nobody. The only route to that inbox this mission can
prove is safe is `/messaging/compose/`, which A2 leaves on the capped counter. So
the letter of A2 uncaps the route that may mark somebody's conversation read, and
caps the route that cannot.

## 6. What this pass did NOT measure

1. **Whether `/messaging/` auto-selects a conversation.** Still section 10.7's
   open question, and deliberately still open: the only way to find out is to
   risk marking a real conversation read.
2. **Which send option the account currently has selected** - section 4 above.
3. **What `Send without a note` and `Send invitation` actually do**, because
   pressing either sends an invitation to a real person. The staged path proves
   everything up to and including the button being present, enabled and
   correctly named; it does not prove that pressing it works.
4. **The re-invite restriction, the invitation row's `note` and `when`, and the
   Sent tab's `when`** - sections 10.5, 10.8 and 10.9 of the first survey, all
   untouched here.
5. **A second pass on these three surfaces.** Each was seen ONCE. Design section
   1 asks for two.

## 7. What the survey tool needed, and a leak it caught

The text sweep that read `Please limit personal note to 300 characters.` off the
page also matched a block of LinkedIn's own configuration JSON that the
custom-invite page embeds in the document. Three lines of probe output came to
150KB, and inside them, written `"plainId":<the id>`, was the signed-in member's
own numeric id - on no path, inside no urn, carrying no parameter name, and
eight digits long, so R17's fifteen-digit net sits above it by construction.

Both halves are fixed at the root rather than in these two files:

* `tools/survey.py` gains `JSON_ID_FORMS` - a SHAPE, not a name: a JSON key
  ending in `id` holding a bare number of five digits or more. `plainId` is what
  was measured; `memberId` and whatever LinkedIn writes next are the same shape
  and need nobody to teach this rule a second name.
* It also gains `SAFE_LINE_LIMIT`, a cap on one line of a committed dump. **A
  dump nobody can read is a dump nobody DID read**, and reading it is the last
  guard the redaction rules rest on (R13.4). 150KB on one line silently retires
  that guard.

`tests/test_no_leak.py` learned both in the same edit, by looping over
`JSON_ID_FORMS` and over `SAFE_LINE_LIMIT` rather than restating either - the
coupling rule that exists because teaching the redactor `vanityName` alone left
the artefact check blind. Both were **watched failing** on these two dumps,
naming the exact lines, before `tools/redact_surveys.py` was run over them; the
dumps went from 175KB to 22KB and the pass is idempotent, which is what
`--check` proves.

**The identifier in question is the owner's own**, which R13.3 would in fact have
kept had it been on a path. That is not why it was removed: it was removed
because nothing here could SEE it, and a rule that cannot see a form cannot be
relied on to have seen a third party's.
