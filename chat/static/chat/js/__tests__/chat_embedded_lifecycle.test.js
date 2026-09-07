/**
 * @jest-environment jsdom
 *
 * Testy lifecycle embedded chatu (plan 9.8 / 13.11):
 *   - wiadomości przychodzące przed końcem joinu są buforowane i renderowane
 *     RAZ po joinie (joinDone gate + pendingMessages),
 *   - reconnect resetuje lokalny stan i rejoinuje (onOpen w subskrypcji),
 *   - onClose resetuje joined/joinDone — sendJson jest zablokowane po zerwaniu,
 *   - REQUEST_TIMEOUT planuje retry zamiast pokazywać "brak dostępu",
 *   - cleanup (beforeunload) odpina subskrypcje i wysyła leave.
 *   - preview załączników: tw-d-none pokazywany/ukrywany klasą (kontrakt 9.8).
 *
 * Kontrakt z chat-embedded.js (synchronizowac przy zmianie — logika
 * kopiowana 1:1; renderery są stubami zapisującymi wywołania).
 */

// ── fake ws — ten sam kształt co websocket-manager.js ───────────────────────
function makeWs() {
    return {
        open: true,
        sent: [],
        joinResult: Promise.resolve({}),
        msgHandler: null,
        connSub: null,
        sendJson(o) { this.sent.push(o); },
        sendJsonAsync(o) { this.sent.push(o); return this.joinResult; },
        isOpen() { return this.open; },
        subscribeMessages(h) { this.msgHandler = h; return () => { this.msgHandler = null; }; },
        subscribeConnection(s) { this.connSub = s; return () => { this.connSub = null; }; },
    };
}

/**
 * Wierna kopia lifecycle z chat-embedded.js — synchronizowac przy zmianie!
 * Stubowane są tylko renderery (appendMessage/updateMessage zbierają wywołania)
 * oraz elementy UI; reszta logiki jest identyczna z produkcją.
 */
function makeEmbeddedHarness({ roomId = 7 } = {}) {
    const ws = makeWs();
    const messagesEl = document.createElement('div');
    const appended = [];
    const deleted = { container: false, previewHidden: false };
    const previewContainer = document.createElement('div');
    previewContainer.classList.add('image-preview-container', 'ec-image-preview-container', 'tw-d-none');
    const previewImagesDiv = document.createElement('div');
    const fileInput = { value: 'x' };
    let selectedFiles = [];

    const appendMessage = (msg) => appended.push(msg);
    const updateMessage = () => {};
    const updateReactions = () => {};
    const updateVotes = () => {};

    // ── 1:1 z initEmbeddedChat ────────────────────────────────────────────
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
                return new Promise(resolve => setTimeout(() => {
                    joinDone = true;
                    messagesEl.innerHTML = '';
                    for (const msg of pendingMessages) appendMessage(msg);
                    pendingMessages = [];
                    if (messagesEl.children.length === 0) {
                        messagesEl.innerHTML = '<div class="ec-empty empty-chat-message">Brak wiadomości. Napisz pierwszy!</div>';
                    }
                    resolve();
                }, 0));
            })
            .catch(err => {
                joinInFlight = false;
                if (err === 'REQUEST_TIMEOUT') {
                    // Błąd przejściowy — spróbuj ponownie, nie pokazuj "brak dostępu".
                    console.warn('embedded chat join timeout, retrying:', err);
                    setTimeout(() => { if (!joined && ws.isOpen()) joinRoom(); }, 5000);
                    return;
                }
                messagesEl.innerHTML = '<div class="ec-loading">Brak dostępu do tego czatu.</div>';
                deleted.container = true;
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
            updateReactions(data.update_reactions);
        }
        if (data.update_votes) {
            updateVotes(data.update_votes);
        }
    }

    const unsubscribeMessages = ws.subscribeMessages(onMessage);
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

    // beforeunload cleanup — kopia 1:1
    const onBeforeUnload = () => {
        unsubscribeMessages();
        unsubscribeConnection();
        if (joined) ws.sendJson({ command: 'leave', room_id: roomId });
    };

    // delete-images-preview handler — kopia 1:1 z listenera w chat-embedded.js
    const deleteImagesHandler = () => {
        selectedFiles = [];
        fileInput.value = '';
        previewContainer.classList.add('tw-d-none');
        previewImagesDiv.innerHTML = '';
    };

    const flushJoin = async () => {
        // sendJsonAsync promise + wewnętrzny setTimeout(0) w .then
        await Promise.resolve();
        await new Promise(r => setTimeout(r, 0));
    };

    return {
        ws, messagesEl, appended, deleted,
        previewContainer, previewImagesDiv, fileInput, deleteImagesHandler,
        joinRoom, onMessage, onBeforeUnload, flushJoin,
        get joined() { return joined; },
        get joinDone() { return joinDone; },
        get pendingCount() { return pendingMessages.length; },
        set selectedFiles(v) { selectedFiles = v; },
        get selectedFiles() { return selectedFiles; },
    };
}

beforeEach(() => {
    jest.spyOn(console, 'warn').mockImplementation(() => {});
    jest.spyOn(console, 'error').mockImplementation(() => {});
});
afterEach(() => {
    console.warn.mockRestore();
    console.error.mockRestore();
    jest.useRealTimers();
});

