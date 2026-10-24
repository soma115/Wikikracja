/**
 * @file chat-embedded.js
 * Embedded chat widget — reużywa Message template i CSS z głównego czatu.
 *
 * Użycie w template:
 *   <div class="tw-embedded-chat" data-room-id="42" data-csrf="{{ csrf_token }}"></div>
 *   <script type="module" src="{% static 'chat/js/chat-embedded.js' %}"></script>
 */

import { clearReplyTarget, createEditHandler, createImageClickHandler, createQuoteJumpHandler, createReactionHandler, createReplyHandler, createVoteHandler, formatMessage, getInputHtml, handleEnterKey, initFormattingToolbar, initGlobalPasteImageHandler, initMentionSuggestion, insertPlainTextAtCaret, setReplyTarget, updateCounter, uploadFiles, voteButtonTitle } from './chat-core.js';
import { Message } from './templates.js';
import { _, dateBannerHtml, formatDate, formatTime } from './utility.js';
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
        <div class="tw-ec-wrapper">
            <div class="tw-ec-messages tw-chat-messages" id="ec-messages-${roomId}">
                <div class="tw-ec-loading">Ładowanie…</div>
            </div>
            <div class="tw-ec-input-area">
                <div class="tw-reply-preview tw-d-none" id="ec-reply-preview-${roomId}">
                    <span class="tw-reply-preview-label">↩ </span>
                    <span class="tw-reply-preview-text" id="ec-reply-preview-text-${roomId}"></span>
                    <button class="tw-reply-preview-close tw-ec-reply-cancel" type="button" title="Anuluj odpowiedź">✕</button>
                </div>
                <div class="tw-image-preview-container tw-ec-image-preview-container tw-d-none" id="ec-image-preview-${roomId}">
                    <div class="tw-preview-images tw-ec-preview-images" id="ec-preview-images-${roomId}"></div>
                    <div class="tw-delete-images-preview tw-ec-delete-images-preview" id="ec-delete-images-${roomId}">
                        <i class="fas fa-times"></i>
                    </div>
                </div>
                <div class="tw-compose-box tw-ec-form-row" id="ec-form-row-${roomId}">
                    <div id="ec-input-${roomId}" class="tw-message-input-rich" role="textbox"
                         contenteditable="true" aria-multiline="true"
                         data-placeholder="${_('Reply to the appropriate message...')}"
                         data-hint="${_('Enter send · Shift/Ctrl+Enter new line · Ctrl+B bold · Ctrl+I italic')}"></div>
                    <div class="tw-compose-bar">
                        <div class="tw-compose-bar-left">
                            <input type="file" id="ec-file-input-${roomId}" class="tw-file-input tw-ec-file-input tw-d-none" multiple="multiple"/>
                            <label class="tw-fmt-btn" for="ec-file-input-${roomId}" title="${_('Attach image')}">
                                <i class="fas fa-image"></i>
                            </label>
                            <div class="tw-compose-separator"></div>
                            <div class="tw-fmt-toolbar">
                                <button class="tw-fmt-btn" data-cmd="bold"      type="button" title="Ctrl+B"><b>B</b></button>
                                <button class="tw-fmt-btn" data-cmd="italic"    type="button" title="Ctrl+I"><i>I</i></button>
                                <button class="tw-fmt-btn" data-cmd="underline" type="button" title="Ctrl+U"><u>U</u></button>
                            </div>
                            <div class="tw-compose-separator"></div>
                            <button class="tw-fmt-btn tw-anonymous-toggle tw-ec-anonymous-toggle" id="ec-anonymous-${roomId}" type="button" title="${_('Anonymous')}">
                                <i class="fas fa-user-secret"></i>
                            </button>
                        </div>
                        <div class="tw-compose-bar-right">
                            <div class="tw-msg-counter" id="ec-counter-${roomId}">
                                <span id="ec-counter-val-${roomId}">${EC_MAX}</span> / ${EC_MAX}
                            </div>
                            <button class="tw-send-message tw-btn tw-btn-primary tw-compose-send tw-ec-send-btn" id="ec-send-${roomId}" type="button">
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
    let removedAttachments = [];
    const canPost = container.dataset.canPost !== 'false';

    if (!canPost) {
        const inputArea = container.querySelector('.tw-ec-input-area');
        if (inputArea) {
            const notice = container.dataset.sourceApp === 'tasks' ? _("Only approved helpers can write here.") : _("You cannot write in this room.");
            inputArea.innerHTML = `<div class="tw-ec-readonly-notice"><i class="fas fa-lock"></i> ${notice}</div>`;
        }
    }

    // ── 2. Local helpers ─────────────────────────────────────────────────────

    function appendMessage(msg) {
        messagesEl.querySelector('.tw-ec-empty, .tw-ec-loading')?.remove();
        const dateStr = formatDate(msg.timestamp);
        if (dateStr !== lastDateBanner) {
            lastDateBanner = dateStr;
            messagesEl.insertAdjacentHTML('beforeend', dateBannerHtml(dateStr));
        }

        const html = Message({
            room_id: roomId,
            user_id: msg.user_id ?? null,
            avatar_url: msg.avatar_url ?? null,
            citizen_color_class: msg.citizen_color_class ?? '',
            message_id: msg.message_id,
            username: msg.username,
            display_name: msg.display_name ?? null,
            initials: msg.initials ?? null,
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
            upvoters: msg.upvoters ?? null,
            downvoters: msg.downvoters ?? null,
            presence_status: msg.presence_status ?? 'red',
            presence_source: msg.presence_source ?? '',
            presence_timestamp: msg.presence_timestamp ?? null,
        });
        messagesEl.insertAdjacentHTML('beforeend', html);
        if (msg.your_vote) {
            const msgDiv = messagesEl.querySelector(`.tw-chat-message[data-message-id="${msg.message_id}"]`);
            msgDiv?.querySelector(`.tw-msg-vote[data-event-name="${msg.your_vote}"]`)?.classList.add('tw-active');
        }
        if (msg.own) unlockSendBtn();
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function updateMessage({ message_id, message, text, latest_timestamp, timestamp, attachments }) {
        const msgDiv = messagesEl.querySelector(`.tw-chat-message[data-message-id="${message_id}"]`);
        if (!msgDiv) return;
        const textEl = msgDiv.querySelector('.tw-msg-text');
        const timeEl = msgDiv.querySelector('.tw-message-timestamp');
        const updatedText = message ?? text;
        if (textEl && typeof updatedText === 'string') {
            textEl.dataset.raw = updatedText;
            textEl.innerHTML = formatMessage(updatedText);
        }
        const messageTime = latest_timestamp ?? timestamp;
        if (timeEl && messageTime !== null && messageTime !== undefined && Number.isFinite(Number(messageTime))) {
            timeEl.textContent = formatTime(messageTime);
        }
        if (attachments !== undefined) {
            const attachmentContainer = msgDiv.querySelector('.tw-attachment-image-container');
            if (attachmentContainer) {
                attachmentContainer.innerHTML = '';
                for (const filename of attachments?.images ?? []) {
                    const image = document.createElement('img');
                    image.className = 'tw-attached-image';
                    image.loading = 'lazy';
                    image.src = `/media/uploads/${encodeURIComponent(filename).replace(/'/g, '%27')}`;
                    attachmentContainer.appendChild(image);
                }
            }
        }
        if (inputEl.dataset.editMessage === String(message_id)) {
            clearEditing();
        }
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

    function clearEditing() {
        delete inputEl.dataset.editMessage;
        delete inputEl.dataset.originalMessageText;
        inputEl.innerHTML = '';
        inputEl.classList.remove('tw-editing');
        selectedFiles = [];
        removedAttachments = [];
        fileInput.value = '';
        previewImagesDiv.innerHTML = '';
        previewContainer.classList.add('tw-d-none');
        updateCounter(inputEl, counterEl, counterVal, sendBtn, EC_MAX);
        unlockSendBtn();
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
                if (previewContainer) previewContainer.classList.add('tw-d-none');
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

    let joinInFlight = false;

    function joinRoom() {
        if (joined || joinInFlight) return;
        joinInFlight = true;
        ws.sendJsonAsync({ command: 'join', room_id: roomId })
            .then(() => {
                joinInFlight = false;
                joined = true;
                setTimeout(() => {
                    joinDone = true;
                    messagesEl.innerHTML = '';
                    lastDateBanner = null;
                    for (const msg of pendingMessages) appendMessage(msg);
                    pendingMessages = [];
                    if (messagesEl.children.length === 0) {
                        messagesEl.innerHTML = '<div class="tw-ec-empty tw-empty-chat-message">' + window.escapeHtml(_('No messages. Write the first one!')) + '</div>';
                    }
                }, 0);
            })
            .catch(err => {
                joinInFlight = false;
                if (err === 'REQUEST_TIMEOUT') {
                    // Błąd przejściowy — spróbuj ponownie, nie pokazuj "brak dostępu".
                    console.warn('embedded chat join timeout, retrying:', err);
                    setTimeout(() => { if (!joined && ws.isOpen()) joinRoom(); }, 5000);
                    return;
                }
                messagesEl.innerHTML = '<div class="tw-ec-loading">' + window.escapeHtml(_('No access to this chat.')) + '</div>';
                container.querySelector('.tw-ec-input-area')?.classList.add('tw-d-none');
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
            const msgDiv = messagesEl.querySelector(`.tw-chat-message[data-message-id="${ev.message_id}"]`);
            if (!msgDiv) return;
            for (const [key, count] of Object.entries(ev.counts || {})) {
                const btn = msgDiv.querySelector(`.tw-reaction-btn[data-reaction="${key}"]`);
                if (!btn) continue;
                const countEl = btn.querySelector('.tw-reaction-count');
                if (count > 0) {
                    if (countEl) countEl.textContent = count;
                    else btn.insertAdjacentHTML('beforeend', `<span class="tw-reaction-count">${count}</span>`);
                } else if (countEl) countEl.remove();
            }
            if (ev.your_reaction != null) {
                const btn = msgDiv.querySelector(`.tw-reaction-btn[data-reaction="${ev.your_reaction}"]`);
                if (btn) btn.classList.toggle('tw-reaction-btn--active', ev.added ?? false);
            }
        }
        if (data.update_votes) {
            const ev = data.update_votes;
            const msgDiv = messagesEl.querySelector(`.tw-chat-message[data-message-id="${ev.message_id}"]`);
            if (!msgDiv) return;
            const upEl = msgDiv.querySelector('.tw-msg-upvotes');
            const dnEl = msgDiv.querySelector('.tw-msg-downvotes');
            if (upEl) upEl.textContent = ev.upvotes;
            if (dnEl) dnEl.textContent = ev.downvotes;
            if (ev.your_vote) {
                msgDiv.querySelectorAll('.tw-msg-vote').forEach(b => b.classList.remove('tw-active'));
                if (ev.add) msgDiv.querySelector(`.tw-msg-vote[data-event-name="${ev.your_vote}"]`)?.classList.add('tw-active');
            }
            // Pokoje zadań: serwer dosyła nicki głosujących — odśwież tooltipsy łapek.
            if (ev.upvoters !== undefined) {
                const upBtn = msgDiv.querySelector('.tw-msg-vote[data-event-name="upvote"]');
                const dnBtn = msgDiv.querySelector('.tw-msg-vote[data-event-name="downvote"]');
                if (upBtn) upBtn.title = voteButtonTitle(_('Upvote'), ev.upvoters);
                if (dnBtn) dnBtn.title = voteButtonTitle(_('Downvote'), ev.downvoters);
            }
        }
    }

    const unsubscribeMessages = ws.subscribeMessages(onMessage);

    // Lifecycle przez subskrypcję — obejmuje pierwszy open (także gdy socket
    // już jest otwarty) oraz reconnect: po zerwaniu serwer gubi członkostwo
    // w pokoju, więc resetujemy lokalny stan i dołączamy ponownie.
    const unsubscribeConnection = ws.subscribeConnection({
        onOpen: () => {
            joined = false;
            joinDone = false;
            pendingMessages = [];
            joinRoom();
        },
        onClose: () => {
            joined = false;
            joinDone = false;
        },
    });

    // ── 4. Eventy UI ──────────────────────────────────────────────────────────

    // File input handler
    fileInput?.addEventListener('change', (e) => {
        const files = e.target.files;
        if (!files || files.length === 0) return;

        selectedFiles = Array.from(files);
        if (previewContainer) previewContainer.classList.remove('tw-d-none');
        previewImagesDiv?.querySelectorAll('.tw-new-attachment').forEach(image => {
            image.closest('.tw-image-preview-wrapper')?.remove();
        });

        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            const fr = new FileReader();
            const previewId = `ec-preview-${i}-${Date.now()}`;

            if (previewImagesDiv) {
                previewImagesDiv.insertAdjacentHTML('beforeend', `
                    <div class="tw-image-preview-wrapper tw-ec-image-preview-wrapper">
                        <img class="tw-image-preview tw-new-attachment" id="${previewId}">
                        <button class="tw-btn tw-btn-sm tw-btn-danger tw-ec-remove-preview tw-image-preview-remove" data-preview-id="${previewId}" type="button">×</button>
                    </div>
                `);
                previewImagesDiv.lastElementChild.querySelector('.tw-ec-remove-preview').dataset.fileIndex = i;
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
        previewImagesDiv?.querySelectorAll('.tw-ec-remove-existing').forEach(button => {
            if (!removedAttachments.includes(button.dataset.filename)) {
                removedAttachments.push(button.dataset.filename);
            }
        });
        selectedFiles = [];
        fileInput.value = '';
        if (previewContainer) previewContainer.classList.add('tw-d-none');
        if (previewImagesDiv) previewImagesDiv.innerHTML = '';
    });

    // Remove single preview
    container.addEventListener('click', (e) => {
        const removeBtn = e.target.closest('.tw-ec-remove-preview');
        if (removeBtn) {
            if (removeBtn.classList.contains('tw-ec-remove-existing')) {
                const filename = removeBtn.dataset.filename;
                if (!removedAttachments.includes(filename)) removedAttachments.push(filename);
            } else {
                const removedIndex = Number(removeBtn.dataset.fileIndex);
                if (Number.isInteger(removedIndex)) {
                    const transfer = new DataTransfer();
                    selectedFiles.filter((_, index) => index !== removedIndex)
                        .forEach(file => transfer.items.add(file));
                    fileInput.files = transfer.files;
                    selectedFiles = Array.from(transfer.files);
                }
            }
            removeBtn.closest('.tw-image-preview-wrapper')?.remove();
            previewImagesDiv?.querySelectorAll('.tw-new-attachment').forEach((image, index) => {
                const remainingRemoveButton = image.closest('.tw-image-preview-wrapper')
                    ?.querySelector('.tw-ec-remove-preview');
                if (remainingRemoveButton) remainingRemoveButton.dataset.fileIndex = index;
            });
            if (previewImagesDiv && previewImagesDiv.children.length === 0) {
                selectedFiles = [];
                fileInput.value = '';
                if (previewContainer) previewContainer.classList.add('tw-d-none');
            }
        }
    });

    // Toggle anonymous
    const anonBtn = container.querySelector(`#ec-anonymous-${roomId}`);
    if (anonBtn) {
        anonBtn.addEventListener('click', () => {
            isAnonymous = !isAnonymous;
            anonBtn.classList.toggle('tw-active', isAnonymous);
        });
    }

    initMentionSuggestion(canPost ? inputEl : null, () => roomId);
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
    container.querySelector('.tw-ec-reply-cancel')?.addEventListener('click', () => {
        currentReplyId = clearReplyTarget(replyPreview);
    });

    // ── Shared handlers from chat-core.js ────────────────────────────────────
    const voteHandler = createVoteHandler((eventName, messageId, isAdd) => {
        // Toggle active state on button
        const btn = messagesEl.querySelector(`.tw-msg-vote[data-event-name="${eventName}"][data-message-id="${messageId}"]`);
        if (btn) btn.classList.toggle('tw-active', isAdd);
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
        const msgDiv = messagesEl.querySelector(`.tw-chat-message[data-message-id="${messageId}"]`);
        const textEl = msgDiv?.querySelector('.tw-msg-text');
        const msgText = textEl?.dataset.raw ?? textEl?.innerHTML ?? '';
        selectedFiles = [];
        removedAttachments = [];
        fileInput.value = '';
        previewImagesDiv.innerHTML = '';
        const existingImages = msgDiv?.querySelectorAll('.tw-attached-image') ?? [];
        existingImages.forEach(image => {
            const filename = decodeURIComponent(image.getAttribute('src').split('/').pop());
            const wrapper = document.createElement('div');
            wrapper.className = 'tw-image-preview-wrapper tw-ec-image-preview-wrapper';

            const preview = document.createElement('img');
            preview.className = 'tw-image-preview';
            preview.src = image.src;

            const removeButton = document.createElement('button');
            removeButton.className = 'tw-btn tw-btn-sm tw-btn-danger tw-ec-remove-preview tw-ec-remove-existing tw-image-preview-remove';
            removeButton.type = 'button';
            removeButton.dataset.filename = filename;
            removeButton.textContent = 'x';

            wrapper.append(preview, removeButton);
            previewImagesDiv.appendChild(wrapper);
        });
        previewContainer.classList.toggle('tw-d-none', existingImages.length === 0);
        inputElRef.dataset.editMessage = messageId;
        inputElRef.dataset.originalMessageText = msgText;
        inputElRef.innerHTML = msgText;
        inputElRef.classList.add('tw-editing');
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

    async function submitInput() {
        if (inputEl.dataset.editMessage) {
            if (!joined) return;
            const message = getInputHtml(inputEl);
            const payload = {
                command: 'edit-message',
                message_id: parseInt(inputEl.dataset.editMessage, 10),
            };
            if (message !== inputEl.dataset.originalMessageText) payload.new_message = message;
            if (removedAttachments.length) payload.removed_attachments = [...removedAttachments];

            lockSendBtn();
            try {
                if (selectedFiles.length) {
                    const uploaded = await uploadFiles(selectedFiles);
                    if (uploaded.filenames.length) payload.attachments = { images: uploaded.filenames };
                }
                if (!payload.new_message && !payload.attachments && !payload.removed_attachments) {
                    clearEditing();
                    return;
                }
                ws.sendJson(payload);
            } catch (error) {
                console.error('Upload error:', error);
                window.showToast?.(error.message);
                unlockSendBtn();
            }
        } else {
            sendMessage();
        }
    }

    sendBtn.addEventListener('click', submitInput);

    inputEl.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && inputEl.dataset.editMessage) {
            clearEditing();
        }
    });

    // ── 5. Cleanup ────────────────────────────────────────────────────────────
    window.addEventListener('beforeunload', () => {
        unsubscribeMessages();
        unsubscribeConnection();
        if (joined) ws.sendJson({ command: 'leave', room_id: roomId });
    });
}

// ── Initialization ────────────────────────────────────────────────────────────
window.wkOnReady(() => {
    initGlobalPasteImageHandler();
    for (const el of document.querySelectorAll('.tw-embedded-chat[data-room-id]')) {
        initEmbeddedChat(el);
    }
});