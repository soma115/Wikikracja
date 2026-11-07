/**
 * @jest-environment jsdom
 */
const fs = require('fs');
const path = require('path');

const APP_JS_PATH = path.join(__dirname, '..', 'app.js');

function loadAppScript() {
    const src = fs.readFileSync(APP_JS_PATH, 'utf8');
    new Function(src)();
}

function createCheckbox(form, name, value, checked = false) {
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.name = name;
    checkbox.value = value;
    checkbox.id = `payer-${name}-${value}`;
    checkbox.dataset.shiftRangeSelect = 'true';
    checkbox.checked = checked;
    form.appendChild(checkbox);
    const label = document.createElement('label');
    label.htmlFor = checkbox.id;
    label.textContent = value;
    form.appendChild(label);
    return checkbox;
}

function clickCheckbox(checkbox, { shiftKey = false } = {}) {
    checkbox.dispatchEvent(new MouseEvent('click', { bubbles: true, shiftKey }));
}

describe('shift range checkbox selection', () => {
    beforeAll(() => {
        loadAppScript();
    });

    beforeEach(() => {
        document.body.innerHTML = '';
    });

    test('checks the inclusive range between the last and shift-clicked checkbox', () => {
        const form = document.createElement('form');
        const members = Array.from({ length: 6 }, (_, index) => createCheckbox(form, 'debtors', String(index)));
        document.body.appendChild(form);
        window.initShiftRangeCheckboxes(form);

        clickCheckbox(members[1]);
        clickCheckbox(members[4], { shiftKey: true });

        expect(members.map((checkbox) => checkbox.checked)).toEqual([false, true, true, true, true, false]);
    });

    test('unchecks the inclusive range when shift-clicking an unchecked item', () => {
        const form = document.createElement('form');
        const members = Array.from({ length: 5 }, (_, index) => createCheckbox(form, 'debtors', String(index), true));
        document.body.appendChild(form);
        window.initShiftRangeCheckboxes(form);

        clickCheckbox(members[4]);
        clickCheckbox(members[1], { shiftKey: true });

        expect(members.map((checkbox) => checkbox.checked)).toEqual([true, false, false, false, false]);
    });

    test('applies shift range when the user clicks the checkbox label', () => {
        const form = document.createElement('form');
        const members = Array.from({ length: 4 }, (_, index) => createCheckbox(form, 'debtors', String(index)));
        document.body.appendChild(form);
        window.initShiftRangeCheckboxes(form);

        clickCheckbox(members[0]);
        members[3].labels[0].dispatchEvent(new MouseEvent('click', { bubbles: true, shiftKey: true }));

        expect(members.map((checkbox) => checkbox.checked)).toEqual([true, true, true, true]);
    });

    test('keeps range selection separate for different payer fields', () => {
        const form = document.createElement('form');
        const members = [createCheckbox(form, 'debtors', 'member-1'), createCheckbox(form, 'debtors', 'member-2')];
        const partners = [createCheckbox(form, 'debtor_partners', 'partner-1'), createCheckbox(form, 'debtor_partners', 'partner-2')];
        document.body.appendChild(form);
        window.initShiftRangeCheckboxes(form);

        clickCheckbox(members[0]);
        clickCheckbox(partners[1], { shiftKey: true });

        expect(members.map((checkbox) => checkbox.checked)).toEqual([true, false]);
        expect(partners.map((checkbox) => checkbox.checked)).toEqual([false, true]);
    });

    test('select-all button selects only the matching payer group', () => {
        const form = document.createElement('form');
        const members = [createCheckbox(form, 'debtors', 'member-1'), createCheckbox(form, 'debtors', 'member-2')];
        const partners = [createCheckbox(form, 'debtor_partners', 'partner-1'), createCheckbox(form, 'debtor_partners', 'partner-2')];
        const selectAll = document.createElement('button');
        selectAll.type = 'button';
        selectAll.dataset.selectAllCheckboxes = 'debtors';
        selectAll.dataset.selectAllLabel = 'Select all';
        selectAll.dataset.deselectAllLabel = 'Deselect all';
        selectAll.textContent = selectAll.dataset.selectAllLabel;
        form.appendChild(selectAll);
        document.body.appendChild(form);
        window.initSelectAllCheckboxes(form);

        selectAll.click();

        expect(members.map((checkbox) => checkbox.checked)).toEqual([true, true]);
        expect(partners.map((checkbox) => checkbox.checked)).toEqual([false, false]);
        expect(selectAll.textContent).toBe('Deselect all');

        selectAll.click();

        expect(members.map((checkbox) => checkbox.checked)).toEqual([false, false]);
        expect(selectAll.textContent).toBe('Select all');
    });
});
