# Findings from driving the live site by hand, 2026-09-09

The Architect used the Phase 2 verbs and then drove a real connection request and a
real message through the browser by hand, for the owner. Four things came out of it
that no selftest run had caught. They are recorded here because two of them change
Phase 3's design and two are defects in Phase 2 that the nine acceptance rows pass
straight over.

## 1. Keyboard Enter on "Send invitation" CLOSES THE DIALOG WITHOUT SENDING

This is the important one, and it invalidates a ruling in `phase-3-design.md`.

Measured on `/in/<slug>/`, the invite dialog, 2026-09-09 evening:

* `element.focus()` on the button named "Send invitation", then
  `Input.dispatchKeyEvent` Enter down/up: **the dialog closed and no invitation was
  created.** The sent-invitations list stayed at 39 and the person was not on it.
* A coordinate click on the same button, same dialog, same note: the dialog closed,
  "Invitation sent" and "Pending" appeared, and the sent list went 39 -> 40 with the
  person on it and the note text intact.

**Why it matters more than an ordinary bug.** Phase 1 learned to press by keyboard
because a late click could fall through onto the page behind, and
`phase-3-design.md` carried that forward to this dialog. Had `connect --submit` been
built that way and proved itself by "the dialog closed", it would have reported a
sent invitation on every run while sending nothing - a silent, plausible, precise
false success, which is the exact defect class this mission is built to refuse. The
only reason it was caught here is that the claim was checked against the sent list
rather than against the dialog.

**Ruling for Phase 3:** the invite dialog's Send is pressed by COORDINATE CLICK, not
by keyboard. Keyboard stays the rule for the Discard/Dismiss/confirm buttons Phase 1
measured it on. Neither rule generalises to the other dialog, and each one names the
dialog it was measured on. And `connect --submit` proves itself on the SENT
INVITATIONS LIST - the person present with the note text - never on the dialog
closing and never on a toast.

## 2. `read-profile` reports a connection state that cannot be acted on

Measured on a 2nd-degree profile: `read-profile` returned
`connection_state: "Message"`. The profile's actual primary button is **Follow**;
"Message" is a secondary button; and **Connect does not exist on the top card at all**
- it is a menu item named "Invite <name> to connect" behind **More**.

So the field answers "what does a button here say" when every caller will read it as
"can I connect with this person, and what happens next". A caller deciding whether to
send an invitation gets `Message` and concludes wrongly.

Phase 2's acceptance row P2-2 asserts only that `connection_state` is in
{Connect, Pending, Message, Follow}. `Message` is in the set, so the row passes. The
row checks membership of a set, not correspondence with the page.

**For the fix:** report the states separately and from the controls they actually
come from - a `primary_button`, and a `can_connect` derived from the presence of the
invite menu item behind More, which is where a 2nd-degree Connect actually lives.

## 3. `read-profile` reports the connections count as the current employer

Same run. `current` came back as
`{"company": "500+", "title": null, "line": "500+"}`.

"500+" is the connections count from the top card. There is no company in that field
at all, and a caller writing "works at 500+" into a CRM or an outreach draft would
never know. The `title_source` note admits the title is not on the top card; nothing
admits the company is wrong rather than merely absent.

An empty field would have been honest. A confident wrong one is the defect class
named in `phase-2-design.md` section 0, and it survived three clean runs because
P2-1 and P2-2 assert `name`, `headline`, `slug` and `degree`, and never look at
`current`.

**Both defects share one cause:** every field that was checked was checked on
Soren's own profile, where there is no Connect button, no degree badge and no
connections-count line in that position. P2-2 exists precisely to cover other
people's profiles, and it asserts four fields out of eleven.

## 4. The 300-character note limit is real and the counter is on the page

The invite dialog's textarea is labelled "Please limit personal note to 300
characters" and renders a live "216/300" counter. Phase 3 should read the limit off
that label rather than hard-coding 200 or 300, and refuse before typing when the
draft is over it.

## What this says about the selftest

Phase 2 passed 23 checks three times in a row, and two of the six verbs return a
wrong field on any profile but the owner's. The suite is not weak because the runs
were faked - they were not. It is weak because nine rows over six verbs is roughly
one assertion per verb per surface, and the fixture that covers other people was
added late and asserts the least. A row per verb proves the verb runs. It does not
prove the record is true.

The Codex inspection was asked to find an eighth gap beyond the seven the Manager
admitted. Findings 2 and 3 are two of them, found by using the tool rather than by
reading it.
