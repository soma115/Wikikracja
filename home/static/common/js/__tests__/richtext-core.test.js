/**
 * @jest-environment jsdom
 *
 * Testy dla richtext-core.js — pure functions sanityzacji/serializacji
 * używane przez chat (normal + embedded) oraz RichTextWidget (glosowania/tasks/events).
 *
 * Bugi które pokrywamy:
 *   A) getInputHtml duplikował <br> dla bloków zawierających <br> (np. <div><br></div> →
 *      "<br><br>" zamiast "<br>"). Powodowało puste linie w renderze po wklejeniu tekstu
 *      z łamaniem linii (browser auto-wrappuje paste w <div> bloki + filler <br>).
 *
 *   B) Paste handlery (richtext-input.js, chat/handlers.js, chat-embedded.js) używały
 *      execCommand('insertText', ...) który zostawia auto-wrapping do browsera. Nowa
 *      funkcja insertPlainTextAtCaret wstawia text+<br> bezpośrednio przez DOM API,
 *      eliminując quirki przeglądarki i normalizując \r\n → \n.
 *
 * Strategia ładowania: czytamy richtext-core.js z dysku, usuwamy `export` keywords,
 * i ekstraktujemy funkcje przez `new Function`. Testujemy REAL kod (nie kopia), bez
 * zmian konfigu Jest na ESM.
 */

const fs = require('fs');
const path = require('path');

const CORE_PATH = path.join(__dirname, '..', 'richtext-core.js');

function loadCore() {
    const src = fs.readFileSync(CORE_PATH, 'utf8').replace(/export\s+/g, '');
    const names = [
        'getInputHtml',
        'formatMessage',
        'updateCounter',
        'handleEnterKey',
        'handleListTrigger',
        'getVisibleTextLength',
        'initGlobalPasteImageHandler',
        'insertPlainTextAtCaret',
    ];
    const factory = new Function(`${src}; return { ${names.join(', ')} };`);
    return factory();
}

let core;

beforeAll(() => {
    core = loadCore();
});

beforeEach(() => {
    document.body.innerHTML = '';
});

function makeEditable(html = '') {
    const el = document.createElement('div');
    el.setAttribute('contenteditable', 'true');
    el.innerHTML = html;
    document.body.appendChild(el);
    return el;
}

// ── Bug A: getInputHtml serializer — bloki z <br> nie powinny duplikować ─────

describe('getInputHtml — bloki zawierające <br>', () => {

    test('<div><br></div> (pusta linia po paście) renderuje pojedyncze złamanie', () => {
        const el = makeEditable('<div><br></div>');
        // Pusty blok to JEDNO logiczne złamanie linii — block-prefix <br> wystarczy.
        // Inner <br> to filler żeby div miał wysokość — nie powinien być serializowany.
        expect(core.getInputHtml(el)).toBe('<br>');
    });

    test('<div>X<br></div> (Firefox trailing filler br) — trailing br stripped', () => {
        // Single block z contentem to wizualnie jedna linia "X" — render też ma być "X",
        // bez wiodącego ani końcowego br. Filler <br> jest artefaktem przeglądarki.
        const el = makeEditable('<div>X<br></div>');
        expect(core.getInputHtml(el)).toBe('X');
    });

    test('<div>A</div><div><br></div><div>B</div> — jedna pusta linia daje 2 <br>', () => {
        const el = makeEditable('<div>A</div><div><br></div><div>B</div>');
        // A + (nowa linia) + (pusta linia) + B = A<br><br>B
        expect(core.getInputHtml(el)).toBe('A<br><br>B');
    });

    test('<div>A<br>B</div> — <br> w środku zachowany (user shift+enter)', () => {
        const el = makeEditable('<div>A<br>B</div>');
        expect(core.getInputHtml(el)).toBe('A<br>B');
    });

    test('regresja: <div>A</div><div>B</div> daje A<br>B', () => {
        const el = makeEditable('<div>A</div><div>B</div>');
        expect(core.getInputHtml(el)).toBe('A<br>B');
    });

    test('regresja: czyste text + <br> bez bloków', () => {
        const el = makeEditable('A<br>B');
        expect(core.getInputHtml(el)).toBe('A<br>B');
    });

    test('regresja: bold/italic wewnątrz bloku', () => {
        const el = makeEditable('<div><b>A</b></div><div><i>B</i></div>');
        expect(core.getInputHtml(el)).toBe('<b>A</b><br><i>B</i>');
    });

    test('zagnieżdżone bloki z trailing br', () => {
        const el = makeEditable('<div><div>A<br></div></div>');
        expect(core.getInputHtml(el)).toBe('A');
    });

    test('wiele pustych linii pod rząd', () => {
        const el = makeEditable('<div>A</div><div><br></div><div><br></div><div>B</div>');
        // A + 1 nowa linia + 2 puste linie + B = A + 3 <br> + B
        expect(core.getInputHtml(el)).toBe('A<br><br><br>B');
    });

    test('regresja: <br> + blok nie podwaja złamania (edycja przepisu)', () => {
        // Przeglądarka miesza <br> i <div> przy edycji wczytanej treści "A<br>B":
        // klik w drugą linię i edycja daje "A<br><div>B</div>". Bez fix-a serializowało
        // się to do "A<br><br>B" → ghost pusta linia nad edytowaną linią.
        const el = makeEditable('A<br><div>B</div>');
        expect(core.getInputHtml(el)).toBe('A<br>B');
    });

    test('regresja: <br> + blok na top-level (wiele linii)', () => {
        const el = makeEditable('A<br><div>B</div><div>C</div>');
        expect(core.getInputHtml(el)).toBe('A<br>B<br>C');
    });
});

