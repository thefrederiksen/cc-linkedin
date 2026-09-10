# -*- coding: utf-8 -*-
"""Every selector the toolkit relies on, in one place, each with the date it was
measured on the live page. When LinkedIn changes a control, the failing verb
names the selector and the fix is one line here.

TWO RENDERINGS OF THE SAME PERMALINK (measured 2026-09-09, minutes apart)
  * "ember": the classic app. `div.feed-shared-update-v2[data-urn]`, class
    names like comments-comment-box, ql-editor, react-button__trigger. This is
    the one every open-source LinkedIn poster was written against.
  * "react": the new app. Hashed class names, `componentkey` attributes, a
    TipTap editor, no data-urn. Only roles and accessible names are stable.
  The tool detects which it got (`[data-urn]` present = ember) and uses that
  rendering's table. Accessible names are preferred in both because they are
  the same words a person reads.

Scope rule: a post's controls are looked up INSIDE the post's own container,
never on the whole page.
"""
import re

# -- shared: accessible names, both renderings ------------------- 2026-09-09
POST_MENU_NAME = re.compile(r"^Open control menu for post")          # button
POST_MENU_ITEMS = ("Edit post", "Delete post", "Copy link to post")  # menuitem text (react) / dropdown item (ember)
COMMENT_EDITOR_NAME = re.compile(r"^Text editor for creating (comment|content)")   # textbox
COMMENT_SUBMIT_NAME = re.compile(r"^(Comment|Post|Reply)$")          # button, enabled once text is in the box; a reply box says "Reply"
IDENTITY_SWITCH_NAME = "Open menu for switching identity when interacting with this post"
REACTIONS_MENU_NAME = "Open reactions menu"
REACTION_NAME = "React {kind}"                                        # React Like / Celebrate / Support / Love / Insightful / Funny
LIKE_STATE_REACT = 'button[aria-label^="Reaction button state"]'    # react rendering: label carries the state
LIKE_STATE_EMBER = 'button.react-button__trigger[aria-pressed]'      # ember: label flips "React Like" <-> "Unreact Like", aria-pressed carries the state
LIKE_ANY = LIKE_STATE_REACT + ", " + LIKE_STATE_EMBER

# -- ember rendering --------------------------------------------- 2026-09-09
EMBER = {
    "card": 'div.feed-shared-update-v2[data-urn="{urn}"], [data-urn="{urn}"]',
    "card_any": 'div.feed-shared-update-v2[data-urn], [data-urn*="activity"]',
    "actor_title": '.update-components-actor__title',
    "actor_link": 'a.update-components-actor__meta-link, a[href*="/in/"], a[href*="/company/"]',
    "text": '.update-components-text, .update-components-update-v2__commentary',
    "more": 'button.feed-shared-inline-show-more-text__see-more-less-toggle, button:has-text("more")',
    "video": 'video',
    "image": '.update-components-image img',
    "counts": '.social-details-social-counts',
    "comment_button": 'button.comment-button, button[aria-label="Comment"]',
    "comment_box": '.comments-comment-box__form, form.comments-comment-box__form',
    "comment_item": 'article.comments-comment-entity, .comments-comment-item, article[class*="comments-comment"]',
    "comment_author": '.comments-comment-meta__description-title, .comments-post-meta__name-text, .comments-comment-meta__name',
    "comment_text": '.comments-comment-item__main-content, .update-components-text',
    "comment_load_more": 'button.comments-comments-list__load-more-comments-button, button:has-text("Load more comments")',
    "comment_show_replies": 'button.comments-comment-item__replies-list-toggle, button:has-text("more replies"), button:has-text("previous replies")',
    "reply_button": 'button[aria-label^="Reply"], button:has-text("Reply")',
    "menu_item": '[role="menuitem"], .artdeco-dropdown__item',
}

# -- react rendering --------------------------------------------- 2026-09-09
REACT = {
    "text": '[data-testid="expandable-text-box"]',
    "menu_item": '[role="menuitem"]',
}

CONFIRM_DELETE = re.compile(r"^Delete$")


# ============================================================================
# PHASE 2: reading people, companies, search, notifications, Page analytics.
# Every line below was measured on the live page on 2026-09-09 and the dump it
# came from is committed under docs/surveys/. A LinkedIn change is a one-line
# fix here.
#
# WHICH RENDERING EACH SURFACE SERVES (measured 2026-09-09, each twice)
#   /in/<slug>/                       new React (SDUI) ONLY - [data-urn] 0, and
#                                     .global-nav__me does not exist
#   /company/<slug>/about/            classic org page, org-top-card-* classes
#   /company/<id>/admin/analytics/    classic
#   /search/results/people/           new React (SDUI) ONLY
#   /search/results/content/          new React (SDUI) ONLY
#   /notifications/                   classic, nt-card classes
# Unlike the post permalink Phase 1 met, none of these was ever seen in a second
# rendering, so there is no reload-until-classic dance here. If one day a dump
# disagrees with another taken minutes later, that surface has gained a second
# rendering and BOTH belong in this file.
# ============================================================================

