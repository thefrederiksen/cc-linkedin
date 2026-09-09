# cc-linkedin: the full toolkit. Plan, tests, proof.

Written 2026-09-09 before any of the new code exists. Every feature below has a
mechanism, a proof, a test and a place to run that test. Nothing gets built
that is not on this list, and nothing is called done until its test passes on
the live page and leaves nothing behind.

## What we learned from what already exists

| Source | What it is | What we take |
|---|---|---|
| [inthevalley.blog library](https://inthevalley.blog/ai-guides/how-to-build-a-linkedin-publishing-library-post-native-image-and-first-comment-browser-automation/) | Playwright, Page posts + first comment, production | Comment flow: focus the box, type with keystrokes (execCommand only fires `input`, the Post button never enables), wait for the submit button to enable, verify the comment inside the post's own card, never the first box on the page. |
| joeygoesgrey [LinkedIn Automation Framework](https://github.com/joeygoesgrey/linkedln-bot) (Selenium, May 2026) | Posting, media, engage loops (like, comment, repost) | Selector families that still hold: `feed-shared-social-action-bar`, `comments-comment-box__submit-button`, `react-button__trigger` / `aria-label="React Like"`, `comments-comment-item`, `social-reshare-button`. Two guards worth copying: "have I already commented here?" and "is a near-identical comment already there?" before writing one. |
| [Linked API linkedin-cli](https://github.com/Linked-API/linkedin-cli) (commercial, cloud browser per account) | The most complete verb list on the market | The verb taxonomy: person fetch/search, company fetch/search, post fetch/create/comment/react, comment reply/react, connection send/withdraw/accept/list/status, message send/get, inbox, feed, stats. It also proves the market runs LinkedIn through a browser, not the API. |
| [linkedin-mcp-server](https://github.com/stickerdaniel/linkedin-mcp-server) (3.4k stars, active) | MCP server: profiles, companies, jobs, messages, through a browser driver on the user's own session cookie | Read-side shapes: what a profile record, a company record and a message thread should contain when returned as JSON. |
| `linkedin-api` on PyPI (Voyager, the endpoints the browser itself calls) | Unofficial Python client | A map of what data exists behind each screen. NOT used: it runs outside the browser on a copied cookie and is the classic way to get an account restricted. |
| Our own `add_comment.py` (2026-07) | browser-harness one-shot | The two rules it got right: permalink only, and refuse unless an expected phrase is in the post. |
| Safety guides ([PhantomBuster](https://phantombuster.com/blog/linkedin-automation/linkedin-automation-safe-limits-2026/), [GetSales](https://getsales.io/blog/linkedin-automation-safety-guide-2026/), [Linked Helper](https://www.linkedhelper.com/blog/linkedin-automation-limits)) | 2026 limits | Connection requests 20-40/day, under 100 per rolling week; 40+ seconds between actions; a burst reads as a bot; "unusual activity" and a CAPTCHA are the first warnings and mean stop for the day. |

Nobody in that list drives LinkedIn with an accessibility tree and coordinate
clicks. Everyone uses selectors on a permalink or profile page, waits on state,
and verifies in the card they acted on. That is what this toolkit does.

## Principles that bind every verb

1. **Permalink or profile URL in, never a feed.** A page with one post has one
   comment box, one like button, one menu. The feed has fifty of each.
2. **Prove the target before acting.** `--expect "phrase"` must appear in the
   post (or the profile name must match) or the verb refuses. A wrong URL
   fails loudly instead of acting on a stranger.
3. **Presence proofs, in the card acted on.** A comment is proven by the
   comment text appearing inside that post's comment list under our name; a
   reaction by the button's pressed state; a connection request by the button
   turning into "Pending". Never by "no error".
4. **Keyboard for anything that can fall through.** Submit and confirm buttons
   are pressed with focus + Enter where a late click could land on the page
   behind (learned from the Discard-over-Photo dialog).
5. **Stage by default for anything that reaches a person's inbox.** Connection
   notes and messages compose, verify, screenshot and stop. `--submit` sends,
   and the skill says a human asked for it in that same message.
6. **Reads return JSON.** One record per line on stdout, so outreach, vault and
   standup can consume them.
7. **Pace like a person.** A built-in gap of 45-90 seconds between outbound
   actions, daily caps (below), and a hard stop on any "unusual activity" or
   CAPTCHA text, reported as FAIL.
8. **Same contract.** `RESULT <verb> ...` on success, `FAIL <reason>` and exit
   1 otherwise, composer/dialog discarded, tab closed, no native dialog left.

## Where it is tested

* **Testbed page:** CenterConsulting, Inc. (page 107519091). Three followers,
  nothing to lose, and it is ours. Comments, replies, reactions, edits and
  deletes are tested ONLY on posts this page owns.
* **Testbed post:** each test run creates its own post with `cc-linkedin post
  --submit` (text "cc-linkedin selftest <timestamp>"), acts on it, and deletes
  it at the end with `delete-post`. Nothing is left on the page. mv-001
  (urn:li:activity:7503499656291622912) is the fixed read-only fixture for
  read verbs (it has a video, a long caption and known text).
* **Profile reads:** Soren's own profile and the CenterConsulting page. Public,
  ours, stable.
* **Search:** queries whose top result we know ("Soren Frederiksen", "mindzie").
* **Connection request and message:** stage-only tests run against a real
  profile URL and stop before Send; the single real send per verb goes to ONE
  consenting person Soren names (open question below). Withdraw and delete
  are tested on that same request/thread.
* **Inbox read:** Soren's own inbox, read-only.

The selftest is one command, `cc-linkedin selftest --page ... --page-name ...`,
runs in the foreground, prints one line per check, and ends with a count. It
is run before every commit to the repo and whenever a verb fails in real use.

## The verbs

Legend: proof = what the tool must SEE before it prints RESULT. Test = what the
selftest does. Safety = the guard that stops the wrong action.

### Phase 1: comments and reactions (first)

| Verb | Input | Mechanism | Proof | Test | Safety |
|---|---|---|---|---|---|
| `read-post` | permalink | open permalink, read author, text (expanded past "...more"), media kind, counts from the card | author and text non-empty; JSON printed | read mv-001: author = CenterConsulting, Inc., text starts with the quote, media = video | read-only |
| `read-comments` | permalink | open permalink, click "Load more comments" until none, read `comments-comment-item` rows: author, headline, profile URL, text, time, replies nested | list printed; count matches the card's comment count | on the selftest post after commenting: sees the comment and the reply, authors correct | read-only |
| `comment` | permalink, text, `--expect` | verify expect; focus the ONE comment box; type by keystroke; wait submit enabled; press Post by keyboard | the text appears as a `comments-comment-item` authored by us within 20s | comment on the selftest post, then `read-comments` shows it | permalink only; expect phrase; refuses if we already have an identical comment there |
| `reply` | permalink, comment author or comment id, text | find that comment row; its Reply button; type; submit | reply appears nested under that comment, authored by us | reply to our own selftest comment | row must match exactly one comment |
| `delete-comment` | permalink, `--match` text | our comment row's menu -> Delete -> confirm (keyboard) | row gone after reload | delete the selftest comment and reply | only rows authored by us |
| `react` | permalink or comment, kind (like, celebrate, support, love, insightful, funny) | hover/open the reaction tray; pick; or plain Like | button `aria-pressed=true` and label shows the kind | react to the selftest post; `unreact` clears it | one target only |
| `unreact` | same | click the pressed button | `aria-pressed=false` | as above | |
| `delete-post` | permalink | our post's menu -> Delete -> confirm | permalink 404s / card gone from the page's list | deletes the selftest post at the end of every run | only posts authored by the page/profile we are |

### Phase 2: reading people and search

| Verb | Input | Mechanism | Proof | Test | Safety |
|---|---|---|---|---|---|
| `read-profile` | /in/ URL | open profile; read name, headline, location, about, current role, connection state (Connect / Pending / Message / 1st) | name non-empty and matches page title | Soren's profile: name, headline contain known strings | read-only |
| `read-company` | /company/ URL | open page; name, tagline, followers, about, website | name matches | CenterConsulting page | read-only |
| `search-people` | query, filters (`--company`, `--title`, `--location`), `--limit` | search results page; read each result card | N results with name + URL; first result checked | "Soren Frederiksen" -> first URL is his | read-only; hard cap 100 per run |
| `search-posts` | query, `--limit` | content search; read cards + permalinks | permalinks contain `activity:` | "mindzie" returns posts | read-only |
| `notifications` | `--limit` | notifications page; read rows: kind, actor, target URL, time | rows printed | read-only smoke | read-only |
| `stats` | page id | Page analytics: followers, impressions, engagements (30 days) | numbers printed | CC page | read-only |

### Phase 3: reaching people (staged by default)

| Verb | Input | Mechanism | Proof | Test | Safety |
|---|---|---|---|---|---|
| `connect` | /in/ URL, `--note`, `--submit` | profile; Connect (or More -> Connect); Add a note; type; STOP unless `--submit`; then Send by keyboard | button reads "Pending" after send | staged: note typed and verified, dialog dismissed, button still "Connect". Real: one consenting person | expect name match; daily cap 20; 100/7 days; 45-90 s gap |
| `withdraw` | /in/ URL | Pending -> Withdraw -> confirm | button back to "Connect" | on the consenting person after the real test | |
| `message` | /in/ URL or thread URL, text, `--submit` | Message button; compose; STOP unless `--submit`; Send by keyboard (Enter SENDS on LinkedIn: guard it) | our message is the last bubble in the thread | staged on any connection; real to the consenting person | recipient name verified in the thread header before typing; never Enter while composing |
| `read-inbox` | `--limit`, `--unread` | messaging page; threads: participant, last line, time, unread | rows printed | Soren's inbox | read-only |
| `read-thread` | thread URL | all messages: sender, text, time | rows printed | a thread with the consenting person | read-only |
| `invitations` | | pending received invitations: name, URL, note | rows printed | read-only | |
| `follow` / `unfollow` | /in/ or /company/ URL | Follow button | button state flips | follow and unfollow a public page we already follow | |
| `invite-to-follow` | page id, /in/ URL | Page admin "Invite connections"; pick the person; Invite | credit count drops by one / row shows Invited | one consenting person | 50 credits/month; cap 5 per run |

### Phase 4: more of posting

| Verb | Input | Mechanism | Proof | Test | Safety |
|---|---|---|---|---|---|
| `post --profile` | text, media | feed composer as Soren (personal profile) | identity node names Soren; post found on his activity page | staged only unless Soren asks; his profile is mindzie content | identity check refuses if the composer names a Page |
| `edit-post` | permalink, new text | menu -> Edit post; replace text; Save | new text on the permalink | edit the selftest post | our post only |
| `repost` | permalink, `--thoughts` | Repost -> with your thoughts; composer; Post | new post appears on our list quoting the original | repost mv-001 from the page, then delete | |
| `post` from other Pages | `--page` | already parameterised | as today | | |

## Build order and what "done" means for each

1. `read-post`, `comment`, `read-comments`, `delete-comment`, `delete-post`,
   `react`, `unreact`, `reply`, and the `selftest` that strings them together
   on a post it creates and deletes. Done = selftest passes three times in a
   row on the live page with zero leftovers (post gone, no stray tab, no
   native dialog), and the skill documents every verb.
2. `read-profile`, `read-company`, `search-people`, `search-posts`,
   `notifications`, `stats`. Done = each returns the known fixture values.
3. `connect`, `withdraw`, `message`, `read-inbox`, `read-thread`,
   `invitations`, `follow`/`unfollow`, `invite-to-follow`. Done = staged tests
   pass; one real round trip with the consenting person, then withdrawn and
   the thread read back.
4. `post --profile`, `edit-post`, `repost`.

Each phase lands as its own pull request to `thefrederiksen/cc-linkedin` with
the selftest output in the PR body.

## Code shape

* One file per surface: `cc_linkedin/post.py` (today's code), `comments.py`,
  `reactions.py`, `people.py`, `search.py`, `messaging.py`, `connections.py`,
  `selftest.py`; one `browser.py` holding the attach, the background tab, the
  keyboard press, the native-dialog watchdog and the pacing clock; one
  `cli.py` mapping verbs to functions. `cc_linkedin.py` at the root stays as
  the entry point so every existing command line keeps working.
* Selectors live in one `selectors.py` with a comment per selector naming the
  date it was measured, so a LinkedIn change is a one-file fix.
* A `pace.json` in `%LOCALAPPDATA%\cc-linkedin\` records outbound actions per
  day, so caps hold across sessions and across agents.

## Measured while building Phase 1 (2026-09-09, afternoon)

* **LinkedIn serves the post permalink in two different renderings at random**:
  the classic app (`data-urn` cards, `comments-comment-entity` rows, `ql-editor`)
  and a new React app (hashed class names, `componentkey`, a TipTap editor). The
  same URL gave each within minutes. The tool detects which it got; comment rows
  are mapped on the classic one and a verb that needs rows reloads until it gets
  it. Accessible names ("Open control menu for post by ...", "Text editor for
  creating comment/content", "React Like" / "Unreact Like") are the same words
  in both and are preferred everywhere.
* **One Playwright client per Chrome.** Two attached at once block each other's
  navigations. `kit/browser.py` holds a lock file per port; a second run waits
  and says whose turn it is. This also serialises the video-pipeline session's
  scheduling runs with everything else.
* **The cencon Chrome wedges** (renderers crash, `Inspector.targetCrashed`; the
  launcher was rewritten today with a real health probe and a `restart`). A
  run caught by that ends with a one-line FAIL naming the port; nothing is
  half-done because every verb proves its result before printing RESULT.
* **Reply boxes come pre-filled with the author's @mention**, and an article
  holds two buttons named "Reply" (the action and the box's submit). Submit is
  scoped to the comment form; row matching uses the comment body only.
* **A comment's menu is an unlabelled dropdown trigger** (Copy link / Edit /
  Delete), confirm dialog Cancel / Delete. Confirmed by keyboard.
* **Reactions**: "React Like" -> aria-pressed; hover opens React Celebrate /
  Support / Love / Insightful / Funny; the pressed label reads "Unreact <kind>".
* A pacing file in `%LOCALAPPDATA%\cc-linkedin\pace.json` enforces 45-90 s gaps
  and daily caps across sessions.

## Open questions for Soren

1. Who is the ONE consenting person for the real connection-request and
   message tests? (Suggested: someone at mindzie who will not mind a test
   note and a withdrawal a minute later.)
2. Reactions on other people's posts and comments on other people's posts are
   real outreach. Keep them automatic (they are what a human does dozens of
   times a day) or stage them like messages? Recommendation: automatic, under
   the pacing caps, because the permalink-plus-expect guard already stops the
   wrong-post failure.