// ── Bug C: text node z surowym \n (stary content z DB) ───────────────────────
//
// Stare wpisy (sprzed fix-a paste) mogą mieć surowe \n w polach DB. Widget render
// wstawia to as-is do contenteditable → text node z \n. Browser ignoruje wizualnie,
// ale richtext|filter konwertuje \n → <br> przy renderze → ghost empty lines.
// Serializer musi normalizować \n w text node, żeby save dawał czysty <br>.

describe('getInputHtml — text node z surowym \\n (legacy DB content)', () => {

    test('text node "A\\nB" → "A<br>B"', () => {
        const el = makeEditable('');
        el.appendChild(document.createTextNode('A\nB'));
        expect(core.getInputHtml(el)).toBe('A<br>B');
    });

    test('<div>A\\nB</div> — \\n w text node wewnątrz bloku', () => {
        const el = document.createElement('div');
        el.setAttribute('contenteditable', 'true');
        const inner = document.createElement('div');
        inner.appendChild(document.createTextNode('A\nB'));
        el.appendChild(inner);
        document.body.appendChild(el);
        expect(core.getInputHtml(el)).toBe('A<br>B');
    });

    test('<b>X\\nY</b> — \\n w text node wewnątrz formatowania', () => {
        const el = document.createElement('div');
        el.setAttribute('contenteditable', 'true');
        const b = document.createElement('b');
        b.appendChild(document.createTextNode('X\nY'));
        el.appendChild(b);
        document.body.appendChild(el);
        expect(core.getInputHtml(el)).toBe('<b>X<br>Y</b>');
    });

    test('multi-line text node: "A\\nB\\nC" → "A<br>B<br>C"', () => {
        const el = makeEditable('');
        el.appendChild(document.createTextNode('A\nB\nC'));
        expect(core.getInputHtml(el)).toBe('A<br>B<br>C');
    });

    test('podwójny \\n\\n staje się <br><br> (pusta linia w legacy text)', () => {
        const el = makeEditable('');
        el.appendChild(document.createTextNode('A\n\nB'));
        expect(core.getInputHtml(el)).toBe('A<br><br>B');
    });

    test('mix: TEXT_NODE z \\n + element <br> obok', () => {
        const el = makeEditable('');
        el.appendChild(document.createTextNode('A\nB'));
        el.appendChild(document.createElement('br'));
        el.appendChild(document.createTextNode('C'));
        expect(core.getInputHtml(el)).toBe('A<br>B<br>C');
    });
});

