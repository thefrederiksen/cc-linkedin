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
