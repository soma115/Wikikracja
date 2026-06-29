/**
 * @file chat-core.js
 * Core chat functionality shared between chat.js and chat-embedded.js.
 * Pure rich-text functions live in /static/common/js/richtext-core.js and are
 * re-exported here so chat callers don't need to change their imports.
 */

export {
    getInputHtml,
    updateCounter,
    formatMessage,
    handleEnterKey,
    getVisibleTextLength,
    initGlobalPasteImageHandler,
    insertPlainTextAtCaret,
} from '../../common/js/richtext-core.js';

export const UPLOAD_MAX_BYTES = 5_000_000;
const IMAGE_MAX_DIMENSION = 1280;
const IMAGE_WEBP_QUALITY = 0.75;

async function compressImage(file) {
    if (!file.type.startsWith('image/') || file.type === 'image/gif') return file;
    try {
        const bitmap = await createImageBitmap(file);
        const { width, height } = bitmap;
        const scale = Math.min(1, IMAGE_MAX_DIMENSION / Math.max(width, height));
        const canvas = document.createElement('canvas');
        canvas.width = Math.round(width * scale);
        canvas.height = Math.round(height * scale);
        canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height);
        bitmap.close();
        return await new Promise((res, rej) =>
            canvas.toBlob(b => b ? res(new File([b], file.name.replace(/\.\w+$/, '.webp'), { type: 'image/webp' })) : rej(new Error('toBlob failed')), 'image/webp', IMAGE_WEBP_QUALITY)
        );
    } catch {
        return file;
    }
}

export async function uploadFiles(files, uploadUrl = '/chat/upload/') {
    if (!files || files.length === 0) {
        return { filenames: [] };
    }

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        if (file.size > UPLOAD_MAX_BYTES) {
            alert('File is too big');
            continue;
        }
        // eslint-disable-next-line no-await-in-loop
        formData.append('images', await compressImage(file));
    }

    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.onreadystatechange = () => {
            if (xhr.readyState === 4 && xhr.status === 200) {
                try {
                    resolve(JSON.parse(xhr.responseText));
                } catch (e) {
                    reject(e);
                }
            }
        };
        xhr.onerror = () => reject(new Error('Upload failed'));
        xhr.open('POST', uploadUrl, true);
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        xhr.send(formData);
    });
}

/**
 * Set reply target with preview
 * @param {number} message_id - Message ID being replied to
 * @param {string} username - Username of the message author
 * @param {string} snippet - Snippet of the message being replied to
 * @param {HTMLElement} previewEl - Reply preview container
 * @param {HTMLElement} previewTextEl - Reply preview text element
 * @returns {number} The message_id (for state management by caller)
 */
export function setReplyTarget(message_id, username, snippet, previewEl, previewTextEl) {
    if (previewEl && previewTextEl) {
        previewTextEl.textContent = `${username}: ${snippet}`;
        previewEl.style.display = '';
    }
    return message_id;
}

/**
 * Clear reply target
 * @param {HTMLElement} previewEl - Reply preview container
 * @returns {null} Returns null (for state management by caller)
 */
export function clearReplyTarget(previewEl) {
    if (previewEl) previewEl.style.display = 'none';
    return null;
}

/**
 * Create a delegated vote handler for message vote buttons
 * @param {Function} sendVote - Callback (eventName, messageId, isAdd) => void
 * @returns {Function} Event handler (e) => void
 */
export function createVoteHandler(sendVote) {
    return function(e) {
        const btn = e.target.closest('.msg-vote');
        if (!btn) return;
        const eventName = btn.dataset.eventName;
        const messageId = btn.dataset.messageId;
        if (!eventName || !messageId) return;
        const isAdd = !btn.classList.contains('active');
        sendVote(eventName, messageId, isAdd);
    };
}

/**
 * Create a delegated reaction handler for message reaction buttons
 * @param {Function} sendReaction - Callback (reaction, messageId) => void
 * @returns {Function} Event handler (e) => void
 */
export function createReactionHandler(sendReaction) {
    return function(e) {
        const btn = e.target.closest('.reaction-btn');
        if (!btn) return;
        const reaction = btn.dataset.reaction;
        const messageId = btn.dataset.messageId;
        if (!reaction || !messageId) return;
        sendReaction(reaction, parseInt(messageId, 10));
    };
}

/**
 * Create a delegated reply handler for reply buttons
 * @param {Function} setReplyTarget - (messageId, username, snippet, previewEl, previewTextEl) => void
 * @param {HTMLElement} replyPreview - Reply preview container
 * @param {HTMLElement} replyPreviewText - Reply preview text element
 * @param {HTMLElement} inputEl - Message input element
 * @returns {Function} Event handler (e) => void
 */
