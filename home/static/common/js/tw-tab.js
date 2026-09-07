/**
 * Lightweight project-owned Tailwind tab component.
 */
(function () {
  'use strict';

  const EVENT_KEY = '.tw.tab';

  function TwTab(element) {
    this._element = element;
    element._twTab = this;
  }

  TwTab.getInstance = function (element) {
    return element ? element._twTab : null;
  };

  TwTab.getOrCreateInstance = function (element) {
    if (!element) return null;
    let instance = TwTab.getInstance(element);
    if (!instance) {
      instance = new TwTab(element);
      element._twTab = instance;
    }
    return instance;
  };

  function getTargetId(trigger) {
    return trigger.getAttribute('data-tw-target') || trigger.getAttribute('href');
  }

  function getPanel(trigger) {
    const target = getTargetId(trigger);
    return target ? document.querySelector(target) : null;
  }

  TwTab.prototype.show = function () {
    const trigger = this._element;
    const target = getTargetId(trigger);
    if (!target) return;

    const showEvent = new CustomEvent('show' + EVENT_KEY, { bubbles: true, cancelable: true });
    trigger.dispatchEvent(showEvent);
    if (showEvent.defaultPrevented) return;

    const list = trigger.closest('.tw-nav-tabs, [role="tablist"]') || trigger.parentElement;
    if (list) {
      list.querySelectorAll('[data-tw-toggle="tab"]').forEach(function (t) {
        t.classList.remove('tw-active');
        t.setAttribute('aria-selected', 'false');
        const panel = getPanel(t);
        if (panel) {
          panel.classList.remove('tw-show', 'tw-active');
          panel.setAttribute('aria-hidden', 'true');
        }
      });
    }

    trigger.classList.add('tw-active');
    trigger.setAttribute('aria-selected', 'true');
    const panel = document.querySelector(target);
    if (panel) {
      panel.classList.add('tw-show', 'tw-active');
      panel.setAttribute('aria-hidden', 'false');
    }

    trigger.dispatchEvent(new CustomEvent('shown' + EVENT_KEY, { bubbles: true }));
  };

  function getTabTarget(trigger) {
    return trigger.getAttribute('data-tw-target') || trigger.getAttribute('href');
  }

  function initAll() {
    document.querySelectorAll('.tw-nav-tabs').forEach(function (list) {
      list.setAttribute('role', 'tablist');
      list.querySelectorAll('[data-tw-toggle="tab"]').forEach(function (trigger) {
        const panel = getPanel(trigger);
        const active = trigger.classList.contains('tw-active');
        trigger.setAttribute('role', 'tab');
        trigger.setAttribute('aria-selected', String(active));
        if (!panel) return;
        if (!trigger.id) trigger.id = panel.id + '-tab';
        trigger.setAttribute('aria-controls', panel.id);
        panel.setAttribute('role', 'tabpanel');
        panel.setAttribute('aria-labelledby', trigger.id);
        panel.setAttribute('aria-hidden', String(!active));
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }

  document.addEventListener('click', function (e) {
    const trigger = e.target.closest('[data-tw-toggle="tab"]');
    if (!trigger) return;
    e.preventDefault();
    TwTab.getOrCreateInstance(trigger).show();
  });

  window.TwTab = TwTab;
})();
