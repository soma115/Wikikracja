/**
 * Lightweight project-owned Tailwind popover component.
 */
(function () {
  'use strict';

  const EVENT_KEY = '.tw.popover';
  let _counter = 0;

  function TwPopover(element, options) {
    this._element = element;
    this._popper = null;
    this._shown = false;
    this._config = Object.assign({
      trigger: 'click',
      placement: 'right',
      html: false,
      title: '',
      content: '',
      customClass: '',
      sanitize: true
    }, options || {});
    this._parseDataAttributes();
    this._bindEvents();
    element._twPopover = this;
  }

  TwPopover.getInstance = function (element) {
    return element ? element._twPopover : null;
  };

  TwPopover.getOrCreateInstance = function (element, options) {
    if (!element) return null;
    let instance = TwPopover.getInstance(element);
    if (!instance) {
      instance = new TwPopover(element, options || {});
      element._twPopover = instance;
    }
    return instance;
  };

  TwPopover.prototype._parseDataAttributes = function () {
    const el = this._element;
    const ds = el.dataset;
    if (ds.twTrigger) this._config.trigger = ds.twTrigger;
    if (ds.twPlacement) this._config.placement = ds.twPlacement;
    if (ds.twHtml) this._config.html = ds.twHtml === 'true';
    if (ds.twTitle) this._config.title = ds.twTitle;
    if (ds.twContent) this._config.content = ds.twContent;
    if (ds.twCustomClass) this._config.customClass = ds.twCustomClass;
  };

  TwPopover.prototype._bindEvents = function () {
    const el = this._element;
    const trigger = this._config.trigger;
    const self = this;

    this._clickHandler = function (e) {
      e.preventDefault();
      e.stopPropagation();
      self.toggle();
    };
    this._enterHandler = function () { self.show(); };
    this._leaveHandler = function () { self.hide(); };
    this._focusHandler = function () { self.show(); };
    this._blurHandler = function () { self.hide(); };

    if (trigger.indexOf('click') !== -1) {
      el.addEventListener('click', this._clickHandler);
    }
    if (trigger.indexOf('hover') !== -1) {
      el.addEventListener('mouseenter', this._enterHandler);
      el.addEventListener('mouseleave', this._leaveHandler);
    }
    if (trigger.indexOf('focus') !== -1) {
      el.addEventListener('focus', this._focusHandler);
      el.addEventListener('blur', this._blurHandler);
    }
  };

  TwPopover.prototype._unbindEvents = function () {
    const el = this._element;
    el.removeEventListener('click', this._clickHandler);
    el.removeEventListener('mouseenter', this._enterHandler);
    el.removeEventListener('mouseleave', this._leaveHandler);
    el.removeEventListener('focus', this._focusHandler);
    el.removeEventListener('blur', this._blurHandler);
  };

  TwPopover.prototype._createPopover = function () {
    const popover = document.createElement('div');
    popover.className = 'tw-popover' + (this._config.customClass ? ' ' + this._config.customClass : '');
    popover.setAttribute('role', 'tooltip');
    _counter += 1;
    const id = 'tw-popover-' + _counter;
    popover.id = id;

    const arrow = document.createElement('div');
    arrow.className = 'tw-popover-arrow';

    const header = document.createElement('div');
    header.className = 'tw-popover-header';

    const body = document.createElement('div');
    body.className = 'tw-popover-body';

    popover.appendChild(arrow);
    popover.appendChild(header);
    popover.appendChild(body);
    document.body.appendChild(popover);
    return popover;
  };

  TwPopover.prototype._renderContent = function () {
    const popover = this._popper;
    if (!popover) return;

    const title = this._getTitle();
    const header = popover.querySelector('.tw-popover-header');
    if (title) {
      header.textContent = this._config.html ? this._sanitize(title) : title;
      header.classList.remove('tw-d-none');
    } else {
      header.classList.add('tw-d-none');
    }

    const body = popover.querySelector('.tw-popover-body');
    const content = this._config.content || '';
    body.innerHTML = this._config.html ? this._sanitize(content) : this._escapeHtml(content);
  };

  TwPopover.prototype._getTitle = function () {
    return this._element.dataset.twTitle || this._config.title || '';
  };

  TwPopover.prototype._getContent = function () {
    return this._element.dataset.twContent || this._config.content || '';
  };

  TwPopover.prototype._escapeHtml = function (text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  };

  TwPopover.prototype._sanitize = function (html) {
    if (!this._config.sanitize) return html;
    if (typeof DOMPurify !== 'undefined') return DOMPurify.sanitize(html);
    const div = document.createElement('div');
    div.textContent = html;
    return div.innerHTML;
  };

  TwPopover.prototype._position = function () {
    const popover = this._popper;
    const el = this._element;
    const rect = el.getBoundingClientRect();
    const popRect = popover.getBoundingClientRect();
    const margin = 8;
    const placement = this._config.placement;
    const scrollX = window.scrollX || window.pageXOffset;
    const scrollY = window.scrollY || window.pageYOffset;
    let top = 0;
    let left = 0;

    if (placement === 'top') {
      top = rect.top + scrollY - popRect.height - margin;
      left = rect.left + scrollX + (rect.width - popRect.width) / 2;
    } else if (placement === 'bottom') {
      top = rect.bottom + scrollY + margin;
      left = rect.left + scrollX + (rect.width - popRect.width) / 2;
    } else if (placement === 'left') {
      top = rect.top + scrollY + (rect.height - popRect.height) / 2;
      left = rect.left + scrollX - popRect.width - margin;
    } else if (placement === 'right') {
      top = rect.top + scrollY + (rect.height - popRect.height) / 2;
      left = rect.right + scrollX + margin;
    }

    const pad = 4;
    if (left < pad) left = pad;
    if (left + popRect.width > window.innerWidth - pad) {
      left = window.innerWidth - popRect.width - pad;
    }
    if (top < scrollY + pad) top = scrollY + pad;
    if (top + popRect.height > scrollY + window.innerHeight - pad) {
      top = scrollY + window.innerHeight - popRect.height - pad;
    }

    popover.style.top = top + 'px';
    popover.style.left = left + 'px';
    popover.dataset.twPlacement = placement;
  };

  TwPopover.prototype.show = function () {
    if (this._shown) return;
    const el = this._element;

    const showEvent = new CustomEvent('show' + EVENT_KEY, { bubbles: true, cancelable: true });
    el.dispatchEvent(showEvent);
    if (showEvent.defaultPrevented) return;

    this._popper = this._createPopover();
    this._renderContent();
    this._popper.classList.add('tw-show');
    this._position();
    this._shown = true;
    el.setAttribute('aria-describedby', this._popper.id);
    el.dispatchEvent(new CustomEvent('shown' + EVENT_KEY, { bubbles: true }));
  };

  TwPopover.prototype.hide = function () {
    if (!this._shown || !this._popper) return;
    const el = this._element;

    const hideEvent = new CustomEvent('hide' + EVENT_KEY, { bubbles: true, cancelable: true });
    el.dispatchEvent(hideEvent);
    if (hideEvent.defaultPrevented) return;

    this._popper.classList.remove('tw-show');
    this._popper.remove();
    this._popper = null;
    this._shown = false;
    el.removeAttribute('aria-describedby');
    el.dispatchEvent(new CustomEvent('hidden' + EVENT_KEY, { bubbles: true }));
  };

  TwPopover.prototype.toggle = function () {
    if (this._shown) this.hide(); else this.show();
  };

  TwPopover.prototype.setContent = function (content) {
    if (typeof content === 'string') {
      this._config.content = content;
    } else if (content && typeof content === 'object') {
      const key = Object.keys(content)[0];
      let body = content[key];
      if (key === '.popover-body' || key === '.tw-popover-body') {
        this._config.content = body;
      } else if (key === '.popover-header' || key === '.tw-popover-header') {
        this._config.title = body;
      }
    }
    if (this._popper) this._renderContent();
  };

  TwPopover.prototype.dispose = function () {
    this._unbindEvents();
    this.hide();
    if (this._element) {
      this._element._twPopover = null;
    }
  };

  document.addEventListener('click', function (e) {
    document.querySelectorAll('.tw-popover').forEach(function (pop) {
      const triggerId = pop.id;
      const trigger = document.querySelector('[aria-describedby="' + triggerId + '"]');
      if (!trigger) return;
      const instance = TwPopover.getInstance(trigger);
      if (!instance) return;
      if (instance._config.trigger.indexOf('manual') === -1) return;
      if (pop.contains(e.target) || trigger.contains(e.target)) return;
      instance.hide();
    });
  });

  window.TwPopover = TwPopover;
})();