# -- profile, the SDUI rendering --------------------------------- 2026-09-09
# The class names are hashed and change without notice; the element IDs are
# generated from the server-driven component names and are the only stable
# handle on the page. The top card's id is
# "com.linkedin.sdui.profile.card.ref<memberid>Topcard", so it is matched on the
# SUFFIX; an id selector cannot be used directly because the id contains dots.
PROFILE_TOPCARD = 'div[id$="Topcard"]'
PROFILE_ABOUT_CARD = 'div[id$="About"]'
PROFILE_ACTIVITY_CARD = 'div[id$="Activity"]'
PROFILE_CONTACT_INFO = 'a[href*="/overlay/contact-info/"]'
# The About card's expander reads "... more", not "see more" (measured
# 2026-09-09: the collapsed text ends "… more"). Both spellings match.
PROFILE_SEE_MORE = re.compile(u"^\s*(?:\u2026\s*)?(?:see\s+)?more\s*$", re.I)
# The degree badge is a paragraph of its own reading "- 1st". It is rendered
# TWICE on the same card, inside different responsive wrappers, and the two can
# hold DIFFERENT values (measured: a 1st-degree profile carried both "- 1st" and
# a hidden "- 2nd"). Only the visible one is read, and two visible ones that
# disagree are a FAIL, never a first-in-document-order guess.
DEGREE_TEXT = re.compile(u"^[\u00b7\u2022\s]*(1st|2nd|3rd\+?|You)\s*$", re.I)
DEGREES = ("self", "1st", "2nd", "3rd", "3rd+")

# THE FIELD THAT WAS REMOVED, AND WHY -------------------------- 2026-09-09
# There used to be a CONNECTION_STATES tuple here - ("Connect", "Pending",
# "Message", "Follow", "Following") - and read-profile reported the first of
# those words it could find among the top card's controls, as
# `connection_state`. DO NOT PUT IT BACK. Measured on
# a 3rd-degree profile on 2026-09-09: the action row reads
# "Message Follow More", there is no Connect control on the top card at all,
# and the invitation lives in the More menu. The old field answered "what does
# a button here say" while every caller reads it as "can I connect with this
# person" - so it answered Message, and a caller deciding whether to send an
# invitation concluded wrongly. It is replaced by two fields read from the two
# different controls they actually come from: `primary_button` (the filled
# control, below) and `can_connect` (the invite control, wherever it lives).

# THE PRIMARY CONTROL IS IDENTIFIED BY ITS FILL, NOT BY ITS POSITION AND NOT BY
# ITS WORDS. Measured 2026-09-09 on five profiles: every top card paints
# exactly one action in LinkedIn blue and outlines the rest, and the filled one
# is NOT always the leftmost - on one of them the row reads
# "Message Follow More" left to right and the filled control is Message. The
# colour sits on an inner <span>, never on the <a>/<button> itself, so the whole
# subtree is searched. Class names on this surface are hashed and meaningless;
# this colour is not. If LinkedIn restyles, read-profile FAILS naming this
# constant and the fix is this one line.
PROFILE_PRIMARY_FILL = "rgb(10, 102, 194)"
# The action row is then every visible control sitting on the same line as that
# one, within this many pixels of its top edge.
PROFILE_ROW_TOLERANCE = 6

