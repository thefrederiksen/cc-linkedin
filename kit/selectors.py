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