// ── Bug B: insertPlainTextAtCaret — wstawianie tekstu z \n jako DOM ──────────

describe('insertPlainTextAtCaret — DOM structure', () => {

    function placeCaretInto(el) {
        const range = document.createRange();
        range.selectNodeContents(el);
        range.collapse(false);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
    }

    test('wstawia text+<br>+text dla "A\\nB"', () => {
        const el = makeEditable('');
        placeCaretInto(el);
        core.insertPlainTextAtCaret(el, 'A\nB');
        const html = core.getInputHtml(el);
        expect(html).toBe('A<br>B');
    });

    test('normalizuje \\r\\n do \\n', () => {
        const el = makeEditable('');
        placeCaretInto(el);
        core.insertPlainTextAtCaret(el, 'A\r\nB');
        expect(core.getInputHtml(el)).toBe('A<br>B');
    });

    test('normalizuje samotne \\r do \\n', () => {
        const el = makeEditable('');
        placeCaretInto(el);
        core.insertPlainTextAtCaret(el, 'A\rB');
        expect(core.getInputHtml(el)).toBe('A<br>B');
    });

    test('pusta linia: "A\\n\\nB" → A<br><br>B', () => {
        const el = makeEditable('');
        placeCaretInto(el);
        core.insertPlainTextAtCaret(el, 'A\n\nB');
        expect(core.getInputHtml(el)).toBe('A<br><br>B');
    });

    test('respektuje maxLength — truncate', () => {
        const el = makeEditable('');
        placeCaretInto(el);
        core.insertPlainTextAtCaret(el, 'abcdef', 3);
        expect(el.textContent).toBe('abc');
    });

    test('maxLength uwzględnia obecną zawartość', () => {
        const el = makeEditable('xx');
        placeCaretInto(el);
        core.insertPlainTextAtCaret(el, 'abcd', 5);
        // xx (2 znaki) + 3 dostępne = "xxabc"
        expect(el.textContent).toBe('xxabc');
    });

    test('zastępuje zaznaczenie', () => {
        const el = makeEditable('abc');
        // Zaznacz "b" (offset 1 do 2)
        const range = document.createRange();
        range.setStart(el.firstChild, 1);
        range.setEnd(el.firstChild, 2);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
        core.insertPlainTextAtCaret(el, 'XYZ');
        expect(el.textContent).toBe('aXYZc');
    });

    test('wstawia w pozycji caret, nie na końcu', () => {
        const el = makeEditable('abc');
        // Caret po "a"
        const range = document.createRange();
        range.setStart(el.firstChild, 1);
        range.collapse(true);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
        core.insertPlainTextAtCaret(el, 'X');
        expect(el.textContent).toBe('aXbc');
    });

    test('caret pozostaje po wstawionym tekście', () => {
        const el = makeEditable('abc');
        const range = document.createRange();
        range.setStart(el.firstChild, 1);
        range.collapse(true);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
        core.insertPlainTextAtCaret(el, 'X');
        // Następne wstawienie powinno iść po "X" — czyli "aXYbc"
        core.insertPlainTextAtCaret(el, 'Y');
        expect(el.textContent).toBe('aXYbc');
    });

    test('puste/zerowe insert nie robi nic', () => {
        const el = makeEditable('abc');
        placeCaretInto(el);
        core.insertPlainTextAtCaret(el, '');
        expect(el.textContent).toBe('abc');
    });

    test('maxLength=0 — nic nie wstawia', () => {
        const el = makeEditable('');
        placeCaretInto(el);
        core.insertPlainTextAtCaret(el, 'abc', 0);
        expect(el.textContent).toBe('');
    });
});

