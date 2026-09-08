// Weryfikacja regresji: paste tekstu z pustymi liniami w RichTextWidget formularza
// nie powinno produkować nadmiarowych <br> w wysyłanym HTML.
//
// Przed fix'em w richtext-core.js: paste "A\n\nB" generował hidden value "A<br><br><br>B"
// (browser auto-wrappował tekst w <div> bloki z filler <br>, a serializer dodawał drugi
// <br> dla bloku). Po fix'cie: "A<br><br>B" (jedno br = nowa linia, drugie = pusta linia).
//
// Testuje formularz ankiety (/ankiety/dodaj/), który używa RichTextWidget dla pola description.
const { test, expect } = require('@playwright/test');

async function pasteAndCheck(page, text, expected) {
    await page.goto('/ankiety/dodaj/');
    await page.waitForSelector('.tw-richtext-wrapper');

    const wrapper = page.locator('.tw-richtext-wrapper').filter({
        has: page.locator('input[type="hidden"][name="description"]'),
    });
    const editor = wrapper.locator('.tw-richtext-input');
    await editor.click();

    await editor.evaluate((el, value) => {
        const dt = new DataTransfer();
        dt.setData('text/plain', value);
        el.dispatchEvent(new ClipboardEvent('paste', {
            clipboardData: dt,
            bubbles: true,
            cancelable: true,
        }));
    }, text);

    const hiddenValue = await wrapper.locator('input[type="hidden"][name="description"]').inputValue();
    expect(hiddenValue).toBe(expected);
}

test('paste z pustymi liniami daje poprawne <br> w hidden input', async ({ page }) => {
    await pasteAndCheck(page, 'A\n\nB\nC', 'A<br><br>B<br>C');
});

test('paste z Windows line endings (CRLF) daje ten sam wynik co LF', async ({ page }) => {
    await pasteAndCheck(page, 'A\r\n\r\nB\r\nC', 'A<br><br>B<br>C');
});