# THE INVITE CONTROL, WHEREVER IT LIVES. Measured 2026-09-09, three shapes on
# five profiles, and the tool must not care which shape it got:
#   * two of them - on the top card: an <a>
#     reading "Connect", aria-label "Invite <name> to connect", href
#     /preload/custom-invite/?vanityName=<slug>
#   * two more - NOT on the top card at
#     all; a More-menu item reading "Connect", same custom-invite href, and no
#     aria-label
#   * one already connected - no invite control anywhere, and
#     the More menu offers "Remove connection" instead
# The href is the reliable marker and the aria-label is the second; the word
# "Connect" alone is not, because it appears all over a profile page (the
# right-hand rail's suggestion cards are full of it).
INVITE_HREF = "custom-invite"
INVITE_ARIA = re.compile(r"^Invite .+ to connect$", re.I)
# AN INVITATION ALREADY SENT - F3, MEASURED 2026-09-10 on the profile the
# Architect invited on 2026-09-09. The control sits in the same action row, an
# <a> between Message and More:
#     text        "Pending"
#     aria-label  "Pending, click to withdraw invitation sent to <the person>"
#     href        the profile's own URL. There is NO withdraw endpoint on the
#                 card, so this says an invitation exists and says nothing about
#                 how to take it back - which Phase 3 needs to know before it
#                 goes looking for one here.
#     disabled    false, filled false (Message is the filled control on that row)
# Matched on the LABEL and not on the word "Pending", for the same reason
# INVITE_ARIA is not matched on the word "Connect": a bare word is not an
# identification. The cost of that choice is stated where it is made, in
# people._pending.
INVITE_PENDING_ARIA = re.compile(r"^Pending, click to withdraw invitation sent to .+", re.I)
# The More button on somebody else's top card: text "More" on the wide layout,
# aria-label "More" on the narrow one. The owner's OWN top card has neither -
# its row reads Open to / Add section / Add custom button / Resources - which is
# one more reason read-profile never opens a menu on its own profile.
# Matched on the ACCESSIBLE NAME, not on a CSS text selector: the word sits in
# a nested <span>, so button:text-is("More") returns 0 on a button a person
# plainly reads as "More" (measured 2026-09-09 on a 3rd-degree profile).
PROFILE_MORE_NAME = re.compile(r"^More$")
PROFILE_MENU_ITEM = '[role="menuitem"]'
# PROOF THE MENU ACTUALLY OPENED. A menu read that comes back empty is
# indistinguishable from a menu with no invite in it, and the second reading is
# the one that quietly reports can_connect=false forever. So the menu is
# believed only when this item is in it - measured present in every one of the
# four other-profile menus read on 2026-09-09, connected and unconnected alike.
PROFILE_MENU_PROOF = "About this member"

# Counts are read from the WHOLE top card's text, not from one paragraph.
# Measured 2026-09-09: the connections count is ONE paragraph ("500+
# connections" on the owner's own profile and on one other) on some profiles
# and TWO adjacent paragraphs ("500+", then "connections") on three others.
# A per-paragraph matcher sees the second shape as
# a bare "500+" with no word attached - which is exactly how "500+" came to be
# reported as an employer - so the card's text is normalised first and matched
# as a whole. "N other mutual connections" cannot match it: the number is not
# adjacent to the word.
COUNT_LINE = re.compile(r"^\s*([\d][\d,\.]*\+?|\d+(?:\.\d+)?[KMB])\s+(connections?|followers?)\s*$", re.I)
CONNECTIONS_IN_CARD = re.compile(r"([\d][\d,\.]*\+?|\d+(?:\.\d+)?[KMB])\s+connections?\b", re.I)
# Anything that is only a number, with or without a K/M/B or a trailing plus.
# A value that matches this is a COUNT, and a count must never be reported as a
# company, a headline or a location.
BARE_COUNT = re.compile(r"^\s*(?:[\d][\d,\.]*|\d+(?:\.\d+)?\s*[KMB])\+?\s*$", re.I)

# -- company, the classic org page ------------------------------- 2026-09-09
# A Page ADMIN is redirected from /company/<id>/ and /company/<slug>/about/ to
# /admin/dashboard/. ?viewAsMember=true serves the ordinary member page and was
# measured NOT to redirect.
COMPANY_MEMBER_VIEW = "https://www.linkedin.com/company/%s/about/?viewAsMember=true"
COMPANY = {
    "name": "h1.org-top-card-summary__title, .org-top-card-summary__title, h1",
    "tagline": "p.org-top-card-summary__tagline, .org-top-card-summary__tagline",
    "info_item": ".org-top-card-summary-info-list__info-item",
    "about": "section.org-about-module__margin-bottom p.break-words, .org-about-module__margin-bottom p.break-words",
    "details": "dl",
    "term": "dt",
    "definition": "dd",
}
FOLLOWERS_ITEM = re.compile(r"^\s*([\d][\d,\.]*|\d+(?:\.\d+)?[KMB])\s+followers?\s*$", re.I)

# -- people search, the SDUI rendering --------------------------- 2026-09-09
# A result is a div[role=listitem]; the person's name is the text of the FIRST
# anchor to /in/ that sits inside a <p>, and that <p>'s parent holds two further
# div > p pairs, the headline then the location. The outer anchor wrapping the
# whole card also points at /in/ - matching on "p a" is what separates the name
# from the card.
SEARCH_ITEM = 'div[role="listitem"]'
SEARCH_PERSON_NAME = 'p a[href*="/in/"]'
SEARCH_PERSON_LINES = ':scope > div > p'
# A content-search card carries NO permalink and no activity urn anywhere in its
# DOM (measured: a[href*="urn:li:activity"] 0, [data-urn] 0, [data-id] 0, on
# four consecutive loads). Its "Copy link to post" is a menu item with no href
# that writes a shortened lnkd.in link to the clipboard.
SEARCH_POST_MENU = re.compile(r"^Open control menu for post by (.+)$")
COPY_LINK_ITEM = "Copy link to post"
SHORT_LINK = re.compile(r"https://lnkd\.in/\S+")

