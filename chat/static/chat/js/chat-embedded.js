/**
 * @file chat-embedded.js
 * Embedded chat widget — reużywa Message template i CSS z głównego czatu.
 *
 * Użycie w template:
 *   <div class="embedded-chat" data-room-id="42" data-csrf="{{ csrf_token }}"></div>
 *   <script type="module" src="{% static 'chat/js/chat-embedded.js' %}"></script>
 */

import { clearReplyTarget, createEditHandler, createImageClickHandler, createQuoteJumpHandler, createReactionHandler, createReplyHandler, createVoteHandler, formatMessage, getInputHtml, handleEnterKey, initFormattingToolbar, initGlobalPasteImageHandler, insertPlainTextAtCaret, setReplyTarget, updateCounter, uploadFiles } from './chat-core.js';
import { Message } from './templates.js';
import { _, formatDate, formatTime } from './utility.js';
import { getSharedWebSocket } from './websocket-manager.js';

/**
 * Inicjalizuje embedded chat dla podanego elementu DOM.
 * @param {HTMLElement} container  - div.embedded-chat z data-room-id i data-csrf
 */
async function initEmbeddedChat(container) {
    const roomId = parseInt(container.dataset.roomId, 10);
    if (!roomId) return;

    const EC_MAX = window.SITE_SETTINGS?.messageMaxLength ?? 500;

    // ── 1. Zbuduj HTML widgetu ────────────────────────────────────────────────
    container.innerHTML = `
        <div class="ec-wrapper">
            <div class="ec-messages messages" id="ec-messages-${roomId}">
                <div class="ec-loading">Ładowanie…</div>
            </div>
            <div class="ec-input-area">
                <div class="reply-preview" id="ec-reply-preview-${roomId}" style="display:none">
                    <span class="reply-preview-label">↩ </span>
                    <span class="reply-preview-text" id="ec-reply-preview-text-${roomId}"></span>
                    <button class="reply-preview-close ec-reply-cancel" type="button" title="Anuluj odpowiedź">✕</button>
                </div>
                <div class="image-preview-container ec-image-preview-container" id="ec-image-preview-${roomId}" style="display:none">
                    <div class="preview-images ec-preview-images" id="ec-preview-images-${roomId}"></div>
                    <div class="delete-images-preview ec-delete-images-preview" id="ec-delete-images-${roomId}">
                        <i class="fas fa fa-times"></i>
                    </div>
                </div>
                <div class="compose-box ec-form-row" id="ec-form-row-${roomId}">
                    <div id="ec-input-${roomId}" class="message-input-rich" role="textbox"
                         contenteditable="true" aria-multiline="true"
                         data-placeholder="${_('Reply to the appropriate message...')}"
                         data-hint="${_('Enter send · Shift/Ctrl+Enter new line · Ctrl+B bold · Ctrl+I italic')}"></div>
                    <div class="compose-bar">
                        <div class="compose-bar-left">
                            <input type="file" id="ec-file-input-${roomId}" class="file-input ec-file-input" multiple="multiple" style="display:none;"/>
                            <label class="fmt-btn" for="ec-file-input-${roomId}" title="${_('Attach image')}">
                                <i class="fas fa-image"></i>
                            </label>
                            <div class="compose-separator"></div>
                            <div class="fmt-toolbar">
                                <button class="fmt-btn" data-cmd="bold"      type="button" title="Ctrl+B"><b>B</b></button>
                                <button class="fmt-btn" data-cmd="italic"    type="button" title="Ctrl+I"><i>I</i></button>
                                <button class="fmt-btn" data-cmd="underline" type="button" title="Ctrl+U"><u>U</u></button>
                            </div>
                            <div class="compose-separator"></div>
                            <button class="fmt-btn anonymous-toggle ec-anonymous-toggle" id="ec-anonymous-${roomId}" type="button" title="${_('Anonymous')}">
                                <i class="fas fa-user-secret"></i>
                            </button>
                        </div>
                        <div class="compose-bar-right">
                            <div class="msg-counter" id="ec-counter-${roomId}">
                                <span id="ec-counter-val-${roomId}">${EC_MAX}</span> / ${EC_MAX}
                            </div>
                            <button class="send-message btn btn-primary compose-send ec-send-btn" id="ec-send-${roomId}" type="button">
                                <i class="fas fa-paper-plane"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    const messagesEl = container.querySelector(`#ec-messages-${roomId}`);
    const inputEl = container.querySelector(`#ec-input-${roomId}`);
    const sendBtn = container.querySelector(`#ec-send-${roomId}`);
    const counterEl = container.querySelector(`#ec-counter-${roomId}`);
    const counterVal = container.querySelector(`#ec-counter-val-${roomId}`);
    const replyPreview = container.querySelector(`#ec-reply-preview-${roomId}`);
    const replyPreviewText = container.querySelector(`#ec-reply-preview-text-${roomId}`);
    const fileInput = container.querySelector(`#ec-file-input-${roomId}`);
    const previewContainer = container.querySelector(`#ec-image-preview-${roomId}`);
    const previewImagesDiv = container.querySelector(`#ec-preview-images-${roomId}`);
    const deleteImagesBtn = container.querySelector(`#ec-delete-images-${roomId}`);

    let currentReplyId = null;
    let lastDateBanner = null;
    let isAnonymous = false;
    let selectedFiles = [];

    // ── 2. Local helpers ─────────────────────────────────────────────────────

    function appendMessage(msg) {
        messagesEl.querySelector('.ec-empty, .ec-loading')?.remove();
        const dateStr = formatDate(msg.timestamp);
        if (dateStr !== lastDateBanner) {
            lastDateBanner = dateStr;
            messagesEl.insertAdjacentHTML('beforeend', `<div class="date-banner">${dateStr}</div>`);
        }

        const html = Message({
            room_id: roomId,
            user_id: msg.user_id ?? null,
            avatar_url: msg.avatar_url ?? null,
            message_id: msg.message_id,
            username: msg.username,
            message: formatMessage(msg.message),
            raw_message: msg.message,
            upvotes: msg.upvotes ?? 0,
            downvotes: msg.downvotes ?? 0,
            vote: msg.your_vote ?? null,
            own: msg.own ?? false,
            edited: msg.edited ?? false,
            attachments: msg.attachments ?? {},
            original_ts: msg.timestamp,
            latest_ts: formatTime(msg.latest_timestamp ?? msg.timestamp),
            type: "public",
            reply_to: msg.reply_to ?? null,
            reactions: msg.reactions ?? { bulb: 0, question: 0 },
            your_reactions: msg.your_reactions ?? [],
            read_by: msg.read_by ?? [],
        });
        messagesEl.insertAdjacentHTML('beforeend', html);
        if (msg.your_vote) {
            const msgDiv = messagesEl.querySelector(`.message[data-message-id="${msg.message_id}"]`);
            msgDiv?.querySelector(`.msg-vote[data-event-name="${msg.your_vote}"]`)?.classList.add('active');
        }
        if (msg.own) unlockSendBtn();
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function updateMessage({ message_id, message, latest_timestamp }) {
        const msgDiv = messagesEl.querySelector(`.message[data-message-id="${message_id}"]`);
        if (!msgDiv) return;
        const textEl = msgDiv.querySelector('.msg-text');
        const timeEl = msgDiv.querySelector('.message-timestamp');
        if (textEl) {
            // data-raw musi nadążać za innerHTML — następna edycja czyta dataset.raw jako "oryginalny tekst do edytowania".
            textEl.dataset.raw = message;
            textEl.innerHTML = formatMessage(message);
        }
        if (timeEl) timeEl.textContent = formatTime(latest_timestamp);
    }

    let ecSendLockTimeout = null;

    function lockSendBtn() {
        sendBtn.disabled = true;
        ecSendLockTimeout = setTimeout(() => { sendBtn.disabled = false; }, 5000);
    }

    function unlockSendBtn() {
        sendBtn.disabled = false;
        clearTimeout(ecSendLockTimeout);
    }

    function sendMessage() {
        const html = getInputHtml(inputEl);
        const text = (inputEl.textContent || '').trim();
        if (!text && selectedFiles.length === 0) return;
        if (!joined) return;
        if (text.length > EC_MAX) return;

        lockSendBtn();

        // Upload files if any selected
        if (selectedFiles.length > 0) {
            uploadFiles(selectedFiles).then((uploadResp) => {
                ws.sendJson({
                    command: 'send',
                    room_id: roomId,
                    message: html,
                    is_anonymous: isAnonymous,
                    attachments: { images: uploadResp.filenames || [] },
                    ...(currentReplyId ? { reply_to_id: currentReplyId } : {}),
                });
                inputEl.innerHTML = '';
                currentReplyId = clearReplyTarget(replyPreview);
                selectedFiles = [];
                fileInput.value = '';
                if (previewContainer) previewContainer.style.display = 'none';
                if (previewImagesDiv) previewImagesDiv.innerHTML = '';
                updateCounter(inputEl, counterEl, counterVal, sendBtn, EC_MAX);
            }).catch((err) => {
                console.error('Upload error:', err);
                unlockSendBtn();
            });
        } else {
            ws.sendJson({
                command: 'send',
                room_id: roomId,
                message: html,
                is_anonymous: isAnonymous,
                attachments: {},
                ...(currentReplyId ? { reply_to_id: currentReplyId } : {}),
            });
            inputEl.innerHTML = '';
            currentReplyId = clearReplyTarget(replyPreview);
            updateCounter(inputEl, counterEl, counterVal, sendBtn, EC_MAX);
        }
    }

    // ── 3. WebSocket ──────────────────────────────────────────────────────────
    const ws = getSharedWebSocket();
    let joined = false;
    let pendingMessages = [];
    let joinDone = false;

    function joinRoom() {
        if (joined) return;
        ws.sendJsonAsync({ command: 'join', room_id: roomId })
            .then(() => {
                joined = true;
                setTimeout(() => {
                    joinDone = true;
                    messagesEl.innerHTML = '';
                    lastDateBanner = null;
                    for (const msg of pendingMessages) appendMessage(msg);
                    pendingMessages = [];
                    if (messagesEl.children.length === 0) {
                        messagesEl.innerHTML = '<div class="ec-empty empty-chat-message">Brak wiadomości. Napisz pierwszy!</div>';
                    }
                }, 0);
            })
            .catch(err => {
                messagesEl.innerHTML = '<div class="ec-loading">Brak dostępu do tego czatu.</div>';
                container.querySelector('.ec-input-area').style.display = 'none';
                console.error('embedded chat join error:', err);
            });
    }

    function onMessage(data) {
        if (data.messages) {
            for (const msg of data.messages) {
                if (msg.room_id && msg.room_id !== roomId) continue;
                if (!joinDone) pendingMessages.push(msg);
                else appendMessage(msg);
            }
        }
        if (data.edit_message) {
            updateMessage(data.edit_message);
        }
        if (data.update_reactions) {
            const ev = data.update_reactions;
            const msgDiv = messagesEl.querySelector(`.message[data-message-id="${ev.message_id}"]`);
            if (!msgDiv) return;
            for (const [key, count] of Object.entries(ev.counts || {})) {
                const btn = msgDiv.querySelector(`.reaction-btn[data-reaction="${key}"]`);
                if (!btn) continue;
                const countEl = btn.querySelector('.reaction-count');
                if (count > 0) {
                    if (countEl) countEl.textContent = count;
                    else btn.insertAdjacentHTML('beforeend', `<span class="reaction-count">${count}</span>`);
                } else if (countEl) countEl.remove();
            }
            if (ev.your_reaction != null) {
                const btn = msgDiv.querySelector(`.reaction-btn[data-reaction="${ev.your_reaction}"]`);
                if (btn) btn.classList.toggle('reaction-btn--active', ev.added ?? false);
            }
        }
        if (data.update_votes) {
            const ev = data.update_votes;
            const msgDiv = messagesEl.querySelector(`.message[data-message-id="${ev.message_id}"]`);
            if (!msgDiv) return;
            const upEl = msgDiv.querySelector('.msg-upvotes');
            const dnEl = msgDiv.querySelector('.msg-downvotes');
            if (upEl) upEl.textContent = ev.upvotes;
            if (dnEl) dnEl.textContent = ev.downvotes;
            if (ev.your_vote) {
                msgDiv.querySelectorAll('.msg-vote').forEach(b => b.classList.remove('active'));
                if (ev.add) msgDiv.querySelector(`.msg-vote[data-event-name="${ev.your_vote}"]`)?.classList.add('active');
            }
        }
    }

    ws.addMessageHandler(onMessage);

    if (ws.socket.readyState === WebSocket.OPEN) {
        joinRoom();
    } else {
        ws.socket.addEventListener('open', function onOpen() {
            ws.socket.removeEventListener('open', onOpen);
            joinRoom();
        });
    }

    // ── 4. Eventy UI ──────────────────────────────────────────────────────────

    // File input handler
    fileInput?.addEventListener('change', (e) => {
        const files = e.target.files;
        if (!files || files.length === 0) return;

        selectedFiles = Array.from(files);
        if (previewContainer) previewContainer.style.display = '';
        if (previewImagesDiv) previewImagesDiv.innerHTML = '';

        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            const fr = new FileReader();
            const previewId = `ec-preview-${i}-${Date.now()}`;

            if (previewImagesDiv) {
                previewImagesDiv.insertAdjacentHTML('beforeend', `
                    <div class="image-preview-wrapper" style="position: relative; display: inline-block;">
                        <img class="image-preview new-attachment" id="${previewId}" style="max-width: 100px; max-height: 100px; margin: 5px;">
                        <button class="btn btn-sm btn-danger ec-remove-preview" data-preview-id="${previewId}" type="button" style="position: absolute; top: 2px; right: 2px; padding: 0 4px; font-size: 12px;">×</button>
                    </div>
                `);
            }

            fr.onload = (event) => {
                const img = document.getElementById(previewId);
                if (img) img.src = event.target.result;
            };
            fr.readAsDataURL(file);
        }
    });

    // Delete images preview
    deleteImagesBtn?.addEventListener('click', () => {
        selectedFiles = [];
        fileInput.value = '';
        if (previewContainer) previewContainer.style.display = 'none';
        if (previewImagesDiv) previewImagesDiv.innerHTML = '';
    });

    // Remove single preview
    container.addEventListener('click', (e) => {
        const removeBtn = e.target.closest('.ec-remove-preview');
        if (removeBtn) {
            const previewId = removeBtn.dataset.previewId;
            removeBtn.closest('.image-preview-wrapper')?.remove();
            // Update selectedFiles by reading from input again
            if (previewImagesDiv && previewImagesDiv.children.length === 0) {
                selectedFiles = [];
                fileInput.value = '';
                if (previewContainer) previewContainer.style.display = 'none';
            }
        }
    });

    // Toggle anonymous
    const anonBtn = container.querySelector(`#ec-anonymous-${roomId}`);
    if (anonBtn) {
        anonBtn.addEventListener('click', () => {
            isAnonymous = !isAnonymous;
            anonBtn.classList.toggle('active', isAnonymous);
        });
    }

    inputEl.addEventListener('input', () => updateCounter(inputEl, counterEl, counterVal, sendBtn, EC_MAX));

    // insertPlainTextAtCaret turns \n into explicit <br> nodes (not browser-wrapped
    // <div> blocks) and fires 'input', so the counter listener handles updates.
    inputEl.addEventListener('paste', (e) => {
        e.preventDefault();
        const pasted = (e.clipboardData || window.clipboardData).getData('text');
        insertPlainTextAtCaret(inputEl, pasted, EC_MAX);
    });

    const { updateToolbarState } = initFormattingToolbar(container, inputEl);

    inputEl.addEventListener('keydown', (e) => {
        const mod = e.ctrlKey || e.metaKey;
        if (mod && e.key === 'b') { e.preventDefault(); document.execCommand('bold'); updateToolbarState(); return; }
        if (mod && e.key === 'i') { e.preventDefault(); document.execCommand('italic'); updateToolbarState(); return; }
        if (mod && e.key === 'u') { e.preventDefault(); document.execCommand('underline'); updateToolbarState(); return; }
        // Enter = wyślij, Shift/Ctrl+Enter = nowa linia
        if (handleEnterKey(e, submitInput)) return;
    });

    // Anuluj odpowiedź
    container.querySelector('.ec-reply-cancel')?.addEventListener('click', () => {
        currentReplyId = clearReplyTarget(replyPreview);
    });

    // ── Shared handlers from chat-core.js ────────────────────────────────────
    const voteHandler = createVoteHandler((eventName, messageId, isAdd) => {
        // Toggle active state on button
        const btn = messagesEl.querySelector(`.msg-vote[data-event-name="${eventName}"][data-message-id="${messageId}"]`);
        if (btn) btn.classList.toggle('active', isAdd);
        if (!joined) return;
        ws.sendJson({
            command: isAdd ? 'message-add-vote' : 'message-remove-vote',
            vote: eventName,
            message_id: messageId,
        });
    });

    const reactionHandler = createReactionHandler((reaction, messageId) => {
        if (!joined) return;
        ws.sendJson({ command: 'message-react', reaction, message_id: messageId });
    });

    function startEdit(messageId, inputElRef) {
        const msgDiv = messagesEl.querySelector(`.message[data-message-id="${messageId}"]`);
        const msgText = msgDiv?.querySelector('.msg-text')?.innerHTML ?? '';
        inputElRef.dataset.editMessage = messageId;
        inputElRef.innerHTML = msgText;
        inputElRef.style.borderColor = 'var(--color-warning)';
        inputElRef.focus();
        updateCounter(inputElRef, counterEl, counterVal, sendBtn, EC_MAX);
    }

    const editHandler = createEditHandler(startEdit, inputEl);

    const replyHandler = createReplyHandler(
        (msgId, username, snippet, preview, previewText) => {
            currentReplyId = setReplyTarget(msgId, username, snippet, preview, previewText);
        },
        replyPreview,
        replyPreviewText,
        inputEl
    );

    const quoteJumpHandler = createQuoteJumpHandler(messagesEl);

    // Attach shared handlers
    messagesEl.addEventListener('click', voteHandler);
    messagesEl.addEventListener('click', reactionHandler);
    messagesEl.addEventListener('click', replyHandler);
    messagesEl.addEventListener('click', editHandler);
    messagesEl.addEventListener('click', quoteJumpHandler);
    messagesEl.addEventListener('click', createImageClickHandler());

    function submitInput() {
        if (inputEl.dataset.editMessage) {
            ws.sendJson({ command: 'edit-message', message_id: parseInt(inputEl.dataset.editMessage), new_message: getInputHtml(inputEl) });
            delete inputEl.dataset.editMessage;
            inputEl.innerHTML = '';
            inputEl.style.borderColor = '';
            updateCounter(inputEl, counterEl, counterVal, sendBtn, EC_MAX);
        } else {
            sendMessage();
        }
    }

    sendBtn.addEventListener('click', submitInput);

    inputEl.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && inputEl.dataset.editMessage) {
            delete inputEl.dataset.editMessage;
            inputEl.innerHTML = '';
            inputEl.style.borderColor = '';
            updateCounter(inputEl, counterEl, counterVal, sendBtn, EC_MAX);
        }
    });

    // ── 5. Cleanup ────────────────────────────────────────────────────────────
    window.addEventListener('beforeunload', () => {
        ws.removeMessageHandler(onMessage);
        if (joined) ws.sendJson({ command: 'leave', room_id: roomId });
    });
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    initGlobalPasteImageHandler();
    for (const el of document.querySelectorAll('.embedded-chat[data-room-id]')) {
        initEmbeddedChat(el);
    }
});