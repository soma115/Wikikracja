/**
 * Lightweight project-owned Tailwind modal component.
 */
(function () {
  'use strict';

  function TwModal(element) {
    this._element = element;
    this._isShown = false;
    this._isTransitioning = false;
    this._backdrop = null;
  }

  const EVENT_KEY = '.tw.modal';

  TwModal.getInstance = function (element) {
    return element ? element._twModal : null;
  };

  TwModal.getOrCreateInstance = function (element) {
    if (!element) return null;
    let instance = TwModal.getInstance(element);
    if (!instance) {
      instance = new TwModal(element);
      element._twModal = instance;
    }
    return instance;
  };

  TwModal.show = function (element) {
    const instance = TwModal.getOrCreateInstance(element);
    if (instance) instance.show();
    return instance;
  };

  TwModal.hide = function (element) {
    const instance = TwModal.getOrCreateInstance(element);
    if (instance) instance.hide();
    return instance;
  };

  TwModal.prototype.show = function () {
    if (this._isShown || this._isTransitioning) return;
    const el = this._element;
    const showEvent = new CustomEvent('show' + EVENT_KEY, { bubbles: true, cancelable: true });
    el.dispatchEvent(showEvent);
    if (showEvent.defaultPrevented) return;

    this._isTransitioning = true;
    if (typeof TwDropdown !== 'undefined') TwDropdown.closeAll();
    document.body.classList.add('tw-modal-open');
    this._backdrop = this._createBackdrop();
    el.classList.add('tw-show');
    el.setAttribute('aria-hidden', 'false');
    if (this._backdrop) this._backdrop.classList.add('tw-show');

    setTimeout(() => {
      this._isShown = true;
      this._isTransitioning = false;
      el.dispatchEvent(new CustomEvent('shown' + EVENT_KEY, { bubbles: true }));
      const focusEl = el.querySelector('[autofocus]') ||
                      el.querySelector('input, textarea, select, button:not([data-tw-dismiss])');
      focusEl?.focus();
    }, 300);
  };

  TwModal.prototype.hide = function () {
    if (!this._isShown || this._isTransitioning) return;
    const el = this._element;
    const hideEvent = new CustomEvent('hide' + EVENT_KEY, { bubbles: true, cancelable: true });
    el.dispatchEvent(hideEvent);
    if (hideEvent.defaultPrevented) return;

    this._isTransitioning = true;
    el.classList.remove('tw-show');
    el.setAttribute('aria-hidden', 'true');
    if (this._backdrop) this._backdrop.classList.remove('tw-show');

    setTimeout(() => {
      document.body.classList.remove('tw-modal-open');
      if (this._backdrop) {
        this._backdrop.remove();
        this._backdrop = null;
      }
      this._isShown = false;
      this._isTransitioning = false;
      el.dispatchEvent(new CustomEvent('hidden' + EVENT_KEY, { bubbles: true }));
    }, 300);
  };

  TwModal.prototype._createBackdrop = function () {
    const backdrop = document.createElement('div');
    backdrop.className = 'tw-modal-backdrop';
    document.body.appendChild(backdrop);
    return backdrop;
  };

  function getModalTarget(trigger) {
    const target = trigger.getAttribute('data-tw-target') || trigger.getAttribute('href');
    return target ? document.querySelector(target) : null;
  }

  document.addEventListener('click', function (e) {
    const trigger = e.target.closest('[data-tw-toggle="modal"]');
    if (trigger) {
      e.preventDefault();
      const modal = getModalTarget(trigger);
      if (modal) TwModal.show(modal);
      return;
    }

    const dismiss = e.target.closest('[data-tw-dismiss="modal"]');
    if (dismiss) {
      const modal = dismiss.closest('.tw-modal');
      if (modal) TwModal.hide(modal);
      return;
    }

    const modal = e.target.closest('.tw-modal');
    if (modal && e.target === modal) {
      TwModal.hide(modal);
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      const open = document.querySelector('.tw-modal.tw-show');
      if (open) TwModal.hide(open);
    }
  });

  window.TwModal = TwModal;
})();
