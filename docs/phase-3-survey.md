# Phase 3 survey: what the reaching-people surfaces actually serve

Measured 2026-09-10, between 02:44 and 03:00 local, against the signed-in
account, through `tools/survey.py`. NOTHING WAS SENT. No connection request, no
message, no follow, no invite, no accept, no withdraw. No unread message thread
was opened - see section 4 for how that was made a property of the tool rather
than a matter of care.

The dumps are in `docs/surveys/*-2026-09-10.txt`. This document is what they
mean; where it disagrees with `docs/phase-3-design.md`, section 9 says so
plainly, and section 10 says what was NOT measured.

## 0. What it cost, and what that leaves

Fourteen capped views of the day's eighty were spent here; the counter finished
at 74. The cap was not raised and is not to be. One of the fourteen was wasted
on a crash in a change to `survey.py` made mid-run, which is a lesson about
editing the instrument between measurements.

## 1. Which rendering each surface serves

Phase 2 found the profile and the search surfaces on the new server-driven
rendering with hashed classes. That does NOT carry over. This phase's surfaces
are split down the middle, and the split is not the one the tool reports.

| Surface | Actually serves | `[data-urn]` test says |
|---|---|---|
| Profile top card, and the More menu | new server-driven (hashed classes, `com.linkedin.sdui.*` ids) | react |
| `/messaging/` list, thread, composer | **OLD Ember** (`msg-*` classes, `#emberNN` ids, `data-test-*`) | react |
| `/mynetwork/invitation-manager/` received and sent | new server-driven (hashed classes, `[componentkey]`) | react |
| Company page (member view) | **OLD Ember** (`org-*` classes, `artdeco-*`) | ember |
| Our own Page admin, and the Invite dialog | **OLD Ember** (`org-*`, `artdeco-*`) | ember |

**The rendering test is wrong on the messaging surfaces.** `survey.py` decides
"ember" versus "react" by counting `[data-urn]` elements, and the messaging
pages carry none - so a page whose every class is `msg-conversation-card` and
whose every element id is `ember47` is reported as "react". The test is a proxy
that happened to hold on the surfaces it was written against. Nothing was built
on it here; a Phase 3 verb must not be either.

**`data-view-name` is absent from every new-rendering surface measured here** -
zero on the profile top card, zero on the invitation manager. Phase 1 and 2
selectors that lean on it have nothing to lean on. The Ember surfaces have
`data-test-*` instead, and those are stable and plentiful.

## 2. The profile: Connect, Pending, and where the invitation lives

Measured twice on each profile, minutes apart. Both passes agree in every
particular; nothing on these surfaces varied between them.

**Connect on the card is a LINK, not a button, and its accessible name is not
"Connect".**

```
tag=A  text="Connect"  aria-label="Invite <Full Name> to connect"
       href=/preload/custom-invite/?vanityName=<slug>
```

The word "Connect" is the VISIBLE text. The accessible name is the sentence
above. Every proof in `docs/phase-3-design.md` that reads "the button still
reads Connect" is therefore written against the wrong string and the wrong role
- see section 9.1. The accessible name is also a gift: it states the target's
full name, on the control being pressed, which is exactly the second naming that
design rule 0.3 asks for.

**Pending is the same shape, and it says what it does:**

```
tag=A  text="Pending"  aria-label="Pending, click to withdraw invitation sent to <Full Name>"
       href=<the profile url>
```

So `withdraw` from the profile is one click on this link. Its accessible name
carries the name too.

**Message is a link with a real destination, not a script handler:**

```
tag=A  text="Message"  href=/messaging/compose/?profileUrn=urn:li:fsd_profile:<id>&recipient=<memberid>
```

**Where the invitation lives.** Measured on both fixtures, and the two are
exactly complementary:

* Card shows **Connect** (fixture `other_profile`): the row is Connect /
  Message / More, and the More menu holds *Send profile in a message*, *Save to
  PDF*, *Follow*, *Report*, *Block*, *About this member* - and **no Connect**.
* Card shows **Message** (fixture `menu_profile`): the row is Message / Follow /
  More, and the More menu holds *Send profile in a message*, *Save to PDF*,
  **Connect**, *Report*, *Block*, *About this member*.
* Card shows **Pending** (fixture `pending_profile`): the row is Message /
  Pending / More, and the menu holds *Following* where the other two hold
  Follow or Connect. No invite control anywhere.

The menu's Connect is a `menuitem` carrying the SAME href as the card's Connect,
`/preload/custom-invite/?vanityName=<slug>`. So "on the card or behind More" is
one control in two places, and both are reachable by the same href - which is
worth knowing but is NOT a licence to navigate to it (section 10.1).

**Three traps in the action row, all measured:**

1. **The action row is rendered TWICE** - once in the top card and once in the
   sticky header that appears on scroll. Every control above appears twice in
   the probe. A `.first` selector is picking one of two identical controls by
   accident, not by design.
2. **The page is full of other people's Connect links.** "More profiles for
   you" and "People you may know" each carry their own
   `Invite <someone else> to connect` links with their own `vanityName`. A
   selector matched on role and name anywhere in `main` will find a stranger.
   The invitation must be located within the top card, and the accessible name
   checked against `--expect-name` before anything is pressed.
3. **A control named "Message top connections"** sits on the same page. A
   name-prefix match on "Message" hits it.

## 3. The message composer

Same in both places it was reached - from a profile's Message href, and from
`/messaging/` - because they are the same page.

```
the box   div[role=textbox].msg-form__contenteditable   aria-label="Write a message..."
the send  button.msg-form__send-button   type=submit   text="Send"
```

On an empty compose form the Send button is `disabled=true`. That is a usable
pre-flight assertion: a staged run that finds Send enabled before it typed
anything is looking at something other than an empty composer.

Beside Send there is a separate **"Open send options"** button. It was NOT
opened. It is the likeliest home of the press-Enter-to-send setting, which
design rule 0.2 hangs on, and reading it is the first thing Phase 3 should do.

**A hazard the design does not mention, and it is a big one.** Inside an open
thread the message list ends with a quick-reply row,
`li.msg-s-message-list__quick-replies-container`, holding buttons whose
accessible names are of the form:

```
button "Reply to conversation with <a canned phrase>"
```

**One click on one of those sends that message to that person.** There is no
composer, no confirmation and no draft. They are present on ordinary thread
views, they are in the accessibility tree of the page, and their names begin
with a common word. Nothing in this toolkit may ever click a control by a
name-match that could resolve to one of these.

## 4. The messaging list, and how a thread was opened without marking one read

`/messaging/` was NEVER loaded during this survey. The global navigation
reported `Messaging, 1 new notification` before anything was opened, and the
messaging page selects a conversation into its reading pane on load - which
marks it read, irreversibly. The list was reached through
`/messaging/compose/?profileUrn=...` instead, which renders the same list with
the reading pane occupied by an empty draft rather than by somebody's
conversation.

Measured on that list: **10 conversations, 4 of them unread.**

```
ul.msg-conversations-container__conversations-list   aria-label="Conversation List"
  li.msg-conversation-listitem
    div.msg-conversation-card                                     <- a row
    div.msg-conversation-card__convo-item-container--unread       <- and unread, when it is
      div.msg-conversation-card__participant-names     10 of 10
      div.msg-conversation-card__message-snippet        8 of 10
      time.msg-conversation-card__time-stamp           10 of 10
```

* **Rows have NO href.** `a[href*="/messaging/thread/"]` counts ZERO on this
  page. A thread id exists only once a thread is open, in the address bar. See
  section 9.3 - this contradicts the design directly.
* **Two rows of ten have no snippet.** A row parser that requires all three
  fields drops 20% of this inbox and calls the rest a complete read.
* `.msg-conversation-listitem__unread-count` does not exist. The per-row unread
  COUNT is `div[aria-label="N unread message(s)"]`; the per-row unread FLAG is
  the `--unread` class above. Both were present.
* There is an `Unread` filter pill,
  `button[data-test-messaging-inbox-filters__filter-pill=UNREAD]`, which is what
  `read-inbox --unread` should drive rather than filtering rows itself.

