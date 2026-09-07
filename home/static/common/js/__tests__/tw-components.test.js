/**
 * @jest-environment jsdom
 *
 * Regression tests for the project-owned Tailwind UI components:
 * TwModal, TwDropdown, TwCollapse, TwTab, TwTooltip, TwPopover.
 */

function loadComponents() {
  require('../tw-collapse.js');
  require('../tw-dropdown.js');
  require('../tw-modal.js');
  require('../tw-popover.js');
  require('../tw-tab.js');
  require('../tw-tooltip.js');
}

describe('Tailwind UI components', () => {
  beforeAll(() => {
    document.body.innerHTML = `
      <!-- collapse -->
      <button type="button" data-tw-toggle="collapse" data-tw-target="#collapse-1" id="collapse-btn">Toggle</button>
      <div class="tw-collapse" id="collapse-1"></div>

      <!-- dropdown -->
      <div class="tw-dropdown" id="test-dropdown">
        <button type="button" data-tw-toggle="dropdown" id="dropdown-btn" aria-expanded="false">Menu</button>
        <ul class="tw-dropdown-menu" id="dropdown-menu">
          <li><a class="tw-dropdown-item" href="#">Item</a></li>
        </ul>
      </div>

      <!-- modal -->
      <button type="button" data-tw-toggle="modal" data-tw-target="#test-modal" id="modal-open">Open</button>
      <div class="tw-modal" id="test-modal">
        <div class="tw-modal-dialog">
          <button type="button" data-tw-dismiss="modal" id="modal-close">Close</button>
          <input type="text" />
        </div>
      </div>

      <!-- popover -->
      <button type="button" data-tw-toggle="popover" data-tw-title="Title" data-tw-content="Body" id="popover-btn">Popover</button>

      <!-- tabs -->
      <ul class="tw-nav-tabs" id="tabs">
        <li><a href="#tab-a" data-tw-toggle="tab" class="tw-active" id="tab-a-link">A</a></li>
        <li><a href="#tab-b" data-tw-toggle="tab" id="tab-b-link">B</a></li>
      </ul>
      <div id="tab-a" class="tw-tab-pane tw-show tw-active">A</div>
      <div id="tab-b" class="tw-tab-pane">B</div>

      <!-- tooltip -->
      <button type="button" data-tw-toggle="tooltip" data-tw-title="Tooltip" title="Tooltip" id="tooltip-btn">?</button>
    `;
    loadComponents();
  });

  beforeEach(() => {
    jest.useFakeTimers();

    // Close any open dropdown
    if (window.TwDropdown) window.TwDropdown.closeAll();

    // Close any open modal
    const openModal = document.querySelector('.tw-modal.tw-show');
    if (openModal && window.TwModal) window.TwModal.hide(openModal);

    // Reset collapse
    const collapse = document.getElementById('collapse-1');
    const collapseBtn = document.getElementById('collapse-btn');
    if (collapse) collapse.classList.remove('tw-show');
    if (collapseBtn) collapseBtn.setAttribute('aria-expanded', 'false');

    // Reset dropdown
    const dropdownMenu = document.getElementById('dropdown-menu');
    const dropdownBtn = document.getElementById('dropdown-btn');
    if (dropdownMenu) dropdownMenu.classList.remove('tw-show');
    if (dropdownBtn) dropdownBtn.setAttribute('aria-expanded', 'false');

    // Reset tabs to initial (A active)
    const tabA = document.getElementById('tab-a');
    const tabB = document.getElementById('tab-b');
    const linkA = document.getElementById('tab-a-link');
    const linkB = document.getElementById('tab-b-link');
    if (tabA) tabA.classList.add('tw-show', 'tw-active');
    if (tabA) tabA.setAttribute('aria-hidden', 'false');
    if (tabB) tabB.classList.remove('tw-show', 'tw-active');
    if (tabB) tabB.setAttribute('aria-hidden', 'true');
    if (linkA) {
      linkA.classList.add('tw-active');
      linkA.setAttribute('aria-selected', 'true');
    }
    if (linkB) {
      linkB.classList.remove('tw-active');
      linkB.setAttribute('aria-selected', 'false');
    }

    // Re-initialize popover so its per-element click listener is bound
    const popoverBtn = document.getElementById('popover-btn');
    if (popoverBtn) {
      const existing = window.TwPopover ? window.TwPopover.getInstance(popoverBtn) : null;
      if (existing) existing.dispose();
      if (window.TwPopover) window.TwPopover.getOrCreateInstance(popoverBtn);
    }

    // Remove floating elements and body lock
    document.body.classList.remove('tw-modal-open');
    document.querySelectorAll('.tw-tooltip, .tw-popover, .tw-modal-backdrop').forEach((el) => el.remove());
    document.querySelectorAll('[aria-describedby]').forEach((el) => el.removeAttribute('aria-describedby'));
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('TwCollapse', () => {
    test('toggle shows and hides', () => {
      const btn = document.getElementById('collapse-btn');
      const el = document.getElementById('collapse-1');

      btn.click();
      expect(el.classList.contains('tw-show')).toBe(true);
      expect(btn.getAttribute('aria-expanded')).toBe('true');

      btn.click();
      expect(el.classList.contains('tw-show')).toBe(false);
      expect(btn.getAttribute('aria-expanded')).toBe('false');
    });
  });

  describe('TwDropdown', () => {
    test('toggle shows menu', () => {
      const btn = document.getElementById('dropdown-btn');
      const menu = document.getElementById('dropdown-menu');

      btn.click();
      expect(menu.classList.contains('tw-show')).toBe(true);
      expect(btn.getAttribute('aria-expanded')).toBe('true');
    });

    test('click outside closes menu', () => {
      const btn = document.getElementById('dropdown-btn');
      const menu = document.getElementById('dropdown-menu');

      btn.click();
      document.body.click();
      expect(menu.classList.contains('tw-show')).toBe(false);
      expect(btn.getAttribute('aria-expanded')).toBe('false');
    });

    test('escape closes menu', () => {
      const btn = document.getElementById('dropdown-btn');
      const menu = document.getElementById('dropdown-menu');

      btn.click();
      const event = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true });
      document.dispatchEvent(event);

      expect(menu.classList.contains('tw-show')).toBe(false);
      expect(btn.getAttribute('aria-expanded')).toBe('false');
    });
  });

  describe('TwModal', () => {
    test('open adds tw-show and body lock', () => {
      const btn = document.getElementById('modal-open');
      const modal = document.getElementById('test-modal');

      btn.click();
      jest.advanceTimersByTime(300);

      expect(modal.classList.contains('tw-show')).toBe(true);
      expect(document.body.classList.contains('tw-modal-open')).toBe(true);
      expect(document.querySelector('.tw-modal-backdrop')).not.toBeNull();
    });

    test('dismiss removes tw-show', () => {
      const btn = document.getElementById('modal-open');
      const modal = document.getElementById('test-modal');
      const close = document.getElementById('modal-close');

      btn.click();
      jest.advanceTimersByTime(300);
      close.click();
      jest.advanceTimersByTime(300);

      expect(modal.classList.contains('tw-show')).toBe(false);
      expect(document.body.classList.contains('tw-modal-open')).toBe(false);
      expect(document.querySelector('.tw-modal-backdrop')).toBeNull();
    });

    test('escape closes modal', () => {
      const btn = document.getElementById('modal-open');
      const modal = document.getElementById('test-modal');

      btn.click();
      jest.advanceTimersByTime(300);
      const event = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true });
      document.dispatchEvent(event);
      jest.advanceTimersByTime(300);

      expect(modal.classList.contains('tw-show')).toBe(false);
      expect(document.body.classList.contains('tw-modal-open')).toBe(false);
    });
  });

  describe('TwPopover', () => {
    test('click shows popover', () => {
      const btn = document.getElementById('popover-btn');

      btn.click();
      const popover = document.querySelector('.tw-popover');

      expect(popover).not.toBeNull();
      expect(popover.classList.contains('tw-show')).toBe(true);
      expect(popover.textContent).toContain('Title');
      expect(popover.textContent).toContain('Body');
    });

    test('click on trigger toggles popover', () => {
      const btn = document.getElementById('popover-btn');

      btn.click();
      expect(document.querySelector('.tw-popover')).not.toBeNull();
      btn.click();
      expect(document.querySelector('.tw-popover')).toBeNull();
      expect(btn.hasAttribute('aria-describedby')).toBe(false);
    });

    test('manual trigger closes on outside click', () => {
      const btn = document.getElementById('popover-btn');
      const instance = window.TwPopover.getInstance(btn);
      if (instance) instance.dispose();

      const manual = new window.TwPopover(btn, { trigger: 'manual', html: true });
      manual.show();

      expect(document.querySelector('.tw-popover')).not.toBeNull();
      document.body.click();

      expect(document.querySelector('.tw-popover')).toBeNull();
      expect(btn.hasAttribute('aria-describedby')).toBe(false);
    });
  });

  describe('TwTab', () => {
    test('switch tab shows pane', () => {
      const linkA = document.getElementById('tab-a-link');
      const linkB = document.getElementById('tab-b-link');
      const paneA = document.getElementById('tab-a');
      const paneB = document.getElementById('tab-b');

      linkB.click();

      expect(paneB.classList.contains('tw-show')).toBe(true);
      expect(paneA.classList.contains('tw-show')).toBe(false);
      expect(linkB.classList.contains('tw-active')).toBe(true);
      expect(linkA.classList.contains('tw-active')).toBe(false);
    });
  });

  describe('TwTooltip', () => {
    test('mouseenter creates tooltip', () => {
      const btn = document.getElementById('tooltip-btn');

      btn.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
      const tip = document.querySelector('.tw-tooltip');

      expect(tip).not.toBeNull();
      expect(tip.classList.contains('tw-show')).toBe(true);
      expect(tip.textContent).toBe('Tooltip');
    });

    test('mouseleave removes tooltip', () => {
      const btn = document.getElementById('tooltip-btn');

      btn.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
      btn.dispatchEvent(new MouseEvent('mouseleave', { bubbles: true }));

      expect(document.querySelector('.tw-tooltip')).toBeNull();
      expect(btn.hasAttribute('aria-describedby')).toBe(false);
    });
  });
});