export function createReplyHandler(setReplyTarget, replyPreview, replyPreviewText, inputEl) {
    return function(e) {
        const replyBtn = e.target.closest('.reply-btn');
        if (!replyBtn) return;
        const messageId = replyBtn.dataset.messageId;
        const username = replyBtn.dataset.username;
        const snippet = replyBtn.dataset.snippet;
        if (!messageId) return;
        setReplyTarget(messageId, username, snippet, replyPreview, replyPreviewText);
        if (inputEl) inputEl.focus();
    };
}

/**
 * Create a delegated edit handler for edit buttons
 * @param {Function} startEdit - (messageId, inputEl) => void
 * @param {HTMLElement} inputEl - Message input element
 * @returns {Function} Event handler (e) => void
 */
export function createEditHandler(startEdit, inputEl) {
    return function(e) {
        const editBtn = e.target.closest('.edit-message');
        if (!editBtn) return;
        const messageId = editBtn.dataset.messageId;
        if (!messageId) return;
        startEdit(messageId, inputEl);
    };
}

/**
 * Create a delegated quote jump handler with built-in return button.
 * Handles both jumping to the quoted message and returning to the reply.
 * @param {HTMLElement|Function} containerOrGetter - Messages container or a getter function (for lazy resolution)
 * @returns {Function} Event handler (e) => void
 */
export function createQuoteJumpHandler(containerOrGetter) {
    let _sourceMessageId = null;
    const getContainer = typeof containerOrGetter === 'function'
        ? containerOrGetter
        : () => containerOrGetter;

    function showReturnBtn(targetMsg) {
        document.getElementById('msg-return-btn')?.remove();
        const btn = document.createElement('button');
        btn.id = 'msg-return-btn';
        btn.type = 'button';
        btn.innerHTML = '↙';
        btn.title = 'Wróć do odpowiedzi';
        (targetMsg.querySelector('.message-content') || targetMsg).appendChild(btn);
        requestAnimationFrame(() => btn.classList.add('visible'));
        const container = getContainer();
        if (container) {
            let listenActive = false;
            setTimeout(() => { listenActive = true; }, 800);
            const onScroll = () => {
                if (!listenActive) return;
                if (container.scrollHeight - container.scrollTop - container.clientHeight < 60) {
                    btn.remove();
                    container.removeEventListener('scroll', onScroll);
                }
            };
            container.addEventListener('scroll', onScroll);
            btn._removeScroll = () => container.removeEventListener('scroll', onScroll);
        }
    }

    return function(e) {
        const retBtn = e.target.closest('#msg-return-btn');
        if (retBtn) {
            retBtn._removeScroll?.();
            retBtn.remove();
            if (_sourceMessageId) {
                const src = (getContainer() || document).querySelector(`.message[data-message-id="${_sourceMessageId}"]`);
                src?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                _sourceMessageId = null;
            }
            return;
        }

        const jumpBtn = e.target.closest('.msg-quote-jump') || e.target.closest('.msg-quote');
        if (!jumpBtn) return;
        const targetId = jumpBtn.dataset.targetId || jumpBtn.dataset.replyId
            || jumpBtn.closest('.msg-quote')?.dataset.replyId;
        if (!targetId) return;
        const currentMsg = jumpBtn.closest('.message');
        if (currentMsg) _sourceMessageId = currentMsg.dataset.messageId;
        const container = getContainer();
        const targetMsg = container?.querySelector(`.message[data-message-id="${targetId}"]`)
            || document.querySelector(`.message[data-message-id="${targetId}"]`);
        if (targetMsg) {
            targetMsg.scrollIntoView({ behavior: 'smooth', block: 'center' });
            targetMsg.classList.remove('msg-highlighted');
            void targetMsg.offsetWidth;
            targetMsg.classList.add('msg-highlighted');
            setTimeout(() => targetMsg.classList.remove('msg-highlighted'), 2000);
            showReturnBtn(targetMsg);
        }
    };
}

/**
 * Create delegated handlers for copy room/message link buttons
 * @param {Function} copyRoomLink - (roomId, button) => void
 * @param {Function} copyMessageLink - (roomId, messageId, button) => void
 * @returns {Object} { roomLinkHandler, messageLinkHandler }
 */
export function createCopyLinkHandler(copyRoomLink, copyMessageLink) {
    return {
        roomLinkHandler: function(e) {
            const btn = e.target.closest('.copy-room-url');
            if (!btn) return;
            const roomId = btn.dataset.roomId;
            if (!roomId) return;
            copyRoomLink(roomId, btn);
        },
        messageLinkHandler: function(e) {
            const btn = e.target.closest('.copy-message-url');
            if (!btn) return;
            const roomId = btn.dataset.roomId;
            const messageId = btn.dataset.messageId;
            if (!roomId || !messageId) return;
            copyMessageLink(roomId, messageId, btn);
        }
    };
}

/**
 * Create a delegated history handler for history buttons
 * @param {Function} showHistory - (messageId) => void
 * @returns {Function} Event handler (e) => void
 */
export function createHistoryHandler(showHistory) {
    return function(e) {
        const btn = e.target.closest('.show-history');
        if (!btn) return;
        const messageId = btn.dataset.messageId;
        if (!messageId) return;
        showHistory(messageId);
    };
}