**Opening a thread was made safe by construction, not by care.** `survey.py`
gained `--open-read-thread`, which cannot be aimed: it counts the conversation
cards, keeps only those WITHOUT the unread class, and refuses outright unless
the list also contains at least one row that HAS it - because a marker missing
from every row is a renamed marker, and "nothing looks unread" would then be a
broken instrument reading as a clean result. It recorded `cards: 10, unread: 4,
read: 6`, opened one of the six, and the unread count was still 4 afterwards.
That last number is the proof nothing was marked read.

Inside the opened thread:

```
ul.msg-s-message-list-content
  li.msg-s-message-list__event          4     <- one per message. THIS is the bubble count.
  .msg-s-event-listitem                 4
  .msg-s-event-listitem__body           4     <- the text
  .msg-s-message-group__name            4     <- the sender
  li.msg-s-message-list__quick-replies-container   <- see section 3
```

`li.msg-s-message-list__event` is the count that design rule 0.2 needs. It is
NOT the same as `.msg-s-message-list-content > li`, which also contains a
top-of-list marker, a hidden loader, a typing indicator, a quick-reply row and a
bottom-of-list marker. Counting children of the list would report 9 where the
answer is 4, and a guard that reads 9 before and 9 after cannot see a fragment
that went.

**No message text and no participant name is in any committed dump.** The
redacted dumps carry counts, class names and lengths only, which was checked by
reading them and by a name sweep, not assumed.

## 5. Invitations

`/mynetwork/invitation-manager/` redirects to `.../received/`. Both tabs are
plain URLs - `/received` and `/sent` - so neither needs a click.

**Received.** Per row: an `a[href=/in/<slug>]` carrying the person's name, and
two buttons:

```
button  text="Ignore"  aria-label="Ignore an invitation to connect from <Full Name>"
button  text="Accept"  aria-label="Accept <Full Name>'s invitation"
```

Neither was pressed. Accepting and declining are out of scope for Phase 3 and
they are the two controls on this page that change another person's world.

**The count the page publishes is a FILTER PILL, not a sentence.** The header
reads `Manage invitations | Received | Sent | Focused (2) | Verified (2)`. There
is no "N pending invitations" anywhere, and no "No pending invitations" either.
Design 4.6 rests on the page publishing its own count to check a parse against -
it does publish one, but in this form, and `Focused (2)` counts the focused
filter rather than the whole list. See section 9.4.

**Sent.** The count here is stated as `People (40)`, a link to
`/sent/CONNECTION/`. Forty invitations are outstanding. Per row: an
`a[href=/in/<slug>]`, and the withdraw control, which is

```
tag=A (a LINK, not a button)  text="Withdraw"
    aria-label="Withdraw invitation sent to <Full Name>"
    href=https://www.linkedin.com/          <- a no-op href on an anchor
```

An anchor with `href="https://www.linkedin.com/"` will NAVIGATE if the click is
delivered in a way the page's own handler does not intercept. That is a real
failure mode for a verb that clicks by coordinate or dispatches a synthetic
event, and it is silent: the withdraw does not happen and the tool lands on the
feed.

The pending fixture profile appears in this list by name, which is what makes
design row P3-1's "and the invitation is NOT in the Sent tab" assertion
measurable.

## 6. Follow and unfollow

Company pages are the old Ember rendering, and the Follow control is the
cleanest thing measured all night:

```
not following   button.follow.org-company-follow-button.org-top-card-primary-actions...
                aria-label="Follow"      aria-pressed="false"   text="Follow"

following       button.follow.is-following.org-company-follow-button.org-top-card-...
                aria-label="Following"   aria-pressed="true"    text="Following"
```

Both states were measured on real top cards - one Page the account follows, one
it does not. Three independent signals agree on the state: `aria-pressed`, the
`is-following` class token, and the accessible name. `aria-pressed` is the one to
read; the other two are the cross-check.

One variance worth carrying: one company URL redirected to
`/posts/?feedView=all` and the other stayed put. A verb that asserts on the URL
it asked for will fail on the first one.

