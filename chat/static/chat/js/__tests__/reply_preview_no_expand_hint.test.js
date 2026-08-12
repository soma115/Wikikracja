/**
 * @jest-environment jsdom
 *
 * Test regresyjny: snippet cytowanej wiadomości używany w reply-preview
 * (data-snippet przycisku "Odpowiedz") musi pochodzić z surowej treści,
 * nie z HTML'u owiniętego w .expandable.
 *
 * Bug: przycisk odpowiedzi brał `message` (sformatowany HTML z
 * .expandable-hint "… pokaż więcej"), więc podgląd cytowanej wiadomości
 * kończył się tekstem "… pokaż więcej".
 *
 * Fix: używać `raw_message` do generowania data-snippet.
 */

// ── wierna kopia logiki z templates.js (synchronizować przy zmianie!) ──────

function makeSnippet(message) {
    return message.replace(/<[^>]*>/g, '').slice(0, 320);
}

// ── testy ──────────────────────────────────────────────────────────────────

test('snippet z surowej wiadomości nie zawiera markera "pokaż więcej"', () => {
    const raw_message = 'Długa wiadomość testowa ' + 'x'.repeat(180);
    const snippet = makeSnippet(raw_message);
    expect(snippet).not.toContain('pokaż więcej');
    expect(snippet.length).toBeLessThanOrEqual(320);
    expect(snippet.endsWith('x')).toBe(true);
});

test('snippet z sformatowanej wiadomości .expandable zawierałby marker (demonstrowanie błędu)', () => {
    const raw_message = 'Krótka treść';
    const message = `<div class="expandable"><div class="expandable-body">${raw_message}</div><div class="expandable-hint">… pokaż więcej</div></div>`;
    const snippet = makeSnippet(message);
    expect(snippet).toContain('… pokaż więcej');
});