# -- notifications, the classic rendering ------------------------ 2026-09-09
NOTIFICATION = {
    "card": "article.nt-card",
    "unread": "nt-card--unread",
    "headline": "a.nt-card__headline",
    "text": ".nt-card__text--3-line",
    "actor_link": 'a[data-view-name="notification-card-image"]',
    "when": "p.nt-card__time-ago",
}
NOTIFICATION_ACTOR = re.compile(u"^View (.+)[\u2019']s profile\.$")
HIGHLIGHTED_URN = re.compile(r"highlightedUpdateUrn=([^&]+)")

# -- Page analytics, the classic rendering ----------------------- 2026-09-09
# THE TRAP ON THIS SURFACE. The only four-number headline card on
# /admin/analytics/updates/ is titled "Your profile view highlights" and holds
# the signed-in MEMBER's own profile-view numbers, not the Page's:
# .member-analytics-addon-summary__list-item has four hits, the right shape and
# the right four labels (Impressions / Reactions / Comments / Reposts), and
# reading it returns the wrong entity's data with no error. It is named here so
# that nobody reaches for it again.
STATS_MEMBER_ADDON_DO_NOT_USE = ".member-analytics-addon-summary__list-item"
STATS_ADMIN_HEADER_FOLLOWERS = re.compile(r"([\d][\d,\.]*)\s+followers?", re.I)
STATS_TABLE = "table"
STATS_TIME_RANGE = re.compile(r"Time range:\s*(.+?)\s*-\s*(.{4,25}?\d{4})", re.I)


# ============================================================================
# PHASE 3: the invitation manager, and withdrawing an invitation we sent.
# Measured 2026-09-10 on the live page; the dump is
# docs/surveys/invitations-sent-rows-2026-09-10.txt. The surface is the new
# server-driven rendering: hashed class names, no data-urn, no data-view-name.
# Accessible names are the only stable handle and they are whole sentences.
# ============================================================================

INVITATION_MANAGER = "https://www.linkedin.com/mynetwork/invitation-manager/"
INVITATIONS_SENT = "https://www.linkedin.com/mynetwork/invitation-manager/sent/"
# What the address bar must still say after the withdraw control is activated.
# A5: the control is an anchor with a LIVE href to the feed, so "did we stay
# here" is a real question with a real wrong answer.
ON_INVITATION_MANAGER = "/mynetwork/invitation-manager"

# THE WITHDRAW CONTROL IS AN <a>, AND ITS href IS THE FEED - measured
# 2026-09-10, and it is the whole reason this verb asserts where it landed:
#
#     tag=A  text="Withdraw"
#            aria-label="Withdraw invitation sent to <Full Name>"
#            href=https://www.linkedin.com/
#
# A click the page's own handler does not swallow NAVIGATES TO THE FEED and
# withdraws nothing, silently. The row is found by the aria-label because the
# visible text is the bare word "Withdraw", repeated forty times on the page,
# and a bare word is not an identification.
WITHDRAW_LINK = 'a[aria-label^="Withdraw invitation sent to"]'
WITHDRAW_ARIA = re.compile(r"^Withdraw invitation sent to (.+)$", re.I)
WITHDRAW_HREF_TRAP = "https://www.linkedin.com/"

# The age each row displays, e.g. "Sent 11 hours ago", "Sent yesterday",
# "Sent 1 week ago", "Sent 3 months ago". LinkedIn states a ROUNDED-DOWN
# relative age and never a date, so "3 months ago" means AT LEAST three months
# and the tool must never turn it into one.
SENT_AGE = re.compile(r"Sent\s+([^\n]+?)\s*$", re.I | re.M)
SENT_AGE_UNITS = re.compile(
    r"^(?:(\d+)\s+)?(second|minute|hour|day|week|month|year)s?\s+ago$", re.I)

# The count the page publishes for the Sent tab: `People (40)`, a link to
# /sent/CONNECTION/. A4 - it is a per-filter pill and there is no sentence to
# fall back on, so a parse is checked against the pill of the SAME filter whose
# rows were parsed.
SENT_COUNT_PILL = re.compile(r"People\s*\((\d[\d,]*)\)", re.I)

