/**
 * @jest-environment jsdom
 */

require('../dom-utils.js');

describe('vote submit state', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <form data-vote-submit>
        <button type="submit" name="tak" value="1">Yes</button>
        <button type="submit" name="nie" value="1">No</button>
        <span class="tw-hidden" data-vote-submit-status></span>
      </form>
    `;
  });

  test('opens a confirmation modal for the selected vote', () => {
    const form = document.querySelector('form');
    const yesButton = form.querySelector('[name="tak"]');
    form.dataset.voteConfirmTitle = 'Confirm your vote';
    form.dataset.voteConfirmCancel = 'Cancel';
    yesButton.dataset.voteConfirmMessage = 'Are you sure you want to vote Yes?';
    yesButton.dataset.voteConfirmAction = 'Vote Yes';
    form.requestSubmit = jest.fn();
    window.TwModal = { confirm: jest.fn() };
    const event = new Event('submit', { bubbles: true, cancelable: true });
    Object.defineProperty(event, 'submitter', { value: yesButton });

    form.dispatchEvent(event);

    expect(event.defaultPrevented).toBe(true);
    expect(window.TwModal.confirm).toHaveBeenCalledWith(expect.objectContaining({
      title: 'Confirm your vote',
      message: 'Are you sure you want to vote Yes?',
      confirmLabel: 'Vote Yes',
      cancelLabel: 'Cancel',
    }));
    window.TwModal.confirm.mock.calls[0][0].onConfirm();
    expect(form.requestSubmit).toHaveBeenCalledWith(yesButton);
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

  test('preserves the confirmed vote value while disabling the buttons', () => {
    const form = document.querySelector('form');
    const yesButton = form.querySelector('[name="tak"]');
    form.dataset.confirmed = 'true';
    const event = new Event('submit', { bubbles: true, cancelable: true });
    Object.defineProperty(event, 'submitter', { value: yesButton });

    form.dispatchEvent(event);

    expect(yesButton.disabled).toBe(true);
    expect(form.querySelector('[name="nie"]').disabled).toBe(true);
    expect(form.querySelector('[data-vote-submit-value]').value).toBe('1');
    expect(new FormData(form).get('tak')).toBe('1');
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
