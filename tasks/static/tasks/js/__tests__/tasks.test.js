/**
 * @jest-environment jsdom
 */
const fs = require('fs');
const path = require('path');

const TASKS_JS_PATH = path.join(__dirname, '..', 'tasks.js');
let readyCallback;

function loadTasksScript() {
  const source = fs.readFileSync(TASKS_JS_PATH, 'utf8');
  new Function(source)();
}

describe('task detail interactions', () => {
  beforeAll(() => {
    window.wkOnReady = (callback) => { readyCallback = callback; };
    window.matchMedia = jest.fn(() => ({ matches: true }));
    window.CURRENT_USER = { id: 1 };
    window.TASK_HELPERS_I18N = {};
    window.TASK_AGAINST_I18N = {};
    window.WK_PRESENCE_GREEN_MINUTES = 5;
    window.escapeHtml = (value) => String(value);
    loadTasksScript();
  });

  beforeEach(() => {
    document.body.innerHTML = '';
    window.apiFetch = jest.fn(() => Promise.resolve({ ok: true }));
    window.initSortableList = jest.fn();
    window.TASK_SUBTASK_REORDER_URL = '';
  });

  test('saves subtask checkbox changes and updates the label', async () => {
    document.body.innerHTML = '<form data-subtask-toggle-form action="/tasks/1/subtasks/2/toggle/"><input data-subtask-toggle type="checkbox"><label>Prepare</label></form>';
    const checkbox = document.querySelector('[data-subtask-toggle]');
    const action = checkbox.closest('form').action;
    const label = document.querySelector('label');
    checkbox.checked = true;
    checkbox.dispatchEvent(new Event('change', { bubbles: true }));

    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(window.apiFetch).toHaveBeenCalledWith(action, expect.objectContaining({ method: 'POST' }));
    expect(label.classList.contains('tw-line-through')).toBe(true);
    expect(label.classList.contains('tw-text-muted')).toBe(true);
    expect(checkbox.disabled).toBe(false);
  });

  test('reverts a subtask checkbox when the request fails', async () => {
    window.apiFetch.mockResolvedValue({ ok: false });
    document.body.innerHTML = '<form data-subtask-toggle-form action="/tasks/1/subtasks/2/toggle/"><input data-subtask-toggle type="checkbox"><label>Prepare</label></form>';
    const checkbox = document.querySelector('[data-subtask-toggle]');
    checkbox.checked = true;
    checkbox.dispatchEvent(new Event('change', { bubbles: true }));

    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(checkbox.checked).toBe(false);
  });

  test('initializes sortable subtasks with the configured handle and endpoint', () => {
    document.body.innerHTML = '<ul data-subtask-list><li data-id="2"></li></ul>';
    window.TASK_SUBTASK_REORDER_URL = '/tasks/1/subtasks/reorder/';
    readyCallback();

    expect(window.initSortableList).toHaveBeenCalledWith(document.querySelector('[data-subtask-list]'), expect.objectContaining({
      reorderUrl: '/tasks/1/subtasks/reorder/',
      handle: '[data-subtask-handle]',
    }));
  });
});
