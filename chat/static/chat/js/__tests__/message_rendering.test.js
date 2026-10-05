const fs = require('fs');
const path = require('path');

const source = fs.readFileSync(path.join(__dirname, '..', 'chat.js'), 'utf8');
const helperSource = source.match(/function ownMessagePresence\([\s\S]*?\n}\n/)[0];
const ownMessagePresence = new Function(`${helperSource}; return ownMessagePresence;`)();
const avatarHelperSource = source.match(/function ownMessageAvatar\([\s\S]*?\n}\n/)[0];
const ownMessageAvatar = new Function(`${avatarHelperSource}; return ownMessageAvatar;`)();
const realtimeHelperSource = source.match(/function isRealtimeMessage\([\s\S]*?\n}\n/)[0];
const isRealtimeMessage = new Function(`${realtimeHelperSource}; return isRealtimeMessage;`)();

const coreSource = fs.readFileSync(path.join(__dirname, '..', 'chat-core.js'), 'utf8')
    .replace(/^import .*?;\s*$/gm, '')
    .replace(/export\s*\{[^}]*\}\s*from\s*['"][^'"]+['"];?/g, '')
    .replace(/export\s+(default\s+)?/g, '');
const initMentionSuggestion = new Function(`${coreSource}; return initMentionSuggestion;`)();

describe('single mention suggestion', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
        jest.useFakeTimers();
        global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({ user: { username: 'anna', name: 'Anna Nowak' } }) });
    });

    afterEach(() => {
        jest.useRealTimers();
        delete global.fetch;
    });

    function editAtEnd(html, room = () => 4) {
        const input = document.createElement('div');
        input.setAttribute('contenteditable', 'true');
        input.innerHTML = html;
        document.body.append(input);
        initMentionSuggestion(input, room);
        const node = input.querySelector('b')?.firstChild || input.firstChild;
        const range = document.createRange();
        range.setStart(node, node.textContent.length);
        range.collapse(true);
        window.getSelection().removeAllRanges();
        window.getSelection().addRange(range);
        input.focus();
        input.dispatchEvent(new InputEvent('input', { bubbles: true }));
        return input;
    }

    async function resolveSuggestion() {
        jest.runOnlyPendingTimers();
        for (let i = 0; i < 12; i++) await Promise.resolve();
    }

    function expectCaretAfterMention(input) {
        const selection = window.getSelection();
        expect(document.activeElement).toBe(input);
        expect(selection.isCollapsed).toBe(true);
        expect(selection.anchorNode.nodeType).toBe(Node.TEXT_NODE);
        expect(selection.anchorNode.textContent).toBe('@anna\u00a0');
        expect(selection.anchorOffset).toBe('@anna\u00a0'.length);
    }

    test('inserts username at caret, preserving formatted text and dispatching input', async () => {
        const input = editAtEnd('<b>Cześć @Ann</b>');
        const onInput = jest.fn();
        input.addEventListener('input', onInput);
        await resolveSuggestion();
        const button = input.nextElementSibling;
        expect(global.fetch).toHaveBeenCalledWith('/chat/api/room/4/mention/?q=Ann');
        expect(button.textContent).toBe('Anna Nowak (@anna)');
        expect(button.classList.contains('tw-d-none')).toBe(false);
        const key = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true });
        input.dispatchEvent(key);
        expect(key.defaultPrevented).toBe(true);
        expect(input.textContent).toBe('Cześć @anna\u00a0');
        expect(input.querySelector('b')).not.toBeNull();
        expectCaretAfterMention(input);
        expect(onInput).toHaveBeenCalledTimes(1);
    });

    test('click inserts only when the current query still matches', async () => {
        const input = editAtEnd('Hej @Ann');
        await resolveSuggestion();
        const button = input.nextElementSibling;
        button.click();
        expect(input.textContent).toBe('Hej @anna\u00a0');
        expectCaretAfterMention(input);
        expect(button.classList.contains('tw-d-none')).toBe(true);
    });

    test('keeps a visible separator when text is typed after the mention', async () => {
        const input = editAtEnd('Hej @Ann');
        await resolveSuggestion();
        input.nextElementSibling.click();
        const selection = window.getSelection();
        selection.anchorNode.insertData(selection.anchorOffset, 'tekst');
        expect(input.textContent).toBe('Hej @anna\u00a0tekst');
    });

    test('does not show a suggestion without a unique result', async () => {
        global.fetch.mockResolvedValue({ ok: true, json: async () => ({ user: null }) });
        const input = editAtEnd('Hej @Ann');
        await resolveSuggestion();
        expect(input.nextElementSibling.classList.contains('tw-d-none')).toBe(true);
    });

    test('does not suggest for an email address or a stale room response', async () => {
        editAtEnd('mail@example.com');
        await resolveSuggestion();
        expect(global.fetch).not.toHaveBeenCalled();
        let roomId = 4;
        const input = editAtEnd('Cześć @Ann', () => roomId);
        roomId = 5;
        await resolveSuggestion();
        expect(input.nextElementSibling.classList.contains('tw-d-none')).toBe(true);
    });
});

test('marks a non-anonymous optimistic message as online with a parseable timestamp', () => {
    const presence = ownMessagePresence(false, 0);
    expect(presence.status).toBe('green');
    expect(presence.source).toBe('app');
    expect(Date.parse(presence.timestamp)).toBe(0);
});

test('keeps anonymous optimistic messages red', () => {
    expect(ownMessagePresence(true, 0)).toEqual({ status: 'red', source: '', timestamp: null });
});

test('uses the current user avatar for non-anonymous optimistic messages', () => {
    expect(ownMessageAvatar(false, { dataset: { avatar: '/media/avatar.png' } })).toBe('/media/avatar.png');
});

test('does not expose the current user avatar for anonymous messages', () => {
    expect(ownMessageAvatar(true, { dataset: { avatar: '/media/avatar.png' } })).toBeNull();
});

test('treats the sender echo with temp_id as a realtime message', () => {
    expect(isRealtimeMessage([{ new: false, temp_id: 'tmp-1' }])).toBe(true);
});

test('does not treat a one-message history response as realtime', () => {
    expect(isRealtimeMessage([{ new: false, temp_id: null }])).toBe(false);
});

test('treats a new message without an optimistic id as realtime', () => {
    expect(isRealtimeMessage([{ new: true, temp_id: null }])).toBe(true);
});

test('does not treat a batch as realtime', () => {
    expect(isRealtimeMessage([{ new: true }, { new: true }])).toBe(false);
});
