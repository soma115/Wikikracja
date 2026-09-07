(function () {
  'use strict';

  var CSRF = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';

  function apiFetch(url, method, body) {
    var opts = { method: method, headers: { 'X-CSRFToken': CSRF } };
    if (body) {
      opts.headers['Content-Type'] = 'application/x-www-form-urlencoded';
      opts.body = new URLSearchParams(body).toString();
    }
    return fetch(url, opts).then(function (r) {
      return r.json().then(function (d) { return { ok: r.ok, data: d }; });
    });
  }

  function buildUrl(tpl, pk) {
    return tpl.replace('{pk}', pk);
  }

  window.initCategoryManager = function (modalId, urls, msg) {
    var modalEl = document.getElementById(modalId);
    if (!modalEl) return;

    var list    = modalEl.querySelector('#catMgrList');
    var errEl   = modalEl.querySelector('#catMgrError');
    var addBtn  = modalEl.querySelector('#catMgrAddBtn');
    var newName = modalEl.querySelector('#catMgrNewName');
    var newDesc = modalEl.querySelector('#catMgrNewDesc');
    var sortable = null;

    function showError(m) {
      errEl.textContent = m;
      errEl.style.display = m ? '' : 'none';
    }

    function renderRow(cat) {
      var li = document.createElement('li');
      li.className = 'cat-mgr-row';
      li.dataset.id = cat.id;

      if (urls.reorder) {
        var grip = document.createElement('span');
        grip.className = 'cat-mgr-handle';
        grip.innerHTML = '<i class="fas fa-grip-vertical"></i>';
        li.appendChild(grip);
      }

      var info = document.createElement('div');
      info.className = 'cat-mgr-info';
      var nameEl = document.createElement('div');
      nameEl.className = 'cat-mgr-name';
      nameEl.textContent = cat.name;
      var descEl = document.createElement('div');
      descEl.className = 'cat-mgr-desc';
      descEl.textContent = cat.description || '';
      info.appendChild(nameEl);
      info.appendChild(descEl);

      var badge = document.createElement('span');
      badge.className = 'cat-mgr-badge';
      badge.textContent = (cat.item_count || 0) + ' ' + msg.items_suffix;

      var actions = document.createElement('div');
      actions.className = 'cat-mgr-actions';

      if (!cat.is_protected) {
        var editBtn = document.createElement('button');
        editBtn.type = 'button';
        editBtn.className = 'cat-mgr-btn';
        editBtn.title = msg.edit;
        editBtn.innerHTML = '<i class="fas fa-pencil"></i>';
        editBtn.addEventListener('click', function () { startEdit(li, cat); });

        var delBtn = document.createElement('button');
        delBtn.type = 'button';
        delBtn.className = 'cat-mgr-btn cat-mgr-btn--delete';
        delBtn.title = msg.delete;
        delBtn.innerHTML = '<i class="fas fa-trash"></i>';
        delBtn.addEventListener('click', function () { deleteCategory(cat, li); });

        actions.appendChild(editBtn);
        actions.appendChild(delBtn);
      } else {
        var prot = document.createElement('span');
        prot.className = 'cat-mgr-protected';
        prot.title = msg.protected;
        prot.innerHTML = '<i class="fas fa-lock"></i>';
        actions.appendChild(prot);
      }

      li.appendChild(info);
      li.appendChild(badge);
      li.appendChild(actions);
      return li;
    }

    function startEdit(li, cat) {
      li.classList.add('cat-mgr-row--editing');
      li.innerHTML = '';
      var fields = document.createElement('div');
      fields.className = 'cat-mgr-edit-fields';

      var ni = document.createElement('input');
      ni.type = 'text'; ni.className = 'cat-mgr-input'; ni.value = cat.name; ni.maxLength = 100;
      var di = document.createElement('input');
      di.type = 'text'; di.className = 'cat-mgr-input'; di.value = cat.description || '';

      var btns = document.createElement('div');
      btns.className = 'cat-mgr-edit-btns';

      var saveB = document.createElement('button');
      saveB.type = 'button'; saveB.className = 'cat-mgr-btn cat-mgr-btn--save';
      saveB.title = msg.save; saveB.innerHTML = '<i class="fas fa-check"></i>';
      saveB.addEventListener('click', function () {
        var name = ni.value.trim();
        if (!name) { showError(msg.name_req); return; }
        apiFetch(buildUrl(urls.edit, cat.id), 'POST', { name: name, description: di.value.trim() })
          .then(function (res) {
            if (!res.ok) { showError(res.data.error || msg.error || 'Error'); return; }
            showError('');
            cat.name = res.data.name;
            cat.description = res.data.description;
            li.replaceWith(renderRow(cat));
          });
      });

      var cancelB = document.createElement('button');
      cancelB.type = 'button'; cancelB.className = 'cat-mgr-btn';
      cancelB.title = msg.cancel; cancelB.innerHTML = '<i class="fas fa-xmark"></i>';
      cancelB.addEventListener('click', function () {
        li.replaceWith(renderRow(cat));
      });

      btns.appendChild(saveB); btns.appendChild(cancelB);
      fields.appendChild(ni); fields.appendChild(di); fields.appendChild(btns);
      li.appendChild(fields);
      ni.focus();
    }

    function performDelete(cat, li) {
      apiFetch(buildUrl(urls.del, cat.id), 'POST', {})
        .then(function (res) {
          if (!res.ok) { showError(res.data.error || msg.error || 'Error'); return; }
          showError('');
          li.remove();
        });
    }

    function deleteCategory(cat, li) {
      var count = cat.item_count || 0;
      // When the host page provides an items endpoint, list the affected titles in the
      // confirm so the user sees exactly which documents will become uncategorized.
      if (urls.items && count > 0) {
        apiFetch(buildUrl(urls.items, cat.id), 'GET')
          .then(function (res) {
            if (!res.ok) { showError(res.data.error || msg.error || 'Error'); return; }
            var items = res.data.items || [];
            var body = msg.confirm_del.replace('{n}', res.data.count);
            // Guard against a lone "• " when the items list went empty between load and click.
            if (items.length) {
              body += '\n\n• ' + items.join('\n• ');
              if (res.data.count > items.length) {
                body += '\n' + msg.and_more.replace('{n}', res.data.count - items.length);
              }
            }
            if (confirm(body)) performDelete(cat, li);
          });
        return;
      }
      if (!confirm(msg.confirm_del.replace('{n}', count))) return;
      performDelete(cat, li);
    }

    function loadCategories() {
      apiFetch(urls.list, 'GET')
        .then(function (res) {
          if (!res.ok) { showError(msg.load_error || 'Failed to load.'); return; }
          list.innerHTML = '';
          res.data.categories.forEach(function (cat) {
            list.appendChild(renderRow(cat));
          });
        });
    }

    if (addBtn) {
      addBtn.addEventListener('click', function () {
        var name = newName.value.trim();
        if (!name) { showError(msg.name_req); return; }
        apiFetch(urls.list, 'POST', { name: name, description: newDesc.value.trim() })
          .then(function (res) {
            if (!res.ok) { showError(res.data.error || msg.error || 'Error'); return; }
            showError('');
            newName.value = ''; newDesc.value = '';
            res.data.item_count = 0;
            list.appendChild(renderRow(res.data));
          });
      });
    }

    modalEl.addEventListener('show.tw.modal', function () {
      loadCategories();
      if (urls.reorder && typeof initSortableList !== 'undefined') {
        if (sortable) { sortable.destroy(); sortable = null; }
        sortable = initSortableList(list, {
          handle: '.cat-mgr-handle',
          reorderUrl: urls.reorder,
          onError: function (m) { showError(m); },
        });
      }
    });
    modalEl.addEventListener('hidden.tw.modal', function () {
      showError('');
      window.location.reload();
    });
  };
}());