Follow controls for OTHER organisations appear further down the same page
(recommendation cards), with the same classes minus the `org-top-card-` part. The
top card must be scoped, as on the profile.

## 7. The Page's Invite connections dialog

Reached on our own Page's admin view - `view_self`, uncapped - and opened by
clicking *Invite connections*. **No credit was spent; nothing was invited.**

Clicking the trigger appends `?invite=true` to the admin URL, so **the dialog is
reachable by URL** and a verb need not hunt for the button.

```
the dialog     [role=dialog]  aria-label="Invite to follow"     <- NOT "Invite connections";
                                                                  that is the trigger's name
the credit     StaticText  "50/50 credits available - Credit refill: October 1, 2026"
the search     input[role=combobox]  aria-label="Search by name"
the filters    Locations / Current company / School / Industry  (artdeco-pill)
each person    role=option, with an input.ember-checkbox
the submit     button  text="Invite"
```

The credit line is the measurement design 4.8 asked for, and it says one thing
the design did not know: the balance carries a **refill date**, not just a
number. `50/50` is the whole month's budget, unspent. The count is stated as
`<used>/<total> credits available`, so the before-and-after proof reads the
first number.

## 8. What the survey tool needed, and why

Three additions, all inside `tools/survey.py` and its in-place partner. No verb,
no kit module, no selftest row was written.

* **`--click NAME`**, against an **allowlist** (`REVEAL_ONLY`) of names that
  only reveal - More, Message, Invite connections, the two invitation tabs, the
  compose control. Any other name is refused before the browser is touched. A
  denylist would certify every name it had not met, and the one it had not met
  is the one that sends something.
* **`--open-read-thread`**, described in section 4. It takes no target.
* **Redaction**, which is section 8.1 and is the part that matters.

### 8.1 Four leaks found, three of them new forms

This repository is public and a leak was found in it yesterday. Four more were
found tonight, and every one is the same defect ruling R17 describes: a rule
written against a SYNTAX loses to the next spelling of the same identifier.

1. **A profile slug inside a DOM element id.** The profile rendering writes it
   into `div#ProfilePostConnectDrawer_<slug>`,
   `div#profileCardsAboveActivityTopcardOnly<slug>` and four more. There is no
   path, no urn and no query parameter around it, so nothing in the redactor
   could see it, and the FIRST committed dump of this phase carried fourteen of
   them. No shape can separate a slug in an element id from an ordinary
   identifier. The fix is not a shape: `survey.py` now collects every `/in/` and
   `/company/` token the live page names - from the URL and from every href in
   the DOM - and redacts those literal strings wherever they appear. The owner's
   own slug and Page keys are kept, per R13.3.
2. **A slug in `?vanityName=`**, on the invitation href. A named query form the
   list did not have. Added, along with `connectionOf`, `miniProfileUrn`,
   `threadId` and `conversationId`.
3. **A conversation id.** `/messaging/thread/<id>` is a stable key to a private
   conversation between named people - the most sensitive identifier this
   mission has produced - and no existing rule fitted it. Added as a path form.
4. **A slug that was PERCENT-ENCODED and then TRUNCATED**, arriving as
   `...%2Fin%2F` plus half a slug, cut mid-token by a probe's own
   110-character slice. This one defeated BOTH kinds of rule at once: the path
   rule because `/in/` was spelled `%2Fin%2F`, and the literal-token rule
   because half a slug is not the string being looked for. **A truncated
   identifier is still a searchable prefix of a real person.** The slug and
   organisation rules now accept either separator and match an empty tail.

**And one self-inflicted defect worth recording**, because it is the exact class
this repository keeps finding. Making those tails `*` instead of `+` made the
rule match the `<slug>` placeholder it had written itself, so every run appended
another one - `/in/<slug><slug><slug>`. `tools/redact_surveys.py` is idempotent
BY CONTRACT; that is how its `--check` proves a dump is clean. A rule that is not
idempotent turns that check into a permanent red that says nothing. Caught by
running `--check` twice, which is now the only way I would believe it.