# THE LIST LAZY-LOADS TEN AT A TIME AND THE WINDOW IS NOT THE SCROLLER -
# measured 2026-09-10. window.scrollTo and mouse wheel events both do nothing:
# document.body.scrollHeight equals its clientHeight, and the element that
# actually scrolls is <main>. Scrolling the wrong thing looks exactly like a
# list with only ten rows in it, which is how "the row is not here" becomes a
# confident wrong answer about somebody's invitation.
SENT_SCROLLER_JS = """
() => {
  const all = [...document.querySelectorAll('main, div')].filter(e => {
    const s = getComputedStyle(e);
    return e.scrollHeight > e.clientHeight + 80 && e.clientHeight > 200
           && /auto|scroll/.test(s.overflowY);
  });
  const el = all[0] || document.scrollingElement;
  el.scrollTop = el.scrollHeight;
  return {tag: el.tagName, height: el.scrollHeight};
}
"""

# THE CONFIRMATION - MEASURED 2026-09-10, and it had never been measured before
# (survey section 10.4). It is a NATIVE <dialog>, which is why the first three
# attempts reported "no confirmation appeared": a native <dialog> carries an
# IMPLICIT role, so it has no role attribute and '[role="dialog"]' does not
# match it. The probe was blind, its pass condition was an absence, and so it
# certified a confirmation that was open on screen intercepting every click.
#
#     <dialog open data-testid="dialog" aria-labelledby="dialog-header">
#       heading  "Withdraw invitation"
#       text     "If you withdraw now, you won't be able to resend to this
#                 person for up to 3 weeks."
#       buttons  Dismiss | Cancel | <the withdraw sentence again>
#
# THE CONFIRM BUTTON IS NOT CALLED "Withdraw". Its visible text is, but its
# accessible name is the SAME SENTENCE the row's control carries - "Withdraw
# invitation sent to <Full Name>" - and the dialog's own heading also reads
# "Withdraw invitation". Matching the bare word would have three candidates on
# screen, one of them a heading. So the confirm control is identified
# positively: a BUTTON, inside the open dialog, whose accessible name is the
# withdraw sentence naming THE SAME PERSON the row named. That is the target's
# name read a third time, off the last control that gets pressed.
DIALOG_OPEN = 'dialog[open], [data-testid="dialog"]'
# What the page itself says a withdrawal costs, quoted from the live dialog on
# 2026-09-10. Note "UP TO 3 weeks": the design said "about three weeks", and the
# page's own words are both weaker and vaguer than that. The RESULT line carries
# what the page said, never what the design remembered.
REINVITE_RESTRICTION = re.compile(
    r"won.?t be able to resend to this person for ([^.]+)", re.I)


# ============================================================================
# PHASE 3, the remaining seven verbs. Measured 2026-09-10 on the live pages;
# the dumps are docs/surveys/custom-invite-2026-09-10.txt,
# custom-invite-add-a-note-2026-09-10.txt,
# messaging-compose-send-options-2026-09-10.txt, messaging-list-2026-09-10.txt,
# messaging-thread-read-2026-09-10.txt, invitations-received-2026-09-10.txt,
# company-follow-not-followed-2026-09-10.txt, company-follow-second-2026-09-10.txt
# and page-invite-connections-2026-09-10.txt. What they mean is in
# docs/phase-3-survey.md and docs/phase-3-survey-2.md.
#
# WHICH RENDERING EACH SURFACE SERVES, and it is split down the middle:
#   /preload/custom-invite/            new server-driven
#   /messaging/... (list, thread, composer)   OLD Ember: msg-* classes,
#                                      data-test-* attributes, #emberNN ids.
#                                      The [data-urn] test reports "react" on
#                                      these and is WRONG - the page carries no
#                                      data-urn at all. Nothing here uses it.
#   /mynetwork/invitation-manager/     new server-driven
#   /company/<key>/ (member view)      OLD Ember: org-*, artdeco-*
#   /company/<id>/admin/?invite=true   OLD Ember
# ============================================================================

# TWO DIALOG IMPLEMENTATIONS ON TWO PHASE 3 SURFACES, AND A SELECTOR FOR EITHER
# ONE IS BLIND ON THE OTHER - measured 2026-09-10.
#
#   the withdraw confirmation   <dialog open data-testid="dialog">   NATIVE.
#       A native <dialog> carries an IMPLICIT role, so it has no role attribute
#       and '[role="dialog"]' MATCHES NOTHING. A probe that looked for exactly
#       that reported "no confirmation appeared" three times while the
#       confirmation sat open on screen intercepting every pointer event.
#   the custom-invite modal     <div role="dialog" aria-labelledby="send-invite-modal">
#       An ordinary div with an EXPLICIT role. 'dialog[open]' matches nothing
#       here.
#
# So anything in this toolkit that asks "is a dialog on screen" asks for BOTH
# forms, and the answer "none" is treated as a broken instrument on any surface
# where one has ever been measured. DIALOG_OPEN above is the withdraw surface's
# own narrower selector; this is the one to reach for on a surface whose modal
# has not been measured.
DIALOG_ANY = ('dialog[open], dialog, [data-testid="dialog"], [role="dialog"], '
              '[role="alertdialog"], [aria-modal="true"]')

