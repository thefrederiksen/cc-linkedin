# Phase 3 design: reaching people

> **AMENDED 2026-09-10. READ `docs/phase-3-amendments.md` FIRST.** The survey
> measured these surfaces and contradicted this document SIX times, including
> the invite control's identity, what `read-inbox` can return at all, and how
> `withdraw` is activated. Where the amendments and this text disagree, the
> amendments win. This document was written before anything was measured -
> the correct order, but it makes the text below a hypothesis.

The Architect's settled design, written 2026-09-09 while Phase 2 is under
inspection. The Manager builds THIS. Where it is silent, decide and write down
what you decided. Where the live page contradicts it, say so and the Architect
rules again - do not quietly build something else. Phase 2 raised two such
questions and both were right to raise.

Verbs: `connect`, `withdraw`, `message`, `read-inbox`, `read-thread`,
`invitations`, `follow` / `unfollow`, `invite-to-follow`.

**This is the first phase whose actions reach another human being and cannot be
taken back.** Everything below follows from that.

## 0. The three rules this phase hangs on

### 0.1 A staged action must PROVE that nothing happened

"Staged" is a claim that we did not act, and a claim of absence certifies
itself. So a staged run does not merely skip the Send click: it dismisses the
dialog, reloads the surface, and asserts the PRE-ACTION state is still there -
the button still reads "Connect" and not "Pending", the thread's last message is
still the one that was last before we typed. A staged run that cannot prove the
pre-action state is a `FAIL`, not a success.

### 0.2 Never press Enter while composing a message

**On LinkedIn's message box, Enter SENDS.** `Browser.type_text()` - which every
Phase 1 verb uses - presses Enter once per newline. Point it at a message box
and a three-paragraph draft sends three fragments to a real person, and no
amount of care afterwards takes them back.

So: the message composer gets its own typing path. Text is inserted per line
with `insert_text`, and line breaks are Shift+Enter, never Enter. And because
that is still just care, it is backed by a check that can fire: **count the
message bubbles in the thread before typing, and assert the count is unchanged
after typing and before submitting.** If it rose, a fragment has already gone;
that is a `FAIL` that says plainly that something reached the recipient, because
the one thing worse than sending a fragment is not telling anyone it went.

### 0.3 An irreversible act names its target twice

A URL can be a typo, and a typo lands on a real different human. So
`--expect-name` is REQUIRED whenever `--submit` is passed to `connect` or
`message`: once in the URL, once in an assertion read off the surface being
acted on - the profile's own name in the top card, the recipient's name in the
thread header. They must match or the verb refuses before typing anything.

Staged runs may omit it. Real sends may not.

## 1. Survey before code

As Phase 2. `tools/survey.py` already exists and it is the tool for this. Survey,
twice, minutes apart, and commit the dumps under `docs/surveys/`:

* a profile showing **Connect** (2nd/3rd degree), and one showing **Pending**;
* a profile whose primary button is **Message**, and one where Connect is behind
  the **More** menu - the plan says it moves, so measure where it is;
* the message composer, both from a profile and from `/messaging/`;
* `/messaging/` thread list, and one open thread;
* `/mynetwork/invitation-manager/` - received invitations, and the Sent tab;
* a company page's Follow control, followed and not followed;
* the Page's **Invite connections** dialog, with its credit count.

Record which rendering each surface serves. Phase 2 found the profile and both
search surfaces are the new server-driven rendering with hashed classes; assume
nothing carries over.

## 2. Pacing gains a rolling window

Today `Pace` caps per calendar day. Connection requests are limited per day AND
per rolling week - the published safe numbers are 20-40 a day and under 100 in
any 7 days, and this tool sits at the bottom of that range.

* `connect`: 20 per calendar day AND 100 per rolling 7 days. The rolling check
  reads the stored per-day counts and sums the last seven, so it survives a
  restart and holds across sessions and agents.
* `message`: 30 per day, unchanged.
* `invite`: 5 per run, and see 4.8 for the credit proof.
* All outbound actions keep the 45-90 second gap.
* `pace.json` today deletes day keys older than today. It must keep at least 8
  days for the rolling window to mean anything. **This is a real change to
  existing behaviour and the rolling check is worthless without it.**

## 3. Code shape

* `kit/connections.py` - `connect`, `withdraw`, `invitations`, `follow`,
  `unfollow`, `invite-to-follow`.
* `kit/messaging.py` - `message`, `read-inbox`, `read-thread`.

New selectors into `kit/selectors.py`, grouped by surface, each with the date
measured, as Phase 1 and Phase 2 do.

## 4. The verbs

Contract as everywhere: JSON records on stdout, one `RESULT <verb> ...` line,
`FAIL <reason>` and exit 1 otherwise.

### 4.1 `connect <profile-url> [--note TEXT] [--expect-name NAME] [--submit]`

Open the profile. Find Connect - on the top card, or behind **More** if that is
where it lives. With `--note`, open "Add a note" and type it (limit 200
characters for a free account; measure it and enforce what the page says, not
what we remember). Then STOP, unless `--submit`.

* Proof of a real send: after a reload, the primary button reads **Pending**.
* Proof of a staged run: after dismissing, and after a reload, the primary
  button still reads **Connect** and the invitation is NOT in the Sent tab.
* `--expect-name` required with `--submit`.
* Counts one connect against both caps. Refuses at either.
* Refuses if the button already reads Pending, and says so rather than clicking.

### 4.2 `withdraw <profile-url>`

