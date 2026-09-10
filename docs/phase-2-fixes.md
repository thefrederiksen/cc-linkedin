# Phase 2 fixes: the two read-profile defects of 2026-09-09

The Manager's account of the fix pass called for by
`docs/findings-from-live-use-2026-09-09.md`. Read that file first: it is what
the Architect measured by hand and it is what this pass was sent to fix.

Written to be read as self-testimony. The parts that are proven say how, the
parts that are not say so, and the evidence is quoted rather than summarised.

**Public repository.** No third party's name, profile URL or headline appears
here or in the code. The six profiles measured on 2026-09-09 are lettered A to
F; who they were is recorded nowhere, deliberately. The selftest fixtures that
name two of them have no defaults and are passed at run time.

---

## 1. What was actually wrong

Both defects have one cause, and it is not the one either symptom points at.

`read-profile` read the top card **by position**. It collected every visible
paragraph, dropped the ones it recognised - a degree badge, a middot, a
`<count> connections` line, the contact-info link, the location - and then
trusted document order: paragraph 0 was the headline, paragraph 1 the employer.

Re-measured on six profiles, three kinds of paragraph the filter did not
recognise turn up in that run and shift everything after them:

| what | where seen |
|---|---|
| a pronoun, e.g. "He/Him" | profiles C and E, and it is FIRST - before the degree badge |
| a connections count SPLIT across two paragraphs: "500+", then "connections" | three of the six; the other three render it as one paragraph |
| a mutual-connections sentence, "X, Y and 25 other mutual connections" | four of the six |

So which field a caller got out of `current.company` was a property of who the
person was. On profile D - no company pill, no school pill, a split count - the
surviving run was:

```
['Human Resources Coordinator | Open To Work | Looking for Human Resources
  Opportunities', '205', 'connections']
```

and paragraph 1 is `'205'`. That is how a connections count came to be reported
as an employer. On profile B it would have reported the right company, which is
why three clean runs saw nothing.

The second defect is the same failure of identification, on the controls rather
than the paragraphs. `connection_state` scanned the top card for the first word
in a hard-coded tuple `(Connect, Pending, Message, Follow, Following)`. On
profile D the action row is `Message Follow More` - there is no Connect control
on the card at all, the invitation is a More-menu item - so the field answered
`Message`. Which is a true statement about a button and a false answer to the
only question a caller asks it.

## 2. What each field is read from now

Nothing on the top card is found by position any more. Every field is
identified by something that says what it IS.

| field | identified by | when it cannot be read |
|---|---|---|
| `name` | the top card's only `h2` | FAIL |
| `headline` | the first visible direct `<p>` of the identity block, and the identity block is found from the "Contact info" link | FAIL |
| `location` | the first `<p>` of the box that holds the contact-info link | null |
| `current.company` | the pill carrying `svg[id^="company-"]` | **null with `company_reason`** |
| `primary_button` | the one control the page paints `rgb(10, 102, 194)` | FAIL naming the colour |
| `actions` | every visible control within 6px of the primary's top edge, left to right | - |
| `can_connect` | the invite control - `href` containing `custom-invite`, or an aria-label `Invite <name> to connect` - on the card, else in the More menu | FAIL if there is no invite control AND no More button |
| `connections`, `followers` | the count matched against normalised text, parsed to an integer, raw kept | null with a `_reason` |

Two consequences worth stating plainly.

**A pronoun cannot reach the headline any more, and a count cannot reach the
employer.** Pronouns and degree badges live in the name box, which is a child of
the identity block, not a direct paragraph of it. Counts are matched positively
against the whole card's normalised text, which reassembles a count that
LinkedIn split across two paragraphs.