# -- connect: the custom-invite page ----------------------------- 2026-09-10
# The destination of the invite control read_profile already resolves. It is a
# PLAIN GET and it sends nothing: measured by counting the Sent tab's own
# People pill before and after (39, 39, and 39 again after Add a note).
CUSTOM_INVITE_URL = "https://www.linkedin.com/preload/custom-invite/?vanityName=%s"
ON_CUSTOM_INVITE = "/preload/custom-invite"
# The modal, identified by what labels it rather than by the word "dialog".
INVITE_MODAL = '[role="dialog"][aria-labelledby="send-invite-modal"]'
INVITE_MODAL_LABELLEDBY = "send-invite-modal"
# The controls, by ACCESSIBLE NAME, each measured verbatim. Note that the
# landing dialog has NO Send: its two actions are "Add a note", which reveals
# the note box, and "Send without a note", which sends immediately with no
# further confirmation at all.
INVITE_ADD_NOTE = "Add a note"
INVITE_SEND_WITHOUT_NOTE = "Send without a note"
INVITE_CANCEL_NOTE = "Cancel adding a note"
# The note dialog's Send. Its VISIBLE text is "Send"; its accessible name is
# "Send invitation". It is disabled while the note box is empty, which is a
# usable pre-flight - a run that finds it enabled before typing is not looking
# at an empty note dialog.
INVITE_SEND = "Send invitation"
INVITE_DISMISS = "Dismiss"
NOTE_BOX = "textarea#custom-message"
# THE LIMIT IS READ OFF THE PAGE, NEVER REMEMBERED. Design 4.1 said 200; the
# page says 300, in two places at once - a sentence and a live counter. The
# textarea carries NO maxlength attribute, so the browser does not enforce it
# and the tool must.
NOTE_LIMIT_SENTENCE = re.compile(r"limit personal note to (\d[\d,]*) characters", re.I)
NOTE_COUNTER = re.compile(r"\b(\d[\d,]*)\s*/\s*(\d[\d,]*)\b")

# -- messaging --------------------------------------------------- 2026-09-10
# THE LIST IS REACHED THROUGH THE BARE COMPOSE ROUTE AND NOT THROUGH /messaging/.
# Loading /messaging/ is believed to select a conversation into the reading pane,
# which MARKS IT READ and cannot be undone invisibly; that belief is untested and
# deliberately stays untested, because the only experiment is somebody's real
# conversation. Measured 2026-09-10: a bare /messaging/compose/ renders the whole
# list with NO thread open (li.msg-s-message-list__event 0) and no quick-reply
# row, and it needs no profileUrn.
MESSAGING_INBOX = "https://www.linkedin.com/messaging/compose/"
ON_MESSAGING = "/messaging/"
CONVO_LIST = "ul.msg-conversations-container__conversations-list"
CONVO_CARD = ".msg-conversation-card"
# The per-row unread FLAG is a class token on an inner container. The per-row
# unread COUNT is a separate element, div[aria-label="N unread message(s)"].
# .msg-conversation-listitem__unread-count DOES NOT EXIST - it was probed and
# came back zero on a list with four unread rows.
CONVO_UNREAD_CLASS = "msg-conversation-card__convo-item-container--unread"
CONVO_NAMES = ".msg-conversation-card__participant-names"
# Present on 8 of 10 rows, measured. A row parser that REQUIRES all three fields
# drops a fifth of the inbox and reports the rest as a complete read.
CONVO_SNIPPET = ".msg-conversation-card__message-snippet"
CONVO_TIME = "time.msg-conversation-card__time-stamp"
CONVO_UNREAD_COUNT = 'div[aria-label*="unread"]'
# The filter pills. read-inbox --unread drives the page's own filter rather than
# filtering rows itself, because the page knows what unread means and this tool
# is reading a class token.
INBOX_FILTER_PILL = "[data-test-messaging-inbox-filters__filter-pill]"
INBOX_UNREAD_PILL = '[data-test-messaging-inbox-filters__filter-pill="UNREAD"]'