Pending -> Withdraw -> confirm by keyboard. Proof: after a reload the button
reads **Connect** again.

**The RESULT line must carry the consequence:** LinkedIn does not let you invite
the same person again for about three weeks after you withdraw. The Manager
verifies that on the live page and words the line from what it measured. A
caller who withdraws without knowing this has spent something they cannot get
back for three weeks, and the tool is the only thing in a position to say so.

### 4.3 `message <profile-url|thread-url> --text ... [--expect-name NAME] [--submit]`

Open the thread (from the profile's Message button, or the thread URL directly).
Assert the recipient in the thread header. Count the existing bubbles. Type by
the rules in 0.2. Assert the count is unchanged. Then STOP, unless `--submit`.

* Proof of a real send: our text is the LAST bubble in the thread, on our side,
  after a reload.
* Proof of a staged run: after discarding, and after a reload, the last bubble
  is the one that was last before we typed, and the draft is gone.
* `--expect-name` required with `--submit`.
* **Never Enter. Never.** See 0.2.

### 4.4 `read-inbox [--limit N] [--unread]`

The `/messaging/` thread LIST only. Record per row: `participant`, `last_line`,
`when`, `unread`, `thread_url`.

**It must not open a thread.** Opening one marks it read, and that is a write
dressed as a read - see 4.5.

Zero rows is a `FAIL`, as everywhere: an empty inbox and a broken selector look
identical, and the broken selector is likelier.

### 4.5 `read-thread <thread-url>`

Every message: `sender`, `text`, `when`.

**Opening a thread MARKS IT READ, and that cannot be undone invisibly** - the
unread signal is gone even if it is later marked unread again. So this verb is
read-only in name only. It says so in its help text, and its `RESULT` line
carries `marked_read=true`. A side effect nobody mentions is how a tool loses
somebody's trust; the fix is one honest word on the line the caller reads.

### 4.6 `invitations [--limit N]`

Received, pending: `name`, `profile_url`, `note`, `when`. Read-only in fact.
Zero rows is a FAIL only when the page states a non-zero count and we parsed
none; a genuinely empty invitation list is ordinary and the page says so
explicitly. **This is the one exception to the zero-rows rule in this toolkit,
and it is allowed only because the page publishes its own count to check
against.** Read the count, compare, and fail on a mismatch.

### 4.7 `follow` / `unfollow` `<profile-url|company-url>`

Read the control's current state, flip it, assert it flipped after a reload.

### 4.8 `invite-to-follow --page ID <profile-url> [--submit]`

The Page's **Invite connections** dialog. Read the remaining credit count, pick
the person, invite.

* Proof: the credit count drops by exactly the number invited, read before and
  after. Not "the row says Invited" alone - the credit is the thing that is
  actually spent, so the credit is what gets counted.
* 50 credits a month is the Page's budget; this verb spends at most 5 per run
  and refuses when the dialog reports fewer credits left than asked for.

## 5. Acceptance rows

| # | What | Asserted |
|---|---|---|
| P3-1 | `connect` staged, no `--submit` | note typed and read back; after dismiss and reload the button still reads Connect; not in the Sent tab |
| P3-2 | `connect --submit` to the consenting person | button reads Pending after reload |
| P3-3 | `withdraw` on that same invitation | button reads Connect after reload; RESULT carries the measured re-invite restriction |
| P3-4 | `connect --submit` with a mismatched `--expect-name` | refuses before typing; exit 1; nothing sent |
| P3-5 | `message` staged | bubble count unchanged after typing; after discard and reload the last bubble is the pre-existing one |
| P3-6 | `message --submit` to the consenting person | our text is the last bubble after reload |
| P3-7 | multi-paragraph message, staged | the box holds all paragraphs as line breaks AND the bubble count never rose - the Enter-sends guard, watched not firing when correct |
| P3-8 | the Enter-sends guard, broken on purpose | point the composer at `type_text`, watch a fragment send, watch the guard FAIL and say so. Run against a thread with the consenting person, who is told to expect it |
| P3-9 | `read-inbox` | rows with participants; no thread opened (assert no thread changed from unread to read across the run) |
| P3-10 | `read-thread` | messages in order; `marked_read=true` on the RESULT line |
| P3-11 | `invitations` | parsed count equals the count the page states |
| P3-12 | `follow` then `unfollow` a Page not currently followed | final state equals the initial state, asserted after a reload |
| P3-13 | `invite-to-follow --submit`, one person | credit count dropped by exactly 1 |
| P3-14 | caps | the rolling 7-day connect check refuses at 100 with a seeded `pace.json`; `pace.json` retains 8 days |
| P3-15 | the whole run | lock released, no stray tab, no native dialog |

Done means every row passes on three consecutive live runs.

**P3-2, P3-3, P3-6, P3-8 and P3-13 need a consenting person and cannot run
without one.** The owner has said he will name them. Until he does, the phase
builds and the staged rows run; the real-send rows are BLOCKED, not skipped, and
the selftest says `BLOCKED: no --consenting-profile given` and exits non-zero.
A blocked row must never read as a passed one.

As in Phase 2, and for the same reason - **this repository is public** - the
consenting person is passed at run time and appears nowhere in the code, the
docs, the surveys or the evidence. Message text and inbox contents are never
committed either: evidence carries counts and shapes.

## 6. Out of scope

Accepting or declining received invitations (reading them is enough for now).
InMail, premium surfaces, Sales Navigator, recruiter. Bulk anything. Group
messages. Attachments in messages. Voice messages. Scheduling a message.
