/**
 * @jest-environment jsdom
 *
 * Tests for the shared window.apiFetch helper in common/js/dom-utils.js.
 */

describe('apiFetch', () => {
  beforeAll(() => {
    require('../dom-utils.js');
  });

  beforeEach(() => {
    window.fetch = jest.fn(() => Promise.resolve({ ok: true, status: 200 }));
    document.cookie = 'csrftoken=testtoken';
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  test('uses the method provided in options', async () => {
    await window.apiFetch('/toggle-bookmark/', {
      method: 'POST',
      body: new URLSearchParams({ content_type: 'event', object_id: '5' })
    });

    expect(window.fetch).toHaveBeenCalledTimes(1);
    const options = window.fetch.mock.calls[0][1];
    expect(options.method).toBe('POST');
  });

  test('sends X-CSRFToken header from cookie', async () => {
    await window.apiFetch('/mark-as-read/', {
      method: 'POST',
      body: new URLSearchParams({ content_type: 'post', object_id: '42' })
    });

    const options = window.fetch.mock.calls[0][1];
    expect(options.headers).toHaveProperty('X-CSRFToken', 'testtoken');
  });

  test('does not let fetchOptions override the explicit method', async () => {
    await window.apiFetch('/mark-as-read/', {
      method: 'POST',
      fetchOptions: { method: 'GET' },
      body: new URLSearchParams({ content_type: 'post', object_id: '42' })
    });

    const options = window.fetch.mock.calls[0][1];
    expect(options.method).toBe('POST');
  });

  test('sends URLSearchParams body as-is', async () => {
    const body = new URLSearchParams({ content_type: 'post', object_id: '42' });
    await window.apiFetch('/mark-as-read/', { method: 'POST', body: body });

    const options = window.fetch.mock.calls[0][1];
    expect(options.body).toBe(body);
  });
});