# The composer. Same element wherever it is reached from - a profile's Message
# href and /messaging/ are the same page.
COMPOSER = 'div[role="textbox"].msg-form__contenteditable'
# type=submit INSIDE A FORM. That is why rule 0.2 exists: a form with a submit
# button sends on Enter, and Browser.type_text presses one Enter per newline.
COMPOSER_SEND = "button.msg-form__send-button"
# An EMPTY composer holds ONE character, not zero - measured. A guard that reads
# "empty" as length zero is wrong before anybody has typed.
COMPOSER_EMPTY_LEN = 1

# THE BUBBLE COUNT, and it is this selector and no other. Rule 0.2's guard
# counts messages before typing and asserts the count is unchanged before
# submitting. `.msg-s-message-list-content > li` ALSO contains a top-of-list
# marker, a hidden loader, a typing indicator, a quick-reply row and a
# bottom-of-list marker: it reported 9 where the answer was 4, and a guard that
# reads 9 before and 9 after cannot see a fragment that went.
THREAD_EVENT = "li.msg-s-message-list__event"
THREAD_BODY = ".msg-s-event-listitem__body"
THREAD_SENDER = ".msg-s-message-group__name"
THREAD_TIME = "time.msg-s-message-group__timestamp"
# THE THREAD HEADER, which is where rule 0.3's second naming is read from.
# Measured 2026-09-10 in docs/surveys/messaging-thread-read-2026-09-10.txt:
#   div#thread-detail-jump-target.msg-title-bar
#     div.shared-title-bar__title.msg-title-bar__title-bar-title
#       a.msg-thread__link-to-profile   href=/in/<slug>
# It carries BOTH the recipient's displayed name and their profile slug, so the
# person the composer is pointed at can be checked against --expect-name AND
# against the URL the caller passed - two namings off one control.
THREAD_TITLE_BAR = "div.msg-title-bar, #thread-detail-jump-target"
THREAD_HEADER_LINK = "a.msg-thread__link-to-profile"

# ONE CLICK ON ONE OF THESE SENDS A CANNED MESSAGE TO THAT PERSON. No composer,
# no confirmation, no draft stage. They sit at the end of an ordinary thread's
# message list and their accessible names begin with a common word - amendment
# A6. NOTHING in this toolkit may click a control by a name match that could
# resolve to one of these, and nothing inside a thread is clicked except the
# composer and its own Send, each identified positively before it is touched.
QUICK_REPLIES = "li.msg-s-message-list__quick-replies-container"
QUICK_REPLY_ARIA = re.compile(r"^Reply to conversation with ", re.I)
# The thread's own address, which only exists once a thread is open. A3: the
# LIST's rows carry no href and no id, so read-inbox cannot return one.
THREAD_URL = re.compile(r"/messaging/thread/([^/?#]+)", re.I)

# -- invitations received ---------------------------------------- 2026-09-10
INVITATIONS_RECEIVED = "https://www.linkedin.com/mynetwork/invitation-manager/received/"
# THE TWO CONTROLS ON THIS PAGE THAT CHANGE ANOTHER PERSON'S WORLD. They are
# named here so that a selector can be checked AGAINST them and refused, not so
# that anything can press them: accepting and declining are out of scope for
# Phase 3 (design section 6) and `invitations` is read-only in fact.
RECEIVED_ACCEPT_ARIA = re.compile(r"^Accept (.+?)(?:’|')s invitation$", re.I)
RECEIVED_IGNORE_ARIA = re.compile(r"^Ignore an invitation to connect from (.+)$", re.I)
# A4: the count the page publishes is a PER-FILTER PILL - "Focused (2)",
# "Verified (2)" on Received, "People (40)" on Sent. There is no "N pending
# invitations" sentence and no "No pending invitations" either; both were
# searched for and are absent. So a parse is checked against the pill of the
# SAME filter whose rows were parsed, and a pill that cannot be read means the
# zero-rows exception does not apply and zero rows is a FAIL.
RECEIVED_COUNT_PILL = re.compile(r"\b(Focused|Verified|Other|People)\s*\((\d[\d,]*)\)", re.I)
# WHICH FILTER'S ROWS ARE ON SCREEN, and it cannot be read off the Focused pill.
# Measured 2026-09-10: `Focused (1)` is a plain BUTTON with no aria-checked at
# all, and `Verified (1)` is a RADIO carrying aria-checked="false". So there is
# no attribute that says "Focused is on" - what there is, is a positive way to
# say it is NOT: no filter radio is checked.
#   no radio checked   -> the rows are the landing set, compare with Focused (N)
#   one radio checked  -> the rows are that filter's, compare with ITS pill
#   two or more        -> a page state this was not written against; refuse
RECEIVED_FILTER_RADIO = '[role="radio"]'
RECEIVED_DEFAULT_FILTER = "Focused"
# A received row carries the person, their headline, and the two controls. It
# carries NO note and NO time element - measured on the one row this account had
# on 2026-09-10, whose <time> count was zero. Design 4.6 asks for both. See
# kit/connections.invitations for what that means and what it does NOT prove.
RECEIVED_ROW_TIME = "time"

