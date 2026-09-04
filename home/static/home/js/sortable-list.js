(function () {
  'use strict';

  var CSRF = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';

  // options: { reorderUrl, handle (CSS selector), onSaved, onError, msg: { reorder_error, network_error } }
  window.initSortableList = function (listEl, options) {
    if (!listEl || typeof Sortable === 'undefined') return;

    var opts = options || {};

    return Sortable.create(listEl, {
      handle: opts.handle || undefined,
      animation: 150,
      ghostClass: 'sortable-ghost',
      chosenClass: 'sortable-chosen',
      onEnd: function () {
        var items = Array.from(listEl.children).map(function (li, idx) {
          return { id: parseInt(li.dataset.id, 10), order: idx };
        });
        fetch(opts.reorderUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': CSRF,
          },
          body: JSON.stringify(items),
        })
          .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
          .then(function (res) {
            if (!res.ok) {
              if (opts.onError) opts.onError(res.data.error || (opts.msg && opts.msg.reorder_error) || 'Reorder failed.');
            } else {
              if (opts.onSaved) opts.onSaved();
            }
          })
          .catch(function () {
            if (opts.onError) opts.onError((opts.msg && opts.msg.network_error) || 'Network error.');
          });
      },
    });
  };

  // options: { storageKey, filter, onSave }
  window.initSortableGrid = function (gridEl, options) {
    if (!gridEl || typeof Sortable === 'undefined') return;

    var opts = options || {};
    var storageKey = opts.storageKey || 'sortableGrid';
    var saved = null;
    try {
      saved = JSON.parse(localStorage.getItem(storageKey));
    } catch (_) {}

    if (saved && Array.isArray(saved)) {
      var tiles = Array.from(gridEl.children);
      tiles.sort(function (a, b) {
        var ai = saved.indexOf(a.dataset.tileId);
        var bi = saved.indexOf(b.dataset.tileId);
        if (ai === -1) ai = Infinity;
        if (bi === -1) bi = Infinity;
        return ai - bi;
      });
      tiles.forEach(function (tile) {
        gridEl.appendChild(tile);
      });
    }

    // Add a dedicated drag handle to each tile so it doesn't conflict with links
    Array.from(gridEl.children).forEach(function (tile) {
      if (tile.querySelector('.drag-handle')) return;
      var handle = document.createElement('i');
      handle.className = 'fas fa-grip-vertical drag-handle';
      handle.setAttribute('aria-hidden', 'true');
      var header = tile.querySelector('.dashboard-tile-header');
      (header || tile).appendChild(handle);
    });

    return Sortable.create(gridEl, {
      animation: 150,
      handle: '.drag-handle',
      delay: 0,
      forceFallback: true,
      fallbackClass: 'sortable-fallback',
      ghostClass: 'sortable-ghost',
      chosenClass: 'sortable-chosen',
      dragClass: 'sortable-drag',
      filter: opts.filter || 'button, input, select, textarea, .btn, .cal-nav, .chat-unread-btn',
      preventOnFilter: false,
      onEnd: function () {
        var order = Array.from(gridEl.children).map(function (tile) {
          return tile.dataset.tileId;
        });
        try {
          localStorage.setItem(storageKey, JSON.stringify(order));
        } catch (_) {}
        if (opts.onSave) opts.onSave(order);
      },
    });
  };
}());