Applying the corrected rules to the ALREADY-COMMITTED Phase 2 dumps changed
`profile-other`, `search-people` and `search-people-self`: third-party slugs in
`vanityName` and `connectionOf` parameters were sitting in a public repository
on `main`. They are removed here. **This is the Architect's to rule on** - the
same question as R14, and with the same honest limit: unreachable is not gone.

### 8.2 The check that stops it coming back

**The leak test did not find any of the four, and could not have.** It tested
three shapes - digit runs, short links, organisation ids on paths - and these
were slugs, a base64 conversation id and a truncated string. Teaching only the
redactor would have left exactly the gap R18 was written about: the redactor
knows a form, the artefact check cannot see it, the next dump leaks and the
suite stays green. That is why the fix and the guard land as one commit.

`tests/test_no_leak.py` gains a second class, and the point of it is the
COUPLING rather than the rules. The parameter names, the path forms, the
organisation path names and the two urn spellings now live once, in
`tools/survey.py`, as `SENSITIVE_QUERY_PARAMS`, `PATH_FORMS`, `ORG_PATH_NAMES`
and `URN_FORMS`; the redactor builds its regexes from them and the test imports
them and LOOPS. There is no second list, so teaching the redactor a fifteenth
parameter arms the check in the same edit. One assertion per parameter would
have reproduced the defect one layer up, and this is the fifth time this shape
has appeared here.

**Watched failing, on the real artefact.** With the three Phase 2 dumps restored
to the state they are in on `main` right now, the query-parameter rule goes red
and names six occurrences - one `connectionOf` and five `vanityName` - while the
other five rules stay green. The path, organisation and urn rules were then
watched going red on FABRICATED identifiers appended to a dump (a conversation
id, a percent-encoded and truncated profile path, an encoded member urn, an
organisation slug), and watched going green again after
`tools/redact_surveys.py` cleaned exactly those four lines and no others. Real
identifiers were not used as controls: putting one back into the repository to
prove identifiers are not in the repository is how the first pass of the R18 fix
failed, in this same file.

**Three of the four forms are now guarded at the artefact. The fourth is not,
and cannot be.** A slug written into a DOM element id has no shape that
separates it from an ordinary identifier, and enumerating the element-id
prefixes is the losing game R17 is about. What guards it is `survey.py`'s
page-derived literal-token pass plus a person reading the dump before committing
it - which is what happened here. That limit is written into the test class
itself, where the next reader will meet it.

### 8.3 What the committed dumps now show

JS probe results used to be redacted line by line, which meant a menu of seven
items was recorded as seven runs of `<redacted len=N>` - safe, and worthless.
They are now redacted structurally: keys, roles, tag names, class names and
`data-view-name` values survive; accessible names and page text do not. The
shape is the engineering content; only the values are anybody's data.

## 9. Where the live pages CONTRADICT docs/phase-3-design.md

These are for the Architect. Nothing was built on either reading.

### 9.1 "The button reads Connect" is wrong twice over

The design says so in 4.1, in 4.2, and in acceptance rows P3-1, P3-2 and P3-3.
The control is a **link**, not a button, and its **accessible name is "Invite
&lt;Name&gt; to connect"** - the string "Connect" is only its visible text.
`get_by_role("button", name="Connect")` finds nothing on this page. The proofs
need to read the visible text of the top-card control, or match the accessible
name as a pattern; and whichever is chosen, the same choice governs Pending,
whose accessible name is a whole sentence.

### 9.2 The messaging list, the thread and the invitation manager are CAPPED

The brief for this survey said most Phase 3 surfaces are our own and count as
`view_self`. **They do not.** `kit.browser.surface_kind` recognises exactly three
own-surfaces - a profile slug on the owner's list, a Page key on his list, and
`/notifications` - and everything else is `view`. Measured:

```
/messaging/                          -> view      (capped)
/messaging/thread/<id>/              -> view      (capped)
/mynetwork/invitation-manager/       -> view      (capped)
/company/<own page>/admin/...        -> view_self (uncapped)   <- the only free one
```

