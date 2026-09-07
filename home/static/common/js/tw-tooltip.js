/**
 * Lightweight project-owned Tailwind tooltip component.
 */
(function () {
  'use strict';

  const EVENT_KEY = '.tw.tooltip';

  function TwTooltip(element, options) {
    this._element = element;
    this._tip = null;
    this._shown = false;
    this._title = element.getAttribute('title') || element.dataset.twTitle || '';
    if (element.hasAttribute('title')) element.removeAttribute('title');
    this._enterHandler = this.show.bind(this);
    this._leaveHandler = this.hide.bind(this);
    this._focusHandler = this.show.bind(this);
    this._blurHandler = this.hide.bind(this);
    this._config = Object.assign({ placement: 'top', trigger: 'hover focus' }, options || {});
    this._parseDataAttributes();
    this._bindEvents();
    element._twTooltip = this;
  }

  TwTooltip.getInstance = function (element) {
    return element ? element._twTooltip : null;
  };

  TwTooltip.getOrCreateInstance = function (element, options) {
    if (!element) return null;
    let instance = TwTooltip.getInstance(element);
    if (!instance) {
      instance = new TwTooltip(element, options);
      element._twTooltip = instance;
    }
    return instance;
  };

  TwTooltip.prototype._parseDataAttributes = function () {
    const el = this._element;
    if (el.dataset.twPlacement) this._config.placement = el.dataset.twPlacement;
    if (el.dataset.twTrigger) this._config.trigger = el.dataset.twTrigger;
  };

  TwTooltip.prototype._bindEvents = function () {
    const el = this._element;
    const trigger = this._config.trigger;
    if (trigger.indexOf('hover') !== -1) {
      el.addEventListener('mouseenter', this._enterHandler);
      el.addEventListener('mouseleave', this._leaveHandler);
    }
    if (trigger.indexOf('focus') !== -1) {
      el.addEventListener('focus', this._focusHandler);
      el.addEventListener('blur', this._blurHandler);
    }
  };

  TwTooltip.prototype._unbindEvents = function () {
    const el = this._element;
    el.removeEventListener('mouseenter', this._enterHandler);
    el.removeEventListener('mouseleave', this._leaveHandler);
    el.removeEventListener('focus', this._focusHandler);
    el.removeEventListener('blur', this._blurHandler);
  };

  TwTooltip.prototype._getTitle = function () {
    return this._element.dataset.twTitle || this._title;
  };

  TwTooltip.prototype._createTip = function () {
    const tip = document.createElement('div');
    tip.className = 'tw-tooltip';
    tip.setAttribute('role', 'tooltip');
    const arrow = document.createElement('div');
    arrow.className = 'tw-tooltip-arrow';
    const inner = document.createElement('div');
    inner.className = 'tw-tooltip-inner';
    tip.appendChild(arrow);
    tip.appendChild(inner);
    document.body.appendChild(tip);
    return tip;
  };

  TwTooltip.prototype._position = function () {
    const tip = this._tip;
    const el = this._element;
    const rect = el.getBoundingClientRect();
    const tipRect = tip.getBoundingClientRect();
    const margin = 8;
    const placement = this._config.placement;
    const scrollX = window.scrollX || window.pageXOffset;
    const scrollY = window.scrollY || window.pageYOffset;
    let top = 0;
    let left = 0;

    if (placement === 'top') {
      top = rect.top + scrollY - tipRect.height - margin;
      left = rect.left + scrollX + (rect.width - tipRect.width) / 2;
    } else if (placement === 'bottom') {
      top = rect.bottom + scrollY + margin;
      left = rect.left + scrollX + (rect.width - tipRect.width) / 2;
    } else if (placement === 'left') {
      top = rect.top + scrollY + (rect.height - tipRect.height) / 2;
      left = rect.left + scrollX - tipRect.width - margin;
    } else if (placement === 'right') {
      top = rect.top + scrollY + (rect.height - tipRect.height) / 2;
      left = rect.right + scrollX + margin;
    }

    // keep inside viewport
    const pad = 4;
    if (left < pad) left = pad;
    if (left + tipRect.width > window.innerWidth - pad) {
      left = window.innerWidth - tipRect.width - pad;
    }
    if (top < scrollY + pad) top = scrollY + pad;
    if (top + tipRect.height > scrollY + window.innerHeight - pad) {
      top = scrollY + window.innerHeight - tipRect.height - pad;
    }

    tip.style.top = top + 'px';
    tip.style.left = left + 'px';
    tip.dataset.twPlacement = placement;
  };

  TwTooltip.prototype.show = function () {
    if (this._shown) return;
    const el = this._element;
    const title = this._getTitle();
    if (!title) return;

    const showEvent = new CustomEvent('show' + EVENT_KEY, { bubbles: true, cancelable: true });
    el.dispatchEvent(showEvent);
    if (showEvent.defaultPrevented) return;

    this._tip = this._createTip();
    this._tip.querySelector('.tw-tooltip-inner').textContent = title;
    this._tip.classList.add('tw-show');
    this._position();
    this._shown = true;
    el.setAttribute('aria-describedby', this._tip.id || (this._tip.id = 'tw-tooltip-' + Math.random().toString(36).slice(2)));
    el.dispatchEvent(new CustomEvent('shown' + EVENT_KEY, { bubbles: true }));
  };

  TwTooltip.prototype.hide = function () {
    if (!this._shown || !this._tip) return;
    const el = this._element;
    const hideEvent = new CustomEvent('hide' + EVENT_KEY, { bubbles: true, cancelable: true });
    el.dispatchEvent(hideEvent);
    if (hideEvent.defaultPrevented) return;

    this._tip.classList.remove('tw-show');
    this._tip.remove();
    this._tip = null;
    this._shown = false;
    el.removeAttribute('aria-describedby');
    el.dispatchEvent(new CustomEvent('hidden' + EVENT_KEY, { bubbles: true }));
  };

  TwTooltip.prototype.dispose = function () {
    this._unbindEvents();
    this.hide();
    if (this._element) {
      if (this._title && !this._element.hasAttribute('title')) this._element.setAttribute('title', this._title);
      this._element._twTooltip = null;
    }
  };

  // Global auto-init
  function initAll() {
    document.querySelectorAll('[data-tw-toggle="tooltip"]').forEach(function (el) {
      TwTooltip.getOrCreateInstance(el);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }

  window.TwTooltip = TwTooltip;
})();
