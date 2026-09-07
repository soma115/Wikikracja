/**
 * Lightweight project-owned Tailwind dropdown component.
 */
(function () {
  'use strict';

  function TwDropdown(toggle, options) {
    this._toggle = toggle;
    this._options = Object.assign({ fixed: false }, options || {});
    this._menu = this._getMenu();
    this._isShown = false;
  }

  TwDropdown.getInstance = function (toggle) {
    return toggle ? toggle._twDropdown : null;
  };

  TwDropdown.getOrCreateInstance = function (toggle, options) {
    if (!toggle) return null;
    let instance = TwDropdown.getInstance(toggle);
    if (!instance) {
      instance = new TwDropdown(toggle, options);
      toggle._twDropdown = instance;
    }
    return instance;
  };

  TwDropdown.prototype._getMenu = function () {
    const target = this._toggle.getAttribute('data-tw-target');
    if (target) return document.querySelector(target);
    const parent = this._toggle.closest('.tw-dropdown');
    return parent ? parent.querySelector('.tw-dropdown-menu') : this._toggle.nextElementSibling;
  };

  TwDropdown.prototype.show = function () {
    if (this._isShown || !this._menu) return;
    this._isShown = true;
    this._menu.classList.add('tw-show');
    this._toggle.setAttribute('aria-expanded', 'true');
    this._position();
  };

  TwDropdown.prototype.hide = function () {
    if (!this._isShown || !this._menu) return;
    this._isShown = false;
    this._menu.classList.remove('tw-show');
    this._toggle.setAttribute('aria-expanded', 'false');
    this._resetPosition();
  };

  TwDropdown.prototype.toggle = function () {
    if (this._isShown) this.hide(); else this.show();
  };

  TwDropdown.prototype._position = function () {
    if (this._options.fixed) {
      this._menu.style.position = 'fixed';
      const rect = this._toggle.getBoundingClientRect();
      if (this._menu.classList.contains('tw-dropdown-menu-end')) {
        this._menu.style.left = 'auto';
        this._menu.style.right = (window.innerWidth - rect.right) + 'px';
      } else {
        this._menu.style.right = 'auto';
        this._menu.style.left = rect.left + 'px';
      }
      this._menu.style.top = rect.bottom + 'px';
    }
  };

  TwDropdown.prototype._resetPosition = function () {
    this._menu.style.position = '';
    this._menu.style.top = '';
    this._menu.style.left = '';
    this._menu.style.right = '';
  };

  let openDropdown = null;

  function closeOpenDropdown() {
    if (openDropdown) {
      openDropdown.hide();
      openDropdown = null;
    }
  }

  document.addEventListener('click', function (e) {
    const item = e.target.closest('.tw-dropdown-item');
    if (item && !item.hasAttribute('data-tw-toggle')) {
      closeOpenDropdown();
    }

    const toggle = e.target.closest('[data-tw-toggle="dropdown"]');
    if (toggle) {
      e.preventDefault();
      e.stopPropagation();
      const options = { fixed: toggle.hasAttribute('data-tw-dropdown-fixed') };
      const instance = TwDropdown.getOrCreateInstance(toggle, options);
      if (!instance) return;

      if (openDropdown && openDropdown !== instance) closeOpenDropdown();
      instance.toggle();
      openDropdown = instance._isShown ? instance : null;
      return;
    }

    if (openDropdown && openDropdown._menu && openDropdown._menu.contains(e.target)) return;
    closeOpenDropdown();
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeOpenDropdown();
  });

  TwDropdown.closeAll = closeOpenDropdown;

  window.TwDropdown = TwDropdown;
})();
