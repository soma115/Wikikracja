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
    window.TASK_ID = 1;
    window.TASK_HELPERS_I18N = {};
    window.TASK_AGAINST_I18N = {};
    window.WK_PRESENCE_GREEN_MINUTES = 5;
    window.escapeHtml = (value) => String(value);
    loadTasksScript();
  });

  beforeEach(() => {
    document.body.innerHTML = '';
    window.apiFetch = jest.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ ok: true, states: [] }) }));
    window.initSortableList = jest.fn();
    window.TASK_SUBTASK_REORDER_URL = '';
    window.TASK_SUBTASK_I18N = {
      add_title: 'Add a task', edit_title: 'Edit task', add_label: 'Add', save_label: 'Save',
      delete_title: 'Delete task', delete_message: 'Are you sure you want to delete this task?',
      delete_confirm_label: 'Yes, delete', cancel_label: 'Cancel', item_title_label: 'Item',
      irreversible_message: 'This action cannot be undone.',
    };
  });

  test('updates detail-page voting buttons and counts without submitting the form', async () => {
    document.body.innerHTML = '<section><span data-votes-badge="Votes: ">Votes: 0</span><span data-realization-vote-score>0</span><div><form action="/tasks/1/vote/"><input name="value" value="1"><button class="tw-task-vote-btn tw-task-vote-btn--up" data-text-active="Helping" data-text-inactive="I want to help" data-icon-active="fa-check" data-icon-inactive="fa-plus" data-tooltip-active="Withdraw" data-tooltip-inactive="Vote to help"><i class="fas fa-plus"></i> I want to help</button></form><form action="/tasks/1/vote/"><input name="value" value="-1"><button class="tw-task-vote-btn tw-task-vote-btn--down" data-text-active="Against" data-text-inactive="Block" data-icon-active="fa-check" data-icon-inactive="fa-minus" data-tooltip-active="Withdraw" data-tooltip-inactive="Vote against"><i class="fas fa-minus"></i> Block</button></form></div></section>';
    window.apiFetch
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ vote: 1, votes_score: 1, votes_up: 1, votes_down: 0 }) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ vote: -1, votes_score: -1, votes_up: 0, votes_down: 1 }) });
    const buttons = document.querySelectorAll('.tw-task-vote-btn');

    const upClick = new MouseEvent('click', { bubbles: true, cancelable: true });
    buttons[0].dispatchEvent(upClick);
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(upClick.defaultPrevented).toBe(true);
    expect(buttons[0].classList.contains('tw-active')).toBe(true);
    expect(buttons[1].classList.contains('tw-active')).toBe(false);
    expect(buttons[0].textContent).toContain('Helping');
    expect(document.querySelector('[data-votes-badge]').textContent).toBe('Votes: 1');
    expect(document.querySelector('[data-realization-vote-score]').textContent).toBe('1');

    buttons[1].dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(buttons[0].classList.contains('tw-active')).toBe(false);
    expect(buttons[1].classList.contains('tw-active')).toBe(true);
    expect(buttons[1].textContent).toContain('Against');
    expect(document.querySelector('[data-votes-badge]').textContent).toBe('Votes: -1');
  });

  test('saves subtask checkbox changes and updates the label', async () => {
    window.apiFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve({ ok: true, states: [{ id: 2, is_completed: true }] }) });
    document.body.innerHTML = '<form data-subtask-toggle-form action="/tasks/1/subtasks/2/toggle/"><input id="subtask-2" data-subtask-toggle type="checkbox"><label>Prepare</label></form>';
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

  test('updates a parent checkbox and its children from the server cascade', async () => {
    window.apiFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ ok: true, states: [{ id: 1, is_completed: true }, { id: 2, is_completed: true }] }),
    });
    document.body.innerHTML = '<form data-subtask-toggle-form action="/tasks/1/subtasks/1/toggle/"><input id="subtask-1" data-subtask-toggle type="checkbox"><label>Parent</label></form><form data-subtask-toggle-form action="/tasks/1/subtasks/2/toggle/"><input id="subtask-2" data-subtask-toggle type="checkbox"><label>Child</label></form>';
    const parent = document.getElementById('subtask-1');
    const child = document.getElementById('subtask-2');
    parent.checked = true;
    parent.dispatchEvent(new Event('change', { bubbles: true }));

    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(parent.checked).toBe(true);
    expect(child.checked).toBe(true);
    expect(child.closest('form').querySelector('label').classList.contains('tw-line-through')).toBe(true);
  });

  test('reverts a subtask checkbox when the request fails', async () => {
    window.apiFetch.mockResolvedValue({ ok: false, json: () => Promise.resolve({ ok: false, states: [] }) });
    document.body.innerHTML = '<form data-subtask-toggle-form action="/tasks/1/subtasks/2/toggle/"><input data-subtask-toggle type="checkbox"><label>Prepare</label></form>';
    const checkbox = document.querySelector('[data-subtask-toggle]');
    checkbox.checked = true;
    checkbox.dispatchEvent(new Event('change', { bubbles: true }));

    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(checkbox.checked).toBe(false);
  });

  test('loads the selected subtask into the edit modal', () => {
    document.body.innerHTML = '<button data-subtask-edit data-edit-url="/tasks/1/subtasks/7/edit/" data-subtask-title="Fix &quot;quotes&quot; and &lt;markup&gt;"></button><h5 id="editSubtaskModalLabel"></h5><form id="editSubtaskForm"><input id="editSubtaskTitle"><i data-subtask-save-icon></i><span data-subtask-save-label></span></form>';
    document.querySelector('[data-subtask-edit]').dispatchEvent(new MouseEvent('click', { bubbles: true }));

    expect(document.getElementById('editSubtaskForm').action).toBe('http://localhost/tasks/1/subtasks/7/edit/');
    expect(document.getElementById('editSubtaskTitle').value).toBe('Fix "quotes" and <markup>');
    expect(document.getElementById('editSubtaskModalLabel').textContent).toBe('Edit task');
    expect(document.querySelector('[data-subtask-save-label]').textContent).toBe('Save');
  });

  test('confirms subtask deletion before submitting its form', () => {
    const confirm = jest.fn();
    window.TwModal = { confirm };
    document.body.innerHTML = '<form action="/tasks/1/subtasks/7/delete/"><button type="button" data-subtask-delete data-subtask-title="Prepare materials"></button></form>';
    const form = document.querySelector('form');
    form.requestSubmit = jest.fn();
    document.querySelector('[data-subtask-delete]').click();

    expect(confirm).toHaveBeenCalledWith(expect.objectContaining({
      title: 'Delete task',
      message: 'Are you sure you want to delete this task?',
      itemTitle: 'Prepare materials',
      irreversible: true,
      confirmLabel: 'Yes, delete',
      cancelLabel: 'Cancel',
      onConfirm: expect.any(Function),
    }));
    expect(form.requestSubmit).not.toHaveBeenCalled();
    confirm.mock.calls[0][0].onConfirm();
    expect(form.requestSubmit).toHaveBeenCalledTimes(1);
  });

  test('opens the same modal with a blank title when adding a subtask', () => {
    document.body.innerHTML = '<button data-subtask-add data-add-url="/tasks/1/subtasks/add/"></button><h5 id="editSubtaskModalLabel"></h5><form id="editSubtaskForm"><input id="editSubtaskTitle"><i data-subtask-save-icon></i><span data-subtask-save-label></span></form>';
    document.getElementById('editSubtaskTitle').value = 'Old value';
    document.querySelector('[data-subtask-add]').dispatchEvent(new MouseEvent('click', { bubbles: true }));

    expect(document.getElementById('editSubtaskForm').action).toBe('http://localhost/tasks/1/subtasks/add/');
    expect(document.getElementById('editSubtaskTitle').value).toBe('');
    expect(document.getElementById('editSubtaskModalLabel').textContent).toBe('Add a task');
    expect(document.querySelector('[data-subtask-save-label]').textContent).toBe('Add');
  });

  test('initializes nested sortable lists and serializes parent and sibling order', () => {
    document.body.innerHTML = '<ul data-subtask-sort-list data-parent-id=""><li data-id="1" data-parent-id=""><ul data-subtask-sort-list data-parent-id="1"><li data-id="2" data-parent-id="1"></li></ul></li><li data-id="3" data-parent-id=""><ul class="tw-hidden" data-subtask-sort-list data-parent-id="3" data-subtask-drop-target></ul></li><li data-id="4" data-parent-id=""></li></ul>';
    window.TASK_SUBTASK_REORDER_URL = '/tasks/1/subtasks/reorder/';
    readyCallback();

    expect(window.initSortableList).toHaveBeenCalledTimes(3);
    const [rootList, rootOptions] = window.initSortableList.mock.calls[0];
    const childList = document.querySelector('[data-parent-id="1"][data-subtask-sort-list]');
    const emptyDropTarget = document.querySelector('[data-subtask-drop-target]');
    expect(rootList.dataset.parentId).toBe('');
    expect(rootOptions.reorderUrl).toBe('/tasks/1/subtasks/reorder/');
    expect(rootOptions.handle).toBe('[data-subtask-handle]');
    expect(rootOptions.group.name).toBe('task-subtasks-1');
    expect(rootOptions.onStart).toBeInstanceOf(Function);
    expect(rootOptions.onEnd).toBeInstanceOf(Function);
    expect(rootOptions.serialize()).toEqual([
      { id: 1, parent_id: null, order: 0 },
      { id: 3, parent_id: null, order: 1 },
      { id: 4, parent_id: null, order: 2 },
      { id: 2, parent_id: 1, order: 0 },
    ]);
    expect(rootOptions.group.put({ el: childList }, rootList, document.querySelector('li[data-id="1"]'))).toBe(false);
    expect(rootOptions.group.put({ el: emptyDropTarget }, rootList, document.querySelector('li[data-id="3"]'))).toBe(false);
    expect(rootOptions.group.put({ el: emptyDropTarget }, rootList, document.querySelector('li[data-id="4"]'))).toBe(true);

    rootOptions.onStart();
    expect(emptyDropTarget.classList.contains('tw-hidden')).toBe(false);
    rootOptions.onEnd();
    expect(emptyDropTarget.classList.contains('tw-hidden')).toBe(true);
  });
});