**`connection_state` is gone.** It is not renamed, it is removed, and
`kit/selectors.py` carries a dated note saying so and why, so nobody puts it
back. In its place, four fields read from the controls they actually come from:
`primary_button`, `can_connect`, `connect_via` (`topcard` or `more-menu`), and
`connect_url` (the invitation's own URL, which Phase 3 will want).

**Where the invitation lives varies, and the primary button does not tell you.**
Measured:

| profile | action row | primary (filled) | invitation |
|---|---|---|---|
| A (already a connection) | Message More | Message | nowhere; the menu offers "Remove connection" |
| B (2nd) | Connect Message More | Connect | on the card |
| C (2nd) | Follow Message More | Follow | on the card |
| D (3rd) | Message Follow More | **Message** | in the More menu |
| E (3rd, large following) | Follow Connect Visit my website More | Follow | on the card |
| F (3rd) | Message Follow More | **Message** | in the More menu |

The filled control is not always the leftmost: on D and F the row reads
`Message Follow More` left to right and Message is the filled one.

**The More menu is opened only when the card has no invite control**, and its
contents are believed only when "About this member" is among them - measured
present in all four other-profile menus. An empty menu read is indistinguishable
from a menu with no invitation in it, and the second reading is the one that
would report `can_connect: false` forever without ever being wrong out loud.

## 3. Deviations from `docs/phase-2-design.md`, for the Architect

The design document is the Architect's and has not been edited. Three things in
it are now superseded by the findings file and by what the page turned out to
say. They are listed so they can be ruled on rather than discovered.

1. **The record's shape.** The design lists `connection_state`. It is removed,
   per the findings file's direction to "report the states separately and from
   the controls they actually come from". Added: `primary_button`, `actions`,
   `can_connect`, `can_connect_reason`, `connect_via`, `connect_url`,
   `connections_raw`, `connections_reason`, `followers_raw`,
   `followers_reason`, and inside `current` a `company_reason` when there is no
   company and a `company_url_source` when there is.
2. **`connections` and `followers` are integers now**, with the raw string
   beside them, exactly as `read-company` already does it. They were strings
   like `"500+ connections"`. This is inside the mandate rather than beyond it:
   a count that stays a string is a count that can wander into a text field,
   which is the defect. `"500+"` becomes `500`; the `+` survives in the raw.
3. **Row P2-2's assertion list**, and a new row P2-10 - section 4.

## 4. The rows, and why the old ones could not have caught this

P2-2 asserted four of the eleven fields, and the one it asserted about the
connection was `connection_state in {Connect, Pending, Message, Follow}`. That
is a check for MEMBERSHIP OF A SET, and the set held every value the verb could
produce. The row could fail only if the verb crashed. `Message` is in the set,
so the row passed on a profile where the answer was wrong.

What replaces it, on the principle that an assertion has to be able to tell a
right answer from a wrong one:

* **`--other-expect` and `--menu-expect`**: a person opens the profile, reads it,
  and states what it says as `key=value` pairs - name, headline, location,
  company, degree, primary, can_connect, connections. The row compares the
  record to that statement field by field. Correspondence with the page, not
  membership of a set. A missing key fails the run; **an unknown key fails it
  too**, because a mistyped key would otherwise silently assert nothing.
* **P2-2b, the invariants that need no reader**: no count may reach `name`,
  `headline`, `location` or `current.company`; a company that is empty must say
  why; `primary_button` must be one of `actions`; `can_connect` true must carry
  a `connect_via` and an invite URL bearing THIS person's slug; `can_connect`
  false must carry neither; `can_connect` null only on our own profile.
* **P2-10, a second profile fixture, and the reason it is specified so
  tightly**: it must be a profile whose invitation is behind More AND whose top
  card states no employer. That is profile D's shape, and it is the only shape
  on which BOTH defects are visible. Any other menu profile leaves the
  empty-employer guard unexercised; any other no-employer profile leaves the
  More-menu code unexecuted.

P2-1 gets the same treatment on the owner's own profile, with a committed
default for the expectation because it is his own.

Row counts on the live run: P2-1 checks 31 fields, P2-2 8 correspondences,
P2-2b 25 invariants, P2-10 36. Where a row fails, every failing sub-check prints
with the value that failed it.

`EXPECTED_VIEWS` rises from 7 to 8 for the extra profile, and P2-9 still proves
the view counter moved by exactly that.

## 5. Proof that each fix can fail - watched, not assumed

### Revert 1: the More-menu half of the connection read - WATCHED FAILING

`_connect` was made to return from the top card alone, never opening the More
menu - the pre-fix knowledge state. Full suite re-run against profile D:

```
[20:11:46] read-profile M   RESULT read-profile slug=... name='...'
        - can_connect: False
        - connect_via: None
        - the invite came from the menu, for this person: None
        - can_connect: False wanted True
      P2-10 FAILED: menu profile, 35 checks
[20:11:46] P2-10            menu profile, 35 checks                            FAIL
```

That is the reported symptom: on a person the tool CAN invite, it reports that
it cannot, because it only looked where the invitation was not. P2-1, P2-2,
P2-2b, P2-3, P2-4, P2-7 and P2-8 stayed green through the same run.

The file was restored with `git checkout --` and the tree confirmed clean.

### Revert 2: the employer read - NOT YET WATCHED FAILING

Blocked, not skipped - see section 7. What it will show is already measured on
profile D by an independent probe that reproduces the old positional code
against the live DOM:

```
OLD lines      : ['Human Resources Coordinator | Open To Work | ...', '205', 'connections']
OLD current    : {'company': '205', 'line': '205'}
OLD conn_state : 'Message'
```

and the fixed verb on the same profile in the same minute:

```
current : {'company': None,
           'company_reason': 'the top card shows no company pill, so no current
                              employer is stated on it', ...}
can_connect: True   connect_via: 'more-menu'   connections: 205
```

So the guard that must fire is `current.company is not a count` in P2-2b/P2-10,
plus P2-10's `company=none` correspondence. Both are expected to go red with
`'205'`. **Expected is not watched, and this is not proven until the revert has
been run.**

## 6. What is NOT proven

* **Revert 2 has not been watched failing** (section 5).
* **Three consecutive clean runs have not been done.** Two full clean runs exist
  (`passed=25 failed=0` at 19:50 and at 20:05 on 2026-09-09), the second with
  the final fixtures. The third is blocked - section 7.
* **A pending invitation is unmeasured.** No profile with an invitation already
  sent was read. Such a profile has no invite control, so `can_connect` comes
  back false with the menu's contents quoted in the reason, which is honest but
  is not the same as having seen it. No `Pending` special case was written,
  precisely because writing one would be a claim about a page nobody looked at.
* **`primary_button` rests on one colour constant.** `rgb(10, 102, 194)` was
  measured on five profiles. If LinkedIn restyles, `read-profile` FAILS naming
  the constant rather than guessing - which is the right failure - but it does
  fail, and the fix is a one-line edit in `kit/selectors.py`.
* **The identity block rests on the "Contact info" link.** Present on all six
  profiles measured. A profile without one FAILS naming it rather than falling
  back to counting paragraphs. Whether such a profile exists is not known.
* **`current.title` is still null on every profile**, with its reason, as
  designed: the title is in the Experience card and Phase 2 does not open it.
* **`current.company_url` is null on every profile.** The company pill is a
  button, not a link; the top card carries no company URL. Recorded as
  `company_url_source` rather than left blank.

## 7. The blocker: the daily view cap is spent

`Pace.VIEW_CAP` is 80 profile/company/search page views a day, shared across the
whole fleet through one `pace.json`. At 20:12 on 2026-09-09 it read `"view": 80`
and every further read refuses with `daily cap reached for views (80 today, cap
80). Tomorrow.`

That is the cap working, and it is not to be raised or bypassed. It resets on the
local date roll.

It is worth the Architect knowing what a verification pass now costs against that
budget: one full selftest is 8 views, so three clean runs plus two revert proofs
is 40 - half a day's budget for one pass, before any survey work.

Everything that does not need a view is done, committed and pushed. What remains
is revert 2 and three consecutive clean runs, and both need the counter to roll
over.