describe('embedded chat — lifecycle połączenia', () => {
    test('pierwszy open subskrypcji wywołuje join', async () => {
        const h = makeEmbeddedHarness();
        h.ws.connSub.onOpen({ reconnected: false, alreadyOpen: false });
        expect(h.ws.sent).toContainEqual({ command: 'join', room_id: 7 });
        await h.flushJoin();
        expect(h.joined).toBe(true);
        expect(h.joinDone).toBe(true);
    });

    test('wiadomości w trakcie joinu są buforowane i renderowane RAZ', async () => {
        const h = makeEmbeddedHarness();
        // open startuje join — wiadomości przychodzą, zanim join się domknie
        h.ws.connSub.onOpen({ reconnected: false });
        h.onMessage({ messages: [{ message_id: 1, room_id: 7 }, { message_id: 2, room_id: 7 }] });
        expect(h.appended.length).toBe(0);
        expect(h.pendingCount).toBe(2);

        await h.flushJoin();
        // bufor opróżniony dokładnie raz — żadnego podwójnego renderu
        expect(h.appended.map(m => m.message_id)).toEqual([1, 2]);
        expect(h.pendingCount).toBe(0);

        // kolejna wiadomość renderuje się od razu
        h.onMessage({ messages: [{ message_id: 3, room_id: 7 }] });
        expect(h.appended.map(m => m.message_id)).toEqual([1, 2, 3]);
    });

    test('wiadomości z innego pokoju są ignorowane', async () => {
        const h = makeEmbeddedHarness();
        h.ws.connSub.onOpen({ reconnected: false });
        await h.flushJoin();
        h.onMessage({ messages: [{ message_id: 1, room_id: 99 }] });
        expect(h.appended.length).toBe(0);
    });

    test('reconnect resetuje stan i rejoinuje — bez utraty nowych wiadomości', async () => {
        const h = makeEmbeddedHarness();
        h.ws.connSub.onOpen({ reconnected: false });
        await h.flushJoin();
        expect(h.joined).toBe(true);

        // zerwanie
        h.ws.connSub.onClose();
        expect(h.joined).toBe(false);
        expect(h.joinDone).toBe(false);

        // reconnect — bufor wyczyszczony, drugi join
        h.ws.sent.length = 0;
        h.appended.length = 0;
        h.ws.connSub.onOpen({ reconnected: true });
        expect(h.ws.sent).toContainEqual({ command: 'join', room_id: 7 });

        // wiadomość w trakcie rejoinu → bufor, nie zgubiona
        h.onMessage({ messages: [{ message_id: 10, room_id: 7 }] });
        await h.flushJoin();
        expect(h.appended.map(m => m.message_id)).toEqual([10]);
    });

    test('REQUEST_TIMEOUT planuje retry, a nie "brak dostępu"', async () => {
        jest.useFakeTimers();
        const h = makeEmbeddedHarness();
        let first = true;
        h.ws.sendJsonAsync = (o) => {
            h.ws.sent.push(o);
            const p = first ? Promise.reject('REQUEST_TIMEOUT') : Promise.resolve({});
            first = false;
            return p;
        };
        h.joinRoom();
        // catch siedzi za .then — potrzebne kilka ticków mikrozadań,
        // żeby zaplanował retry na fake timerze.
        await Promise.resolve();
        await Promise.resolve();
        await Promise.resolve();
        expect(h.deleted.container).toBe(false);
        // retry po 5 s (fake timers — wszystko synchronicznie sterowane)
        jest.advanceTimersByTime(5000);
        await Promise.resolve(); // .then drugiego joinu — joined ustawione
        await Promise.resolve();
        expect(h.ws.sent.filter(o => o.command === 'join').length).toBe(2);
        expect(h.joined).toBe(true);
        // wewnętrzny setTimeout(0) → joinDone + opróżnienie bufora
        jest.advanceTimersByTime(0);
        await Promise.resolve();
        expect(h.joinDone).toBe(true);
    });

    test('błąd inny niż timeout pokazuje stan "brak dostępu"', async () => {
        const h = makeEmbeddedHarness();
        h.ws.sendJsonAsync = (o) => { h.ws.sent.push(o); return Promise.reject('ACCESS_DENIED'); };
        h.joinRoom();
        await Promise.resolve();
        await Promise.resolve();
        expect(h.deleted.container).toBe(true);
        expect(h.messagesEl.innerHTML).toContain('Brak dostępu');
    });

    test('cleanup odpina subskrypcje i wysyła leave gdy joined', async () => {
        const h = makeEmbeddedHarness();
        h.ws.connSub.onOpen({ reconnected: false });
        await h.flushJoin();

        h.onBeforeUnload();
        expect(h.ws.msgHandler).toBeNull();
        expect(h.ws.connSub).toBeNull();
        expect(h.ws.sent).toContainEqual({ command: 'leave', room_id: 7 });
    });

    test('cleanup bez joina nie wysyła leave', () => {
        const h = makeEmbeddedHarness();
        h.onBeforeUnload();
        expect(h.ws.sent.find(o => o.command === 'leave')).toBeUndefined();
    });
});

describe('embedded chat — preview załączników (kontrakt tw-d-none)', () => {
    test('usunięcie wszystkich podglądów chowa kontener klasą tw-d-none', () => {
        const h = makeEmbeddedHarness();
        // symulacja: user dodał plik — kontener pokazany
        h.previewContainer.classList.remove('tw-d-none');
        h.previewImagesDiv.innerHTML = '<div class="image-preview-wrapper">x</div>';
        h.selectedFiles = [{}];

        h.deleteImagesHandler();

        expect(h.previewContainer.classList.contains('tw-d-none')).toBe(true);
        expect(h.previewImagesDiv.innerHTML).toBe('');
        expect(h.fileInput.value).toBe('');
        expect(h.selectedFiles.length).toBe(0);
    });
});