So the inbox, a thread and the invitation list all spend the safety number today.
By the reasoning of `docs/ruling-view-cap-2026-09-09.md` they arguably should not
- they are the owner's own inbox and his own invitations, they notify nobody, and
they look nothing like scraping - but that is a ruling and not a surveyor's call,
so the cap was obeyed exactly as it stands and this run paid for them. **Nothing
was changed in `surface_kind`.** If the Architect rules them `view_self`, the
enumeration is the place, and the direction of its failure mode stays safe.

### 9.3 `read-inbox` cannot record `thread_url`, because the list has none

Design 4.4 asks for `thread_url` on every row and forbids opening a thread. The
rows are not links and carry no thread id in any attribute; the id first exists
in the address bar after a row is clicked, and clicking a row is the thing 4.5
says marks it read. As specified, 4.4 asks for a field that cannot be obtained
without doing the thing 4.4 forbids. Either the field goes, or `read-inbox`
returns a row handle that is not a URL and `read-thread` accepts it.

### 9.4 The invitation count is a filter pill, not a sentence

Design 4.6 makes the page's own stated count the check that lets `invitations`
be the one verb allowed to return zero rows. The page states `Focused (2)` and
`Verified (2)` on Received and `People (40)` on Sent. There is a number to check
against, so the rule survives - but it is a per-filter count, and the parse it is
compared with has to be the same filter's rows. There is no "No pending
invitations" text on an empty list to fall back on; that phrase was searched for
and is absent.

### 9.5 Withdraw is an anchor with a live href

Design 4.2 treats withdraw as a button press. On the Sent tab it is an `<a>`
whose `href` is `https://www.linkedin.com/`. A click that the page's own handler
does not swallow navigates to the feed and withdraws nothing, silently.

### 9.6 One thing the design got right that is worth saying

Rule 0.2 - never press Enter in the composer - is not paranoia. The composer's
Send button is `type=submit` inside a form, and the thread carries one-click
quick-reply buttons that send canned text with no draft stage at all. The
surface is more dangerous than the design assumed, not less.

## 10. What was NOT measured, so nobody thinks it was

1. **The custom-invite page itself.** `/preload/custom-invite/?vanityName=<slug>`
   is the invitation's destination, measured as a URL on both the card and the
   menu. It was NOT navigated to, because it is not known whether it opens the
   note dialog or does something more, and this run's rule was that nothing
   leaves. **The "Add a note" dialog, its 200-character limit, its "Send" and
   its "Send without a note" are therefore all UNMEASURED.** Design 4.1 depends
   on every one of them. This is the first thing Phase 3 should measure, with
   the owner awake.
2. **The Connect button was never clicked**, on the card or in the menu, for the
   same reason. What a staged `connect` actually sees after pressing it is
   unknown.
3. **"Open send options"** beside the Send button was not opened. It is the
   likeliest home of the Enter-sends setting.
4. **The withdraw confirmation.** Design 4.2 says "confirm by keyboard". Whether
   there is a confirmation at all, and what it says, is unmeasured on both the
   profile and the Sent tab.
5. **The re-invite restriction after a withdrawal** - the three weeks design 4.2
   requires the RESULT line to carry - is NOT verified. Nothing on any surveyed
   page states it. It cannot be measured without withdrawing a real invitation.
6. **A profile whose primary control is Message** was measured (the menu
   fixture), but no profile in a **1st-degree** state was surveyed at all.
7. **`/messaging/` itself was never loaded.** Everything in section 4 was
   measured through the compose route. The plain list route may auto-select a
   conversation; that is precisely why it was avoided, and it remains untested.
8. **The invitation row's `note` and `when`** - design 4.6 asks for both. Neither
   was isolated to a selector; only the name and the profile URL were.
9. **The Sent tab's `when`** likewise.
10. **A second pass** was taken on the two Connect profiles only. The messaging
    list was seen twice (sections 4 and the row-field pass) and agreed both
    times. The invitation manager, both company pages and the Invite dialog were
    each seen ONCE. Design section 1 asks for two passes on everything; six
    surfaces have one.
11. **Nothing here was verified against a logged-out or differently-permissioned
    account.** Every measurement is this account, this night, this A/B bucket.
