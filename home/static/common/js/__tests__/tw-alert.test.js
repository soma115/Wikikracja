/**
 * @jest-environment jsdom
 *
 * Regression tests for TwAlert dismiss behaviour.
 */

require('../tw-alert.js');

describe('TwAlert', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div role="alert" id="test-alert" class="tw-alert">
        <span>Alert message</span>
        <button type="button" data-tw-dismiss="alert">Close</button>
      </div>
    `;
  });

  test('dismiss button removes the alert', () => {
    const alert = document.getElementById('test-alert');
    const btn = alert.querySelector('[data-tw-dismiss="alert"]');
    btn.click();
    expect(document.getElementById('test-alert')).toBeNull();
  });
});
