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

/**
 * DOM API class for managing chat interface DOM operations
 * @class
 */
export default class DomApi {
    getRoomLinkDiv(room_id) {
        return $(`.room-link[data-room-id="${room_id}"]`);
    }

    createRoomDiv(room_id, title, is_public, notifs_enabled) {
        const messageMaxLength = window.SITE_SETTINGS?.messageMaxLength ?? 500;
        const html = Room({ room_id, title, is_public, notifs_enabled, messageMaxLength });
        const container = $('.chat-root-messages');
        container.innerHTML = '';
        container.insertAdjacentHTML('beforeend', html);
        return $('#room');
    }

    getRoom() {
        return $('#room');
    }

    getMessagesDiv() {
        const room = this.getRoom();
        return room ? $('.messages', room) : null;
    }

    buildMessageHtml(room_id, user_id, avatar_url, citizen_color_class, message_id, username, message, upvotes, downvotes, vote, own, edited, attachments, original_ts, latest_ts, reply_to = null, reactions = null, your_reactions = null, read_by = null) {
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
        });
    }

    addMessage(room_id, user_id, avatar_url, citizen_color_class, message_id, username, message, upvotes, downvotes, vote, own, edited, attachments, original_ts, latest_ts, reply_to = null, reactions = null, your_reactions = null, read_by = null, temp_id = null) {
        const html = this.buildMessageHtml(room_id, user_id, avatar_url, citizen_color_class, message_id, username, message, upvotes, downvotes, vote, own, edited, attachments, original_ts, latest_ts, reply_to, reactions, your_reactions, read_by);

        const messagesDiv = this.getMessagesDiv();
        messagesDiv?.insertAdjacentHTML('beforeend', html);
        this.getVoteDiv(message_id, vote)?.classList.add('active');
        const msgDiv = this.getMessageDiv(message_id);
        if (temp_id && msgDiv) {
            msgDiv.dataset.tempId = temp_id;
            msgDiv.classList.add('message--pending');
        }
    }

    confirmMessage(temp_id, real_id) {
        const msgDiv = this.getMessagesDiv()?.querySelector(`.message[data-temp-id="${temp_id}"]`);
        if (!msgDiv) return;
        msgDiv.classList.remove('message--pending', 'message--failed');
        msgDiv.dataset.messageId = real_id;
        msgDiv.querySelectorAll(`[data-message-id="${temp_id}"]`).forEach(el => {
            el.dataset.messageId = real_id;
        });
        delete msgDiv.dataset.tempId;
    }

    failMessage(temp_id) {
        const msgDiv = this.getMessagesDiv()?.querySelector(`.message[data-temp-id="${temp_id}"]`);
        if (!msgDiv) return;
        msgDiv.classList.remove('message--pending');
        msgDiv.classList.add('message--failed');
    }

    getMessageDiv(message_id) {
        return $(`.message[data-message-id="${message_id}"]`);
    }

    scrollToMessage(message_id) {
        const message = this.getMessageDiv(message_id);
        if (!message) return false;
        message.scrollIntoView();
        message.classList.add('msg-highlight');
        setTimeout(() => message.classList.remove('msg-highlight'), 5000);
        return true;
    }

    updateVoteBar(message_id, upvotes, downvotes) {
        const msgDiv = this.getMessageDiv(message_id);
        if (!msgDiv) return;
        const total = upvotes + downvotes;
        const barWrap = $('.vote-bar-wrap', msgDiv);
        const barFill = $('.vote-bar-fill', msgDiv);
        const barLabel = $('.vote-bar-label', msgDiv);
        if (total >= 3) {
            const pct = Math.round((upvotes / total) * 100);
            const cls = pct >= 60 ? 'vote-bar--positive' : (pct >= 40 ? 'vote-bar--neutral' : 'vote-bar--negative');
            if (barFill) {
                barFill.style.setProperty('--vote-progress', `${pct}%`);
                barFill.className = `vote-bar-fill ${cls}`;
            }
            if (barLabel) barLabel.textContent = `${pct}% popiera`;
            if (barWrap) barWrap.style.display = '';
            if (barLabel) barLabel.style.display = '';
        } else {
            if (barWrap) barWrap.style.display = 'none';
            if (barLabel) barLabel.style.display = 'none';
        }
    }

    getMessageUpvotesCountDiv(message_id) {
        const msgDiv = this.getMessageDiv(message_id);
        return msgDiv ? $(".msg-upvotes", msgDiv) : null;
    }

    getMessageDownvotesCountDiv(message_id) {
        const msgDiv = this.getMessageDiv(message_id);
        return msgDiv ? $(".msg-downvotes", msgDiv) : null;
    }

    getVoteDiv(message_id, vote) {
        const msgDiv = this.getMessageDiv(message_id);
        return msgDiv ? $(`.msg-vote[data-event-name="${vote}"]`, msgDiv) : null;
    }

    editMessageText(message_id, text, ts) {
        this.getMessageTimeDiv(message_id).textContent = formatTime(ts);
        const msgDiv = this.getMessageDiv(message_id);
        if (msgDiv) {
            const msgText = $(".msg-text", msgDiv);
            if (msgText) {
                msgText.dataset.raw = text;
                msgText.innerHTML = this.wrapExpandable(this.formatMessage(text));
                // Re-evaluate overflow after content change
                msgText.querySelectorAll('.expandable').forEach(exp => exp.classList.remove('has-overflow'));
                requestAnimationFrame(() => this.markOverflow(msgText));
                return msgText;
            }
        }
        return null;
    }

    updateMessageAttachments(message_id, attachments) {
        const message_div = this.getMessageDiv(message_id);
        if (!message_div) return;
        const attachment_container = $('.attachment-image-container', message_div);
        if (attachment_container) {
            attachment_container.innerHTML = '';
            if (attachments?.images?.length > 0) {
                for (const filename of attachments.images) {
                    attachment_container.insertAdjacentHTML('beforeend', `<img class='attached-image' src='/media/uploads/${filename}'>`);
                }
            }
        }
    }

    showHistoryButton(message_id) {
        const msgDiv = this.getMessageDiv(message_id);
        if (msgDiv) {
            $(".show-history", msgDiv).style.display = '';
        }
    }

    getRoomType(room_id) {
        return $(`.room-link[data-room-id="${room_id}"]`)?.getAttribute("data-room-type") ?? null;
    }

    getLastMessageBanner() {
        const messagesDiv = this.getMessagesDiv();
        return messagesDiv ? $$('.date-banner', messagesDiv) : [];
    }

    getMessageText(message_id) {
        const msgDiv = this.getMessageDiv(message_id);
        if (!msgDiv) return '';
        const msgText = $(".msg-text", msgDiv);
        if (!msgText) return '';
        return msgText.dataset.raw ?? msgText.innerHTML ?? '';
    }

    formatMessage(raw_message) {
        return coreFormatMessage(raw_message);
    }

    // Wraps message in expandable shell — CSS max-height clips it; markOverflow() disables chrome when content fits.
    wrapExpandable(formattedHtml) {
        return `<div class="expandable">` +
            `<div class="expandable-body">${formattedHtml}</div>` +
            `<div class="expandable-hint">… pokaż więcej</div>` +
            `</div>`;
    }

    // After inserting into DOM, mark expandables that actually overflow — hint i klikalnosc dopiero po potwierdzeniu.
    markOverflow(container) {
        container?.querySelectorAll('.expandable:not(.is-open)').forEach(exp => {
            const body = exp.querySelector('.expandable-body');
            if (!body) return;
            exp.classList.toggle('has-overflow', body.scrollHeight > body.clientHeight);
        });
    }

    getPreviewDiv() {
        return $(".preview-images");
    }

    getPreviewContainer() {
        return $(`.image-preview-container`);
    }

    seenChat(room_id) {
        const roomLink = this.getRoomLinkDiv(room_id);
        roomLink?.classList.remove("room-not-seen");
        // Swap unread dot → read circle
        const unreadDot = roomLink?.querySelector('.nav-status--unread');
        if (unreadDot) {
            unreadDot.classList.remove('nav-status--unread');
            unreadDot.classList.add('nav-status--read');
            unreadDot.removeAttribute('aria-label');
            unreadDot.setAttribute('aria-hidden', 'true');
        }
        this.setRoomSeenIconState(room_id, true);
        if ($$('.room-not-seen').length === 0) {
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
        room_link.classList.toggle('online', is_online);
        room_link.classList.toggle('offline', !is_online);
    }

    getMessageTimeDiv(message_id) {
        return $(`.message-timestamp[data-message-id="${message_id}"]`);
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
        return $(`#anonymous-toggle`)?.classList.contains('active') ?? false;
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
        this.getPreviewContainer().style.display = 'none';
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
            input.style.borderColor = 'var(--color-warning)';
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
            input.style.borderColor = '';
            input.dispatchEvent(new InputEvent('input', { bubbles: true }));
        }
        this.clearFiles();
    }

    openBigImage(srcs, startIndex = 0) {
        _openBigImage(srcs, startIndex);
    }

    closeBigImage() {
        document.getElementById('image-viewer-overlay')?.remove();
        document.body.classList.remove('modal-open');
    }

    getLatestOwnMessage() {
        const messagesDiv = this.getMessagesDiv();
        if (!messagesDiv) return null;
        const ownMessages = $$('.message.own', messagesDiv);
        return ownMessages.length > 0 ? ownMessages[ownMessages.length - 1] : null;
    }

    isEditing() {
        return !!this.getEditedMessageId();
    }

    removeNoMessagesBanner() {
        $('.empty-chat-message')?.remove();
    }

    setRoomTitle(title) {
        const el = $("#room-title");
        if (el) el.textContent = title;
    }

    setRoomNotifications(room_id, is_enabled) {
        const btn = $(`.notif-switch[data-room-id='${room_id}']`);
        if (!btn) return;
        btn.disabled = false;
        btn.dataset.enabled = is_enabled;
        const icon = $("i", btn);
        if (icon) {
            icon.classList.toggle('fa-bell', is_enabled);
            icon.classList.toggle('fa-bell-slash', !is_enabled);
        }
        const label = btn.querySelector('.notif-label');
        if (label) label.textContent = is_enabled ? _('Mute room') : _('Unmute room');
        const meta = btn.closest('.room-link')?.querySelector('.room-link__meta');
        if (meta) {
            meta.dataset.muted = is_enabled ? 'false' : 'true';
            let mutedIcon = meta.querySelector('.room-link__muted-icon');
            if (!is_enabled) {
                if (!mutedIcon) {
                    mutedIcon = document.createElement('i');
                    mutedIcon.className = 'fas fa-bell-slash room-link__muted-icon';
                    mutedIcon.title = _('Muted');
                    meta.appendChild(mutedIcon);
                }
            } else {
                mutedIcon?.remove();
            }
        }
    }

    setRoomSeenIconState(room_id, is_seen) {
        const btn = $(`.seen-switch[data-room-id='${room_id}']`);
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
        messagesDiv?.insertAdjacentHTML('beforeend', "<p class='empty-chat-message'>" + _("Loading...") + "</p>");
    }

    showCopyFeedback(button, message, success) {
        if (!button) return;
        const tooltip = document.createElement('span');
        tooltip.className = "copy-feedback badge-status";
        tooltip.textContent = message;
        tooltip.classList.add(success ? 'badge-success' : 'badge-danger');
        button.appendChild(tooltip);
        setTimeout(() => {
            tooltip.style.transition = 'opacity 0.2s';
            tooltip.style.opacity = '0';
            setTimeout(() => tooltip.remove(), 200);
        }, 1200);
    }

    getMessageAttachments(message_id) {
        const message_div = this.getMessageDiv(message_id);
        const attachments = { images: [] };
        if (message_div) {
            $$('.attached-image', message_div).forEach(img => {
                attachments.images.push(img.getAttribute('src').split('/').pop());
            });
        }
        return attachments.images.length > 0 ? attachments : {};
    }

    loadEditingAttachments(message_id, attachments) {
        const preview_container = this.getPreviewDiv();
        if (preview_container) preview_container.innerHTML = '';
        if (!attachments?.images?.length) {
            this.getPreviewContainer().style.display = 'none';
            return;
        }
        this.getPreviewContainer().style.display = '';
        for (let i = 0; i < attachments.images.length; i++) {
            const filename = attachments.images[i];
            preview_container?.insertAdjacentHTML('beforeend', `<div class="image-preview-wrapper">
                <img class='image-preview' id='preview-existing-${i}' src='/media/uploads/${filename}' data-filename='${filename}'>
                <button class="btn btn-sm btn-danger remove-existing-attachment image-preview-remove"
                    data-filename="${filename}" type="button">×</button>
            </div>`);
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
            `<span class="bc-seg${p.active ? ' bc-seg--active' : ''}">${p.label}</span>` +
            (i < parts.length - 1 ? '<span class="bc-sep" aria-hidden="true"> › </span>' : '')
        ).join('');
    }

    showFoldedRoomHeader() {
        const chatRooms = $(".chat-rooms");
        if (chatRooms) {
            chatRooms.classList.add('room-active');
            chatRooms.classList.remove('room-list-showing');
        }
    }

    hideFoldedRoomHeader() {
        const chatRooms = $(".chat-rooms");
        if (chatRooms) {
            chatRooms.classList.remove('room-active');
            chatRooms.classList.remove('room-list-showing');
        }
    }

    updateSidebarForMessage(msg, {reorder = true, bumpActivity = reorder} = {}) {
        const roomLink = document.querySelector(`.room-link[data-room-id="${msg.room_id}"]`);
        if (!roomLink) return;

        // Pull the room out of archive as soon as a new message arrives.
        // `new` is true for other users; for the sender `new` is false and `own` is true.
        if ((msg.new || msg.own) && roomLink.dataset.roomArchived === 'true') {
            roomLink.dataset.roomArchived = 'false';
            if (msg.own) {
                roomLink.classList.remove('room-not-seen');
            } else {
                roomLink.classList.add('room-not-seen');
            }
            const statusEl = roomLink.querySelector('.room-link__status');
            if (statusEl) {
                if (msg.own) {
                    statusEl.innerHTML = '<span class="nav-status nav-status--read" aria-hidden="true"></span>';
                } else {
                    statusEl.innerHTML = '<span class="nav-status nav-status--unread" aria-label="' + _('Unread') + '"></span>';
                }
            }
        }

        if (bumpActivity) {
            roomLink.dataset.lastActivity = Math.floor(msg.timestamp / 1000);
            const dateEl = roomLink.querySelector('.room-link__date');
            if (dateEl) dateEl.textContent = _relativeChatDate(msg.timestamp);
        }

        const senderEl = roomLink.querySelector('.room-link__sender');
        if (senderEl) senderEl.textContent = (msg.username || '—') + ':';

        const snippetEl = roomLink.querySelector('.room-link__snippet');
        if (snippetEl) {
            const tmp = document.createElement('div');
            tmp.innerHTML = msg.message || '';
            const text = tmp.textContent.replace(/\s+/g, ' ').trim();
            snippetEl.textContent = text || _('attachment');
        }

        if (reorder) {
            const container = roomLink.closest('.nav-cat-content, #room-list-flat');
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