/**
 * Create a file upload handler for file inputs
 * @param {Function} handleFiles - (files, previewContainer, previewImagesDiv) => void
 * @param {HTMLElement} previewContainer - Preview container element
 * @param {HTMLElement} previewImagesDiv - Preview images container
 * @returns {Function} Event handler (e) => void
 */
export function createFileUploadHandler(handleFiles, previewContainer, previewImagesDiv) {
    return function(e) {
        if (!e.target.classList.contains('file-input')) return;
        const files = e.target.files;
        if (!files || files.length === 0) return;
        handleFiles(files, previewContainer, previewImagesDiv);
    };
}

/**
 * Open a fullscreen image viewer lightbox.
 * @param {string[]} srcs - Array of image URLs to display
 * @param {number} [startIndex=0] - Index of the first image to show
 */
export function openBigImage(srcs, startIndex = 0) {
    document.getElementById('image-viewer-overlay')?.remove();

    const overlay = document.createElement('div');
    overlay.id = 'image-viewer-overlay';
    overlay.className = 'image-viewer-overlay';
    overlay.innerHTML = `
        <button class="image-viewer-close" aria-label="Close">&times;</button>
        <button class="image-viewer-nav image-viewer-prev" aria-label="Previous">&#10094;</button>
        <button class="image-viewer-nav image-viewer-next" aria-label="Next">&#10095;</button>
        <div class="image-viewer-container">
            <img class="image-viewer-img" src="" alt="">
        </div>
        <div class="image-viewer-counter"></div>
    `;
    document.body.appendChild(overlay);
    document.body.classList.add('modal-open');

    let currentIndex = startIndex;
    const imgEl = overlay.querySelector('.image-viewer-img');
    const counterEl = overlay.querySelector('.image-viewer-counter');
    const prevBtn = overlay.querySelector('.image-viewer-prev');
    const nextBtn = overlay.querySelector('.image-viewer-next');

    function show(index) {
        currentIndex = (index + srcs.length) % srcs.length;
        imgEl.src = srcs[currentIndex];
        const multi = srcs.length > 1;
        counterEl.textContent = multi ? `${currentIndex + 1} / ${srcs.length}` : '';
        prevBtn.style.display = multi ? 'block' : 'none';
        nextBtn.style.display = multi ? 'block' : 'none';
    }

    function close() {
        document.removeEventListener('keydown', onKey);
        overlay.remove();
        document.body.classList.remove('modal-open');
    }

    function onKey(e) {
        if (e.key === 'Escape') close();
        if (e.key === 'ArrowLeft') show(currentIndex - 1);
        if (e.key === 'ArrowRight') show(currentIndex + 1);
    }

    overlay.querySelector('.image-viewer-close').addEventListener('click', close);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
    prevBtn.addEventListener('click', (e) => { e.stopPropagation(); show(currentIndex - 1); });
    nextBtn.addEventListener('click', (e) => { e.stopPropagation(); show(currentIndex + 1); });
    document.addEventListener('keydown', onKey);

    show(currentIndex);
}

/**
 * Initialize the rich-text formatting toolbar (B / I / U buttons).
 * Uses event delegation so it works for dynamically rendered rooms.
 * Prevents mousedown focus-theft so selection is preserved when clicking buttons.
 *
 * @param {Document|HTMLElement} root - Delegation root (document for main chat, container for embedded)
 * @param {HTMLElement|Function} inputEl - The contenteditable input, or a getter () => element
 * @returns {{ updateToolbarState: Function }}
 */
export function initFormattingToolbar(root, inputEl) {
    const resolveInput = typeof inputEl === 'function' ? inputEl : () => inputEl;

    function updateToolbarState() {
        root.querySelectorAll('.fmt-btn[data-cmd]').forEach(btn => {
            btn.classList.toggle('active', document.queryCommandState(btn.dataset.cmd));
        });
    }

    root.addEventListener('mousedown', (e) => {
        if (e.target.closest('.fmt-btn[data-cmd]')) e.preventDefault();
    });

    root.addEventListener('click', (e) => {
        const btn = e.target.closest('.fmt-btn[data-cmd]');
        if (!btn) return;
        document.execCommand(btn.dataset.cmd);
        updateToolbarState();
    });

    document.addEventListener('selectionchange', () => {
        const el = resolveInput();
        if (el && document.activeElement === el) updateToolbarState();
    });

    return { updateToolbarState };
}

/**
 * Create a delegated click handler that opens the image viewer
 * when user clicks an .attached-image inside .attachment-image-container.
 * @returns {Function} click event handler
 */
export function createImageClickHandler() {
    return function(e) {
        const img = e.target.closest('.attached-image');
        if (!img) return;
        const container = img.closest('.attachment-image-container');
        if (!container) return;
        const images = Array.from(container.querySelectorAll('.attached-image'));
        openBigImage(images.map(i => i.src), images.indexOf(img));
    };
}
