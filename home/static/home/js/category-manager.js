(function () {
  'use strict';

  function apiFetch(url, method, body) {
    return window.apiFetch(url, {
      method: method,
      body: body ? new URLSearchParams(body) : undefined,
    }).then(function (r) {
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
      errEl.classList.toggle('tw-d-none', !m);
    }

    function setBusy(elements, busy) {
      modalEl.setAttribute('aria-busy', busy ? 'true' : 'false');
      (elements || []).forEach(function (element) {
        if (!element) return;
        element.disabled = busy;
        element.setAttribute('aria-disabled', busy ? 'true' : 'false');
      });
    }

    function request(promise, elements, onSuccess) {
      setBusy(elements, true);
      return promise
        .then(function (res) {
          if (!res.ok) {
            showError(res.data.error || msg.error || 'Error');
            return;
          }
          onSuccess(res.data);
        })
        .catch(function () { showError(msg.error || 'Error'); })
        .finally(function () { setBusy(elements, false); });
    }

    function renderRow(cat) {
      var li = document.createElement('li');
      li.className = 'tw-cat-mgr-row';
      li.dataset.id = cat.id;

      if (urls.reorder) {
        var grip = document.createElement('span');
        grip.className = 'tw-cat-mgr-handle';
        grip.innerHTML = '<i class="fas fa-grip-vertical"></i>';
        li.appendChild(grip);
      }

      var info = document.createElement('div');
      info.className = 'tw-cat-mgr-info';
      var nameEl = document.createElement('div');
      nameEl.className = 'tw-cat-mgr-name';
      nameEl.textContent = cat.name;
      var descEl = document.createElement('div');
      descEl.className = 'tw-cat-mgr-desc';
      descEl.textContent = cat.description || '';
      info.appendChild(nameEl);
      info.appendChild(descEl);

      var badge = document.createElement('span');
      badge.className = 'tw-cat-mgr-badge';
      badge.textContent = (cat.item_count || 0) + ' ' + msg.items_suffix;

      var actions = document.createElement('div');
      actions.className = 'tw-cat-mgr-actions';

      if (!cat.is_protected) {
        var editBtn = document.createElement('button');
        editBtn.type = 'button';
        editBtn.className = 'tw-cat-mgr-btn';
        editBtn.title = msg.edit;
        editBtn.setAttribute('aria-label', msg.edit);
        editBtn.innerHTML = '<i class="fas fa-pencil"></i>';
        editBtn.addEventListener('click', function () { startEdit(li, cat); });

        var delBtn = document.createElement('button');
        delBtn.type = 'button';
        delBtn.className = 'tw-cat-mgr-btn tw-cat-mgr-btn--delete';
        delBtn.title = msg.delete;
        delBtn.setAttribute('aria-label', msg.delete);
        delBtn.innerHTML = '<i class="fas fa-trash"></i>';
        delBtn.addEventListener('click', function () { deleteCategory(cat, li); });

        actions.appendChild(editBtn);
        actions.appendChild(delBtn);
      } else {
        var prot = document.createElement('span');
        prot.className = 'tw-cat-mgr-protected';
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
      li.classList.add('tw-cat-mgr-row--editing');
      li.innerHTML = '';
      var fields = document.createElement('div');
      fields.className = 'tw-cat-mgr-edit-fields';

      var ni = document.createElement('input');
      ni.type = 'text'; ni.className = 'tw-cat-mgr-input'; ni.value = cat.name; ni.maxLength = 100;
      ni.setAttribute('aria-label', msg.category);
      var di = document.createElement('input');
      di.type = 'text'; di.className = 'tw-cat-mgr-input'; di.value = cat.description || '';
      di.setAttribute('aria-label', msg.description || msg.category);

      var btns = document.createElement('div');
      btns.className = 'tw-cat-mgr-edit-btns';

      var saveB = document.createElement('button');
      saveB.type = 'button'; saveB.className = 'tw-cat-mgr-btn tw-cat-mgr-btn--save';
      saveB.title = msg.save; saveB.setAttribute('aria-label', msg.save); saveB.innerHTML = '<i class="fas fa-check"></i>';
      saveB.addEventListener('click', function () {
        var name = ni.value.trim();
        if (!name) { showError(msg.name_req); return; }
        request(
          apiFetch(buildUrl(urls.edit, cat.id), 'POST', { name: name, description: di.value.trim() }),
          [saveB, cancelB, ni, di],
          function (data) {
            showError('');
            cat.name = data.name;
            cat.description = data.description;
            li.replaceWith(renderRow(cat));
          }
        );
      });

      var cancelB = document.createElement('button');
      cancelB.type = 'button'; cancelB.className = 'tw-cat-mgr-btn';
      cancelB.title = msg.cancel; cancelB.setAttribute('aria-label', msg.cancel); cancelB.innerHTML = '<i class="fas fa-times"></i>';
      cancelB.addEventListener('click', function () {
        li.replaceWith(renderRow(cat));
      });

      btns.appendChild(saveB); btns.appendChild(cancelB);
      fields.appendChild(ni); fields.appendChild(di); fields.appendChild(btns);
      li.appendChild(fields);
      ni.focus();
    }

    function performDelete(cat, li) {
      request(
        apiFetch(buildUrl(urls.del, cat.id), 'POST', {}),
        li.querySelectorAll('button'),
        function () {
          showError('');
          li.remove();
        }
      );
    }

    function confirmDelete(message, itemTitle, callback) {
      if (window.TwModal && window.TwModal.confirm) {
        window.TwModal.confirm({
          title: msg.delete,
          message: message,
          itemTitle: itemTitle,
          itemTitleLabel: msg.category,
          irreversible: true,
          irreversibleLabel: msg.irreversible,
          confirmLabel: msg.delete,
          cancelLabel: msg.cancel,
          onConfirm: callback,
        });
        return;
      }
      showError(msg.error || 'Confirmation is unavailable.');
    }

    function deleteCategory(cat, li) {
      var count = cat.item_count || 0;
      // When the host page provides an items endpoint, list the affected titles in the
      // confirmation so the user sees exactly which documents will become uncategorized.
      if (urls.items && count > 0) {
        request(
          apiFetch(buildUrl(urls.items, cat.id), 'GET'),
          li.querySelectorAll('button'),
          function (data) {
            var items = data.items || [];
            var body = msg.confirm_del.replace('{n}', data.count);
            // Guard against a lone "• " when the items list went empty between load and click.
            if (items.length) {
              body += '\n\n• ' + items.join('\n• ');
              if (data.count > items.length) {
                body += '\n' + msg.and_more.replace('{n}', data.count - items.length);
              }
            }
            confirmDelete(body, cat.name, function () { performDelete(cat, li); });
          }
        );
        return;
      }
      confirmDelete(msg.confirm_del.replace('{n}', count), cat.name, function () { performDelete(cat, li); });
    }

    function loadCategories() {
      request(
        apiFetch(urls.list, 'GET'),
        [addBtn, newName, newDesc],
        function (data) {
          list.innerHTML = '';
          data.categories.forEach(function (cat) {
            list.appendChild(renderRow(cat));
          });
        }
      );
    }

    if (addBtn) {
      addBtn.addEventListener('click', function () {
        var name = newName.value.trim();
        if (!name) { showError(msg.name_req); return; }
        request(
          apiFetch(urls.list, 'POST', { name: name, description: newDesc.value.trim() }),
          [addBtn, newName, newDesc],
          function (data) {
            showError('');
            newName.value = ''; newDesc.value = '';
            data.item_count = 0;
            list.appendChild(renderRow(data));
          }
        );
      });
    }

    modalEl.addEventListener('show.tw.modal', function () {
      loadCategories();
      if (urls.reorder && typeof initSortableList !== 'undefined') {
        if (sortable) { sortable.destroy(); sortable = null; }
        sortable = initSortableList(list, {
          handle: '.tw-cat-mgr-handle',
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
