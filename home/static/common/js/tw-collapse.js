/**
 * Lightweight project-owned Tailwind collapse component.
 */
(function () {
  'use strict';

  function TwCollapse(element) {
    this._element = element;
  }

  TwCollapse.getInstance = function (element) {
    return element ? element._twCollapse : null;
  };

  TwCollapse.getOrCreateInstance = function (element) {
    if (!element) return null;
    let instance = TwCollapse.getInstance(element);
    if (!instance) {
      instance = new TwCollapse(element);
      element._twCollapse = instance;
    }
    return instance;
  };

  TwCollapse.prototype._setExpanded = function (expanded) {
    const id = this._element.id;
    if (!id) return;
    document.querySelectorAll('[data-tw-toggle="collapse"]').forEach(function (trigger) {
      const target = trigger.getAttribute('data-tw-target') || trigger.getAttribute('href');
      if (target === '#' + id) {
        trigger.setAttribute('aria-controls', id);
        trigger.setAttribute('aria-expanded', String(expanded));
        trigger.classList.toggle('tw-collapsed', !expanded);
      }
    });
  };

  TwCollapse.prototype.show = function () {
    const parentSelector = this._element.getAttribute('data-tw-parent');
    const parent = parentSelector ? document.querySelector(parentSelector) : null;
    if (parent) {
      parent.querySelectorAll('.tw-collapse.tw-show').forEach((element) => {
        if (element !== this._element) TwCollapse.getOrCreateInstance(element).hide();
      });
    }
    this._element.classList.add('tw-show');
    this._setExpanded(true);
  };

  TwCollapse.prototype.hide = function () {
    this._element.classList.remove('tw-show');
    this._setExpanded(false);
  };

  TwCollapse.prototype.toggle = function () {
    if (this._element.classList.contains('tw-show')) this.hide(); else this.show();
  };

  function getCollapseTarget(trigger) {
    const target = trigger.getAttribute('data-tw-target') || trigger.getAttribute('href');
    return target ? document.querySelector(target) : null;
  }

  function initAll() {
    document.querySelectorAll('[data-tw-toggle="collapse"]').forEach(function (trigger) {
      const element = getCollapseTarget(trigger);
      if (!element) return;
      TwCollapse.getOrCreateInstance(element)._setExpanded(element.classList.contains('tw-show'));
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }

  document.addEventListener('click', function (e) {
    const trigger = e.target.closest('[data-tw-toggle="collapse"]');
    if (!trigger) return;
    e.preventDefault();
    const el = getCollapseTarget(trigger);
    if (el) TwCollapse.getOrCreateInstance(el).toggle();
  });

  window.TwCollapse = TwCollapse;
})();
