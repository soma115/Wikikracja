/**
 * @file
 * DOM API module providing a clean interface for DOM manipulation operations.
 * Handles all UI updates, element queries, and DOM-related functionality for the chat application.
 */

import { Message, Room } from './templates.js';
import { openBigImage as _openBigImage } from './chat-core.js';
import {
    $,
    $$,
    _,
    escapeHtml,
    formatTime,
    removeNotification,
    setCaretPosition
} from './utility.js';
import { formatMessage as coreFormatMessage, getInputHtml } from './chat-core.js';

function encodeAttachmentName(filename) {
    return encodeURIComponent(filename).replace(/'/g, '%27');
}

/**
 * DOM API class for managing chat interface DOM operations
 * @class
 */
export default class DomApi {
    getRoomLinkDiv(room_id) {
        return $(`.tw-room-link[data-room-id="${room_id}"]`);
    }

    createRoomDiv(room_id, title, is_public, notifs_enabled, can_post = true) {
        const messageMaxLength = window.SITE_SETTINGS?.messageMaxLength ?? 500;
        const html = Room({ room_id, title, is_public, notifs_enabled, messageMaxLength });
        const container = $('.tw-chat-root-messages');
        container.innerHTML = '';
        container.insertAdjacentHTML('beforeend', html);
        const room = $('#room');
        if (!can_post) {
            const controls = $('.tw-chat-controls', room);
            if (controls) {
                controls.innerHTML = `<div class="tw-ec-readonly-notice"><i class="fas fa-lock"></i> ${_("Only approved helpers can write here.")}</div>`;
                controls.classList.add('tw-chat-controls--readonly');
            }
        }
        return room;
    }

    getRoom() {
        return $('#room');
    }

    getMessagesDiv() {
        const room = this.getRoom();
        return room ? $('.tw-chat-messages', room) : null;
    }

    buildMessageHtml(room_id, user_id, avatar_url, citizen_color_class, message_id, username, message, upvotes, downvotes, vote, own, edited, attachments, original_ts, latest_ts, reply_to = null, reactions = null, your_reactions = null, read_by = null, upvoters = null, downvoters = null) {
        const formatted = this.formatMessage(message);
        return Message({
            room_id, user_id, avatar_url, citizen_color_class, message_id, username,
            message: this.wrapExpandable(formatted),
            raw_message: message,
            upvotes, downvotes, vote, own, edited, attachments,
            original_ts, latest_ts: formatTime(latest_ts),
            type: this.getRoomType(room_id),
            reply_to,
            reactions: reactions ?? { bulb: 0, question: 0 },
            your_reactions: your_reactions ?? [],
            read_by: read_by ?? [],
            upvoters: upvoters ?? [],
            downvoters: downvoters ?? [],
        });
    }

    addMessage(room_id, user_id, avatar_url, citizen_color_class, message_id, username, message, upvotes, downvotes, vote, own, edited, attachments, original_ts, latest_ts, reply_to = null, reactions = null, your_reactions = null, read_by = null, upvoters = null, downvoters = null, temp_id = null) {
        const html = this.buildMessageHtml(room_id, user_id, avatar_url, citizen_color_class, message_id, username, message, upvotes, downvotes, vote, own, edited, attachments, original_ts, latest_ts, reply_to, reactions, your_reactions, read_by, upvoters, downvoters);

        const messagesDiv = this.getMessagesDiv();
        messagesDiv?.insertAdjacentHTML('beforeend', html);
        this.getVoteDiv(message_id, vote)?.classList.add('tw-active');
        const msgDiv = this.getMessageDiv(message_id);
        if (temp_id && msgDiv) {
            msgDiv.dataset.tempId = temp_id;
            msgDiv.classList.add('tw-chat-message--pending');
        }
    }

    confirmMessage(temp_id, real_id) {
        const msgDiv = this.getMessagesDiv()?.querySelector(`.tw-chat-message[data-temp-id="${temp_id}"]`);
        if (!msgDiv) return;
        msgDiv.classList.remove('tw-chat-message--pending', 'tw-chat-message--failed');
        msgDiv.dataset.messageId = real_id;
        msgDiv.querySelectorAll(`[data-message-id="${temp_id}"]`).forEach(el => {
            el.dataset.messageId = real_id;
        });
        delete msgDiv.dataset.tempId;
    }

    failMessage(temp_id) {
        const msgDiv = this.getMessagesDiv()?.querySelector(`.tw-chat-message[data-temp-id="${temp_id}"]`);
        if (!msgDiv) return;
        msgDiv.classList.remove('tw-chat-message--pending');
        msgDiv.classList.add('tw-chat-message--failed');
    }

    getMessageDiv(message_id) {
        return $(`.tw-chat-message[data-message-id="${message_id}"]`);
    }

    scrollToMessage(message_id) {
        const message = this.getMessageDiv(message_id);
        if (!message) return false;
        message.scrollIntoView();
        message.classList.add('tw-msg-highlight');
        setTimeout(() => message.classList.remove('tw-msg-highlight'), 5000);
        return true;
    }

    updateVoteBar(message_id, upvotes, downvotes) {
        const msgDiv = this.getMessageDiv(message_id);
        if (!msgDiv) return;
        const total = upvotes + downvotes;
        const barWrap = $('.tw-vote-bar-wrap', msgDiv);
        const barFill = $('.tw-vote-bar-fill', msgDiv);
        const barLabel = $('.tw-vote-bar-label', msgDiv);
        if (total >= 3) {
            const pct = Math.round((upvotes / total) * 100);
            const cls = pct >= 60 ? 'tw-vote-bar--positive' : (pct >= 40 ? 'tw-vote-bar--neutral' : 'tw-vote-bar--negative');
            if (barFill) {
                barFill.style.setProperty('--vote-progress', `${pct}%`);
                barFill.className = `tw-vote-bar-fill ${cls}`;
            }
            if (barLabel) barLabel.textContent = `${pct}% popiera`;
            if (barWrap) barWrap.classList.remove('tw-d-none');
            if (barLabel) barLabel.classList.remove('tw-d-none');
        } else {
            if (barWrap) barWrap.classList.add('tw-d-none');
            if (barLabel) barLabel.classList.add('tw-d-none');
        }
    }

    getMessageUpvotesCountDiv(message_id) {
        const msgDiv = this.getMessageDiv(message_id);
        return msgDiv ? $(".tw-msg-upvotes", msgDiv) : null;
    }

    getMessageDownvotesCountDiv(message_id) {
        const msgDiv = this.getMessageDiv(message_id);
        return msgDiv ? $(".tw-msg-downvotes", msgDiv) : null;
    }

    getVoteDiv(message_id, vote) {
        const msgDiv = this.getMessageDiv(message_id);
        return msgDiv ? $(`.tw-msg-vote[data-event-name="${vote}"]`, msgDiv) : null;
    }

    editMessageText(message_id, text, ts) {
        this.getMessageTimeDiv(message_id).textContent = formatTime(ts);
        const msgDiv = this.getMessageDiv(message_id);
        if (msgDiv) {
            const msgText = $(".tw-msg-text", msgDiv);
            if (msgText) {
                msgText.dataset.raw = text;
                msgText.innerHTML = this.wrapExpandable(this.formatMessage(text));
                // Re-evaluate overflow after content change
                msgText.querySelectorAll('.tw-expandable').forEach(exp => exp.classList.remove('tw-has-overflow'));
                requestAnimationFrame(() => this.markOverflow(msgText));
                return msgText;
            }
        }
        return null;
    }

    updateMessageAttachments(message_id, attachments) {
        const message_div = this.getMessageDiv(message_id);
        if (!message_div) return;
        const attachment_container = $('.tw-attachment-image-container', message_div);
        if (!attachment_container) return;
        attachment_container.innerHTML = '';
        if (attachments?.images?.length > 0) {
            for (const filename of attachments.images) {
                const img = document.createElement('img');
                img.className = 'tw-attached-image';
                img.loading = 'lazy';
                img.src = `/media/uploads/${encodeAttachmentName(filename)}`;
                attachment_container.appendChild(img);
            }
        }
    }

    showHistoryButton(message_id) {
        const msgDiv = this.getMessageDiv(message_id);
        if (msgDiv) {
            $(".tw-show-history", msgDiv).classList.remove('tw-d-none');
        }
    }

    getRoomType(room_id) {
        return $(`.tw-room-link[data-room-id="${room_id}"]`)?.getAttribute("data-room-type") ?? null;
    }

    getLastMessageBanner() {
        const messagesDiv = this.getMessagesDiv();
        return messagesDiv ? $$('.tw-date-banner', messagesDiv) : [];
    }

    getMessageText(message_id) {
        const msgDiv = this.getMessageDiv(message_id);
        if (!msgDiv) return '';
        const msgText = $(".tw-msg-text", msgDiv);
        if (!msgText) return '';
        return msgText.dataset.raw ?? msgText.innerHTML ?? '';
    }

    formatMessage(raw_message) {
        return coreFormatMessage(raw_message);
    }

    // Wraps message in expandable shell — CSS max-height clips it; markOverflow() disables chrome when content fits.
    wrapExpandable(formattedHtml) {
        return `<div class="tw-expandable">` +
            `<div class="tw-expandable-body">${formattedHtml}</div>` +
            `<div class="tw-expandable-hint">… pokaż więcej</div>` +
            `</div>`;
    }

    // After inserting into DOM, mark expandables that actually overflow — hint i klikalnosc dopiero po potwierdzeniu.
    markOverflow(container) {
        container?.querySelectorAll('.tw-expandable:not(.tw-is-open)').forEach(exp => {
            const body = exp.querySelector('.tw-expandable-body');
            if (!body) return;
            exp.classList.toggle('tw-has-overflow', body.scrollHeight > body.clientHeight);
        });
    }

    getPreviewDiv() {
        return $(".tw-preview-images");
    }

    getPreviewContainer() {
        return $(`.tw-image-preview-container`);
    }

    seenChat(room_id) {
        const roomLink = this.getRoomLinkDiv(room_id);
        roomLink?.classList.remove("tw-room-link--not-seen");
        // Swap unread dot → read circle
        const unreadDot = roomLink?.querySelector('.tw-nav-status--unread');
        if (unreadDot) {
            unreadDot.classList.remove('tw-nav-status--unread');
            unreadDot.classList.add('tw-nav-status--read');
            unreadDot.removeAttribute('aria-label');
            unreadDot.setAttribute('aria-hidden', 'true');
        }
        this.setRoomSeenIconState(room_id, true);
        if ($$('.tw-room-link--not-seen').length === 0) {
            removeNotification();
        }
        // Trigger unread filter update if it's active
        if (typeof window.updateUnreadFilter === 'function') {
            window.updateUnreadFilter();
        }
    }

    updateOnline(room_id, is_online) {
        const room_link = this.getRoomLinkDiv(room_id);
        if (!room_link) return;
        room_link.classList.toggle('tw-room-link--online', is_online);
        room_link.classList.toggle('tw-room-link--offline', !is_online);
    }

    getMessageTimeDiv(message_id) {
        return $(`.tw-message-timestamp[data-message-id="${message_id}"]`);
    }

    getMessageInput() {
        return $(`#message-input`);
    }

    getEnteredText() {
        const el = this.getMessageInput();
        if (!el) return '';
        if (el.isContentEditable) {
            // Canonical serializer (richtext-core.js) — single source of truth so newline
            // handling matches chat-embedded.js (empty-line blocks → single <br>, trailing
            // filler <br> stripped). Avoids the double-spacing divergence of the old inline impl.
            return getInputHtml(el).replace(/(<br\s*\/?>\s*)+$/, '');
        }
        return el.value ?? '';
    }

    getVisibleTextLength() {
        const el = this.getMessageInput();
        if (!el) return 0;
        return el.isContentEditable ? (el.textContent || '').length : (el.value || '').length;
    }

    getAnonymousValue() {
        return $(`#anonymous-toggle`)?.classList.contains('tw-active') ?? false;
    }

    getFileInput() {
        return $(`#file-input`);
    }

    getFiles() {
        return this.getFileInput()?.files ?? null;
    }

    clearFiles() {
        const fileInput = $(`#file-input`);
        if (fileInput) fileInput.value = "";
        this.getPreviewContainer().classList.add('tw-d-none');
        this.getPreviewDiv().innerHTML = '';
    }

    getEditedMessageId() {
        return this.getMessageInput()?.dataset.editMessage ?? null;
    }

    setEditing(message_id) {
        const text = this.getMessageText(message_id);
        this.getFileInput()?.removeAttribute('disabled');
        const input = this.getMessageInput();
        if (input) {
            input.dataset.editMessage = message_id;
            input.dataset.originalMessageText = text;
            if (input.isContentEditable) {
                input.innerHTML = text;
            } else {
                input.value = text;
            }
            input.classList.add('tw-editing');
        }
        this.loadEditingAttachments(message_id, this.getMessageAttachments(message_id));
        if (input?.isContentEditable) {
            input.focus();
            const range = document.createRange();
            range.selectNodeContents(input);
            range.collapse(false);
            window.getSelection()?.removeAllRanges();
            window.getSelection()?.addRange(range);
        } else {
            setCaretPosition(this.getMessageInput(), text.length);
        }
        input?.dispatchEvent(new Event('input'));
    }

    stopEditing() {
        this.getFileInput()?.removeAttribute('disabled');
        const input = this.getMessageInput();
        if (input) {
            delete input.dataset.editMessage;
            delete input.dataset.removedAttachments;
            delete input.dataset.originalMessageText;
            if (input.isContentEditable) {
                input.innerHTML = '';
            } else {
                input.value = '';
            }
            input.classList.remove('tw-editing');
            input.dispatchEvent(new InputEvent('input', { bubbles: true }));
        }
        this.clearFiles();
    }

    openBigImage(srcs, startIndex = 0) {
        _openBigImage(srcs, startIndex);
    }

    closeBigImage() {
        document.getElementById('image-viewer-overlay')?.remove();
        document.body.classList.remove('tw-modal-open');
    }

    getLatestOwnMessage() {
        const messagesDiv = this.getMessagesDiv();
        if (!messagesDiv) return null;
        const ownMessages = $$('.tw-chat-message.tw-chat-message--own', messagesDiv);
        return ownMessages.length > 0 ? ownMessages[ownMessages.length - 1] : null;
    }

    isEditing() {
        return !!this.getEditedMessageId();
    }

    removeNoMessagesBanner() {
        $('.tw-empty-chat-message')?.remove();
    }

    setRoomTitle(title) {
        const el = $("#room-title");
        if (el) el.textContent = title;
    }

    setRoomNotifications(room_id, is_enabled) {
        const btn = $(`.tw-notif-switch[data-room-id='${room_id}']`);
        if (!btn) return;
        btn.disabled = false;
        btn.dataset.enabled = is_enabled;
        const icon = $("i", btn);
        if (icon) {
            icon.classList.toggle('fa-bell', is_enabled);
            icon.classList.toggle('fa-bell-slash', !is_enabled);
        }
        const label = btn.querySelector('.tw-notif-label');
        if (label) label.textContent = is_enabled ? _('Mute room') : _('Unmute room');
        const meta = btn.closest('.tw-room-link')?.querySelector('.tw-room-link-meta');
        if (meta) {
            meta.dataset.muted = is_enabled ? 'false' : 'true';
            let mutedIcon = meta.querySelector('.tw-room-link-muted-icon');
            if (!is_enabled) {
                if (!mutedIcon) {
                    mutedIcon = document.createElement('i');
                    mutedIcon.className = 'fas fa-bell-slash tw-room-link-muted-icon';
                    mutedIcon.title = _('Muted');
                    meta.appendChild(mutedIcon);
                }
            } else {
                mutedIcon?.remove();
            }
        }
    }

    setRoomSeenIconState(room_id, is_seen) {
        const btn = $(`.tw-seen-switch[data-room-id='${room_id}']`);
        if (!btn) return;
        btn.dataset.seen = is_seen.toString();
        const icon = $("i", btn);
        if (icon) {
            icon.classList.toggle('fa-eye', is_seen);
            icon.classList.toggle('fa-eye-slash', !is_seen);
        }
    }

    clearRoomData() {
        const messagesDiv = this.getMessagesDiv();
        if (messagesDiv) messagesDiv.innerHTML = '';
        this.clearFiles();
        this.stopEditing();
        messagesDiv?.insertAdjacentHTML('beforeend', "<p class='tw-empty-chat-message'>" + _("Loading...") + "</p>");
    }

    showCopyFeedback(button, message, success) {
        if (!button) return;
        const tooltip = document.createElement('span');
        tooltip.className = "tw-copy-feedback tw-badge-status";
        tooltip.textContent = message;
        tooltip.classList.add(success ? 'tw-badge-success' : 'tw-badge-danger');
        button.appendChild(tooltip);
        setTimeout(() => {
            tooltip.classList.add('tw-copy-feedback--out');
            setTimeout(() => tooltip.remove(), 200);
        }, 1200);
    }

    getMessageAttachments(message_id) {
        const message_div = this.getMessageDiv(message_id);
        const attachments = { images: [] };
        if (message_div) {
            $$('.tw-attached-image', message_div).forEach(img => {
                const encoded = img.getAttribute('src').split('/').pop();
                attachments.images.push(decodeURIComponent(encoded));
            });
        }
        return attachments.images.length > 0 ? attachments : {};
    }

    loadEditingAttachments(message_id, attachments) {
        const preview_container = this.getPreviewDiv();
        if (preview_container) preview_container.innerHTML = '';
        if (!attachments?.images?.length) {
            this.getPreviewContainer().classList.add('tw-d-none');
            return;
        }
        this.getPreviewContainer().classList.remove('tw-d-none');
        for (let i = 0; i < attachments.images.length; i++) {
            const filename = attachments.images[i];
            const wrapper = document.createElement('div');
            wrapper.className = 'tw-image-preview-wrapper';

            const img = document.createElement('img');
            img.className = 'tw-image-preview';
            img.id = `preview-existing-${i}`;
            img.src = `/media/uploads/${encodeAttachmentName(filename)}`;
            img.setAttribute('data-filename', filename);

            const btn = document.createElement('button');
            btn.className = 'tw-btn tw-btn-sm tw-btn-danger tw-remove-existing-attachment tw-image-preview-remove';
            btn.setAttribute('data-filename', filename);
            btn.type = 'button';
            btn.textContent = '×';

            wrapper.appendChild(img);
            wrapper.appendChild(btn);
            preview_container?.appendChild(wrapper);
        }
    }

    getRemovedAttachments() {
        const input = this.getMessageInput();
        return input?.dataset.removedAttachments ? JSON.parse(input.dataset.removedAttachments) : [];
    }

    addRemovedAttachment(filename) {
        const removed = this.getRemovedAttachments();
        if (!removed.includes(filename)) {
            removed.push(filename);
            this.getMessageInput().dataset.removedAttachments = JSON.stringify(removed);
        }
    }

    getOriginalMessageText(message_id) {
        return this.getMessageInput()?.dataset.originalMessageText ?? '';
    }

    /**
     * Update the sticky breadcrumb above the message list.
     * @param {Array<{label: string, active?: boolean}>} parts
     */
    updateBreadcrumb(parts) {
        const bc = $('#chat-breadcrumb');
        if (!bc) return;
        bc.innerHTML = parts.map((p, i) =>
            `<span class="tw-bc-seg${p.active ? ' tw-bc-seg--active' : ''}">${p.label}</span>` +
            (i < parts.length - 1 ? '<span class="tw-bc-sep" aria-hidden="true"> › </span>' : '')
        ).join('');
    }

    // Klasy widoku (.room-active / .room-list-showing / .room-list-hidden) są
    // wyprowadzane ze stanu przez renderChatView() w chat.js — domapi nie
    // podejmuje decyzji, który panel jest widoczny.

    updateSidebarForMessage(msg, {reorder = true, bumpActivity = reorder} = {}) {
        const roomLink = document.querySelector(`.tw-room-link[data-room-id="${msg.room_id}"]`);
        if (!roomLink) return;

        // Pull the room out of archive as soon as a new message arrives.
        // `new` is true for other users; for the sender `new` is false and `own` is true.
        if ((msg.new || msg.own) && roomLink.dataset.roomArchived === 'true') {
            roomLink.dataset.roomArchived = 'false';
            if (msg.own) {
                roomLink.classList.remove('tw-room-link--not-seen');
            } else {
                roomLink.classList.add('tw-room-link--not-seen');
            }
            const statusEl = roomLink.querySelector('.tw-room-link-status');
            if (statusEl) {
                if (msg.own) {
                    statusEl.innerHTML = '<span class="tw-nav-status tw-nav-status--read" aria-hidden="true"></span>';
                } else {
                    statusEl.innerHTML = '<span class="tw-nav-status tw-nav-status--unread" aria-label="' + _('Unread') + '"></span>';
                }
            }
        }

        if (bumpActivity) {
            roomLink.dataset.lastActivity = Math.floor(msg.timestamp / 1000);
            const dateEl = roomLink.querySelector('.tw-room-link-date');
            if (dateEl) dateEl.textContent = _relativeChatDate(msg.timestamp);
        }

        const senderEl = roomLink.querySelector('.tw-room-link-sender');
        if (senderEl) senderEl.textContent = (msg.username || '—') + ':';

        const snippetEl = roomLink.querySelector('.tw-room-link-snippet');
        if (snippetEl) {
            const tmp = document.createElement('div');
            tmp.innerHTML = msg.message || '';
            const text = tmp.textContent.replace(/\s+/g, ' ').trim();
            snippetEl.textContent = text || _('attachment');
        }

        if (reorder) {
            const container = roomLink.closest('.tw-chat-cat-content, #room-list-flat');
            if (container && container.firstElementChild !== roomLink) {
                container.prepend(roomLink);
            }
        }
    }

}

const _DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
const _MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function _relativeChatDate(tsMs) {
    const now = new Date();
    const d = new Date(tsMs);
    const todayMidnight = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const msgMidnight = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    const deltaDays = Math.round((todayMidnight - msgMidnight) / 86400000);
    if (deltaDays === 0) return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
    if (deltaDays === 1) return _('Yesterday');
    if (deltaDays < 7) return _(_DAYS[d.getDay()]);
    if (d.getFullYear() === now.getFullYear()) return `${d.getDate()} ${_(_MONTHS[d.getMonth()])}`;
    return `${d.getDate()} ${_(_MONTHS[d.getMonth()])} ${d.getFullYear()}`;
}
