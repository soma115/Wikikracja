/**
 * @jest-environment jsdom
 */

require('../dom-utils.js');

describe('vote submit state', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <form data-vote-submit>
        <button type="submit" name="tak">Yes</button>
        <button type="submit" name="nie">No</button>
        <span class="tw-hidden" data-vote-submit-status></span>
      </form>
    `;
  });

  test('disables both vote buttons and shows the saving status', () => {
    const form = document.querySelector('form');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));

    expect(form.getAttribute('aria-busy')).toBe('true');
    expect(form.dataset.submitting).toBe('true');
    expect(form.querySelector('[name="tak"]').disabled).toBe(true);
    expect(form.querySelector('[name="nie"]').disabled).toBe(true);
    expect(form.querySelector('[data-vote-submit-status]').classList.contains('tw-hidden')).toBe(false);
  });

  test('prevents a second submit while the first one is pending', () => {
    const form = document.querySelector('form');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    const secondSubmit = new Event('submit', { bubbles: true, cancelable: true });

    form.dispatchEvent(secondSubmit);

    expect(secondSubmit.defaultPrevented).toBe(true);
  });

  test('restores the form after returning through the browser cache', () => {
    const form = document.querySelector('form');
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    window.dispatchEvent(new Event('pageshow'));

    expect(form.dataset.submitting).toBe('false');
    expect(form.hasAttribute('aria-busy')).toBe(false);
    expect(form.querySelector('[name="tak"]').disabled).toBe(false);
    expect(form.querySelector('[name="nie"]').disabled).toBe(false);
    expect(form.querySelector('[data-vote-submit-status]').classList.contains('tw-hidden')).toBe(true);
  });
});