# -- follow / unfollow, the classic org page --------------------- 2026-09-10
# The cleanest control measured in this phase. THREE independent signals agree
# on the state and aria-pressed is the one to read:
#   not following  aria-pressed="false"  aria-label="Follow"     text "Follow"
#   following      aria-pressed="true"   aria-label="Following"  text "Following"
#                  and the class token `is-following`
# Follow controls for OTHER organisations appear further down the same page on
# recommendation cards, with the same classes MINUS the org-top-card- part, so
# the top card is scoped exactly as it is on a profile.
COMPANY_TOP_CARD = ".org-top-card"
FOLLOW_BUTTON = "button.org-company-follow-button[aria-pressed]"
FOLLOW_TOP_CARD_CLASS = "org-top-card-primary-actions"
FOLLOW_STATE_FOLLOWING = "is-following"
FOLLOW_NAME_FOLLOWING = re.compile(r"^Following$", re.I)
FOLLOW_NAME_FOLLOW = re.compile(r"^Follow$", re.I)
# One company URL redirected to /posts/?feedView=all and the other stayed put,
# measured on the same night. A verb that asserts on the URL it asked for fails
# on the first one, so what is asserted is the company KEY being in the final
# URL rather than the whole URL matching.
COMPANY_KEY_IN_URL = "/company/%s"

# -- invite to follow: the Page's own dialog --------------------- 2026-09-10
# Clicking "Invite connections" appends ?invite=true to the admin URL, so the
# dialog is reachable BY URL and nothing has to hunt for the trigger.
PAGE_INVITE_URL = "https://www.linkedin.com/company/%s/admin/?invite=true"
# THE DIALOG IS NOT IDENTIFIED BY ITS ACCESSIBLE NAME, AND THAT IS A CORRECTION
# TO A MEASUREMENT TAKEN SEVEN HOURS EARLIER. The first survey recorded
# `[role=dialog] aria-label="Invite to follow"`. On the second pass, same
# account, same Page, the SAME dialog carried `aria-label=null` and the words
# "Invite to follow" were only its heading text. A selector written against the
# first reading finds NOTHING on the second - the failure that looks exactly
# like "the dialog did not open".
#
# So it is found by role and then CONFIRMED by two things the dialog states
# about itself: the heading, and the credits line. Design section 1 asks for two
# passes on every surface precisely because of this, and this is the first time
# in Phase 3 that two passes of the same surface disagreed.
PAGE_INVITE_DIALOG = '[role="dialog"], [aria-modal="true"]'
PAGE_INVITE_DIALOG_NAME = "Invite to follow"
# ?invite=true on /admin/ REDIRECTS to /admin/dashboard/?invite=true - measured
# 2026-09-10. A verb asserting on the URL it asked for fails here, so what is
# asserted is the Page key AND invite=true surviving the redirect.
PAGE_INVITE_QUERY = "invite=true"
# Each candidate row carries a control whose accessible name NAMES THE PERSON:
# "Select <Full Name>". That is the positive identification a pick needs - the
# checkbox beside it is a bare input.ember-checkbox with no label at all, and
# twenty of them are on screen at once before anybody has searched.
PAGE_INVITE_SELECT_ARIA = re.compile(r"^Select (.+)$", re.I)
PAGE_INVITE_CHECKBOX = "input.ember-checkbox"
# Invite and Unselect all are BOTH disabled until something is selected, which
# is a usable pre-flight: a run that finds Invite enabled before it picked
# anybody is not looking at a fresh dialog.
PAGE_INVITE_UNSELECT_ALL = "Unselect all"
# "50/50 credits available - Credit refill: October 1, 2026". The FIRST number
# is what is left; the design did not know the line also carries a refill date.
# The before-and-after proof reads the first number, because the credit is the
# thing that is actually spent - a row that says "Invited" is not.
PAGE_INVITE_CREDITS = re.compile(r"(\d[\d,]*)\s*/\s*(\d[\d,]*)\s+credits?\s+available", re.I)
PAGE_INVITE_REFILL = re.compile(r"Credit refill:\s*([^\n]+)", re.I)
PAGE_INVITE_SEARCH = 'input[role="combobox"]'
PAGE_INVITE_OPTION = '[role="option"]'
PAGE_INVITE_SUBMIT = re.compile(r"^Invite$", re.I)