// ── formatMessage: linkifikacja URL-i z &amp; w query stringu ─────────────────
//
// Bug: URL_REGEX nie zawierał ';' w character class query stringu, więc gdy
// bleach.clean zamieniał & → &amp;, regex zatrzymywał się na ';' i ucinał
// resztę parametrów (np. &t=721 w YouTube URL).
//
// Fix: podejście A — alternacja (char_class|&amp;)* zamiast dodania ';' do
// char class. Dzięki temu ';' jest akceptowany TYLKO jako część sekwencji &amp;,
// a samotny ';' na końcu zdania nie jest wciągany do URL.
//
// Uwaga o środowisku testowym: loadCore() działa przez new Function bez DOMPurify,
// więc typeof DOMPurify === 'undefined' i input nie jest sanityzowany.
// Testy operują bezpośrednio na wyjściu bleach.clean (stan po backendzkie), co jest
// dokładnie tym stanem, który trafia do formatMessage() w produkcji.

describe('formatMessage — linkifikacja URL z parametrami', () => {

    test('URL z &amp; (encja HTML) linkifikuje cały query string', () => {
        // Backend (bleach.clean) produkuje &amp; zamiast & — frontend musi go złapać.
        const input = 'https://www.youtube.com/watch?v=GBISeUYMzoU&amp;t=721';
        const result = core.formatMessage(input);
        expect(result).toContain('href="https://www.youtube.com/watch?v=GBISeUYMzoU&amp;t=721"');
        expect(result).not.toContain('href="https://www.youtube.com/watch?v=GBISeUYMzoU&amp"');
    });

    test('URL z wieloma parametrami (&amp; jako separator) linkifikuje wszystkie', () => {
        const input = 'https://example.com/page?a=1&amp;b=2&amp;c=3';
        const result = core.formatMessage(input);
        expect(result).toContain('href="https://example.com/page?a=1&amp;b=2&amp;c=3"');
    });

    test('prosty URL bez parametrów nadal działa', () => {
        const input = 'https://example.com/path';
        const result = core.formatMessage(input);
        expect(result).toContain('href="https://example.com/path"');
    });

    test('regresja: średnik po URL (koniec zdania) nie jest wciągany do linku', () => {
        // Samotny ';' nie jest w char class ani nie startuje '&amp;' — URL urwie się przed nim.
        const input = 'Zobacz https://example.com/page; potem coś';
        const result = core.formatMessage(input);
        expect(result).toContain('href="https://example.com/page"');
        expect(result).not.toContain('href="https://example.com/page;"');
    });

    test('URL już zawinięty w <a> przez backend nie jest podwójnie linkifikowany', () => {
        // Alt 1 regexa (?:<a\b...) łapie istniejące <a> i zwraca je niezmienione.
        // Guard dla głównego flow chatu — backend (bleach.linkify) już linkifikuje URL,
        // więc formatMessage nie powinno tworzyć zagnieżdżonych <a>.
        const input = 'Zobacz <a href="https://youtube.com/?v=X&amp;t=721" target="_blank" rel="noopener">YouTube</a> dzisiaj';
        const result = core.formatMessage(input);
        expect(result).not.toMatch(/<a[^>]*><a/);
        expect(result).toContain('href="https://youtube.com/?v=X&amp;t=721"');
    });
});

// ── Integracja: paste-flow end-to-end ────────────────────────────────────────

describe('insertPlainTextAtCaret + getInputHtml — paste flow E2E', () => {

    test('paste wielo-linijkowego tekstu Polskiego z pustymi liniami', () => {
        const el = makeEditable('');
        const range = document.createRange();
        range.selectNodeContents(el);
        range.collapse(false);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);

        const pasted = 'Polska to kraj.\n\nMasz pomysł?\n- Zgłaszasz.';
        core.insertPlainTextAtCaret(el, pasted);

        const html = core.getInputHtml(el);
        expect(html).toBe('Polska to kraj.<br><br>Masz pomysł?<br>- Zgłaszasz.');
    });

    test('paste z Windows line endings (CRLF) daje ten sam wynik co LF', () => {
        const el = makeEditable('');
        const range = document.createRange();
        range.selectNodeContents(el);
        range.collapse(false);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);

        core.insertPlainTextAtCaret(el, 'A\r\nB\r\nC');
        expect(core.getInputHtml(el)).toBe('A<br>B<br>C');
    });
});
