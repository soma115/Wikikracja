(function () {
  'use strict';

  function setVoteBtnState(btn, isActive) {
    btn.classList.toggle('active-vote', isActive);
    var icon = btn.querySelector('i');
    if (icon) {
      icon.className = 'fas ' + (isActive ? btn.dataset.iconActive : btn.dataset.iconInactive);
    }
    var textNode = Array.from(btn.childNodes).find(function (n) {
      return n.nodeType === Node.TEXT_NODE && n.textContent.trim();
    });
    if (textNode) {
      textNode.textContent = ' ' + (isActive ? btn.dataset.textActive : btn.dataset.textInactive);
    }
    var newTitle = isActive ? btn.dataset.tooltipActive : btn.dataset.tooltipInactive;
    if (newTitle) {
      btn.setAttribute('title', newTitle);
      if (typeof bootstrap !== 'undefined') {
        var tip = bootstrap.Tooltip.getInstance(btn);
        if (tip) { tip.dispose(); new bootstrap.Tooltip(btn, { trigger: 'hover' }); }
      }
    }
  }

  function updateVoteCounts(form, data) {
    var card = form.closest('.task-card');
    if (card) {
      var countEl = card.querySelector('.task-helpers-count');
      if (countEl) {
        countEl.textContent = data.votes_up;
      }
      var againstEl = card.querySelector('.task-against-count');
      if (againstEl && typeof data.votes_down !== 'undefined') {
        againstEl.textContent = data.votes_down;
      }
      // Vote changed — popover content may be stale, drop cached html for this task
      var helpersBtn = card.querySelector('[data-task-helpers]');
      if (helpersBtn) {
        helpersCache.delete(helpersBtn.dataset.taskHelpers);
      }
      var againstBtn = card.querySelector('[data-task-against]');
      if (againstBtn) {
        againstCache.delete(againstBtn.dataset.taskAgainst);
      }
    }
    var badge = document.querySelector('[data-votes-badge]');
    if (badge) {
      badge.textContent = badge.dataset.votesBadge + data.votes_score;
    }
  }

  function handleVoteClick(e) {
    var btn = e.target.closest('.task-vote-btn');
    if (!btn) return;
    var form = btn.closest('form');
    if (!form) return;

    // Prevent form submission and stop click reaching card-body onclick / card-header navigation
    e.preventDefault();
    e.stopPropagation();

    var value = parseInt(form.querySelector('input[name="value"]').value, 10);
    var csrf = form.querySelector('[name="csrfmiddlewaretoken"]').value;

    fetch(form.action, {
      method: 'POST',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({ value: value, csrfmiddlewaretoken: csrf }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var row = form.closest('.task-vote-row, .task-actions');
        if (!row) return;
        var upBtn = row.querySelector('.task-vote-btn.up');
        var downBtn = row.querySelector('.task-vote-btn.down');
        if (upBtn) setVoteBtnState(upBtn, data.vote === 1);
        if (downBtn) setVoteBtnState(downBtn, data.vote === -1);
        updateVoteCounts(form, data);
        updateVoterLists(data);
      })
      .catch(function () {
        // silent fail — card stays open, user can retry
      });
  }

  // Capture phase: fires before card-body onclick and card-header navigation
  document.addEventListener('click', handleVoteClick, true);

  // ─── Live update for "Willing to help" / "Against this task" lists ──
  function buildVoterItem(user) {
    var item = document.createElement('a');
    item.className = 'helpers-popover-item';
    item.href = user.profile_url;
    item.dataset.userId = user.id;

    var avatar = document.createElement('span');
    avatar.className = 'avatar avatar-xl avatar-accent';
    if (user.avatar_url) {
      var img = document.createElement('img');
      img.src = user.avatar_url;
      img.alt = '';
      avatar.appendChild(img);
    } else {
      avatar.textContent = (user.username || '').slice(0, 2).toUpperCase();
    }
    item.appendChild(avatar);

    var name = document.createElement('span');
    name.className = 'helpers-popover-name';
    name.textContent = user.username;
    item.appendChild(name);

    return item;
  }

  function buildDetailVoterItem(user) {
    var i18n = window.TASK_HELPERS_I18N || {};
    var isSelfCoordinator = window.IS_COORDINATOR && window.CURRENT_USER && user.id === window.CURRENT_USER.id;
    var wrap = document.createElement('div');
    wrap.className = 'helpers-voter-item';
    wrap.dataset.userId = user.id;

    var link = buildVoterItem(user);
    link.className = 'helpers-popover-item';
    wrap.appendChild(link);

    var status = document.createElement('span');
    if (isSelfCoordinator) {
      status.className = 'helper-status helper-status--approved';
      status.innerHTML = '<i class="fas fa-user-shield"></i> ' + (i18n.coordinator || 'Coordinator');
    } else {
      status.className = 'helper-status helper-status--pending';
      status.innerHTML = '<i class="fas fa-clock"></i> ' + (i18n.pending || 'Pending');
    }
    wrap.appendChild(status);

    if (window.IS_COORDINATOR && window.TASK_ID && !isSelfCoordinator) {
      var form = document.createElement('form');
      form.className = 'helper-toggle-form';
      form.method = 'post';
      form.action = '/tasks/' + window.TASK_ID + '/toggle/' + user.id + '/';
      form.dataset.userId = user.id;

      var csrf = document.querySelector('[name="csrfmiddlewaretoken"]');
      if (csrf) {
        var csrfInput = document.createElement('input');
        csrfInput.type = 'hidden';
        csrfInput.name = 'csrfmiddlewaretoken';
        csrfInput.value = csrf.value;
        form.appendChild(csrfInput);
      }

      var label = document.createElement('label');
      label.className = 'helper-switch';
      label.title = i18n.approve_for_team || 'Approve for team';

      var checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.dataset.helperToggle = '';

      var slider = document.createElement('span');
      slider.className = 'helper-switch-slider';

      label.appendChild(checkbox);
      label.appendChild(slider);
      form.appendChild(label);
      wrap.appendChild(form);
    }

    return wrap;
  }

  function syncVoterEmptyState() {
    ['helpers', 'against'].forEach(function (key) {
      var list = document.querySelector('[data-voter-list="' + key + '"]');
      var empty = document.querySelector('[data-voter-empty="' + key + '"]');
      if (!list || !empty) return;
      var has = list.children.length > 0;
      list.hidden = !has;
      empty.hidden = has;
    });
  }

  function updateVoterLists(data) {
    if (!window.CURRENT_USER || window.CURRENT_USER.id == null) return;
    var userId = String(window.CURRENT_USER.id);
    document.querySelectorAll('[data-voter-list] .helpers-voter-item[data-user-id="' + userId + '"]')
      .forEach(function (el) { el.remove(); });
    document.querySelectorAll('[data-voter-list] .helpers-popover-item[data-user-id="' + userId + '"]')
      .forEach(function (el) { el.closest('.helpers-voter-item')?.remove(); el.remove(); });

    var targetKey = data.vote === 1 ? 'helpers' : (data.vote === -1 ? 'against' : null);
    if (targetKey) {
      var target = document.querySelector('[data-voter-list="' + targetKey + '"]');
      if (target) {
        if (target.classList.contains('helpers-voter-list')) {
          var item = buildDetailVoterItem(window.CURRENT_USER);
          if (window.IS_COORDINATOR) {
            target.insertBefore(item, target.firstChild);
          } else {
            target.appendChild(item);
          }
        } else {
          target.appendChild(buildVoterItem(window.CURRENT_USER));
        }
      }
    }
    syncVoterEmptyState();
  }

  // ─── Coordinator take/resign live update ──────────────────────
  function handleCoordSubmit(e) {
    var form = e.target.closest && e.target.closest('form');
    if (!form) return;
    var action = form.action || '';
    if (!/\/(take|resign)\/?$/.test(action)) return;

    e.preventDefault();
    e.stopPropagation();

    var csrf = form.querySelector('[name="csrfmiddlewaretoken"]');
    if (!csrf) return;

    fetch(action, {
      method: 'POST',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({ csrfmiddlewaretoken: csrf.value }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data || !data.ok) return;
        updateCoordinatorUI(form, data);
      })
      .catch(function () {
        // silent fail — user can retry
      });
  }

  function buildAvatarHtml(user, size) {
    var initials = escapeHtml((user.username || '').slice(0, 2).toUpperCase());
    if (user.avatar_url) {
      return '<img class="avatar avatar-' + size + '" src="' + escapeHtml(user.avatar_url) + '" alt="' + escapeHtml(user.username || '') + '">';
    }
    var color = user.citizen_color_class ? ' ' + user.citizen_color_class : '';
    return '<div class="avatar avatar-' + size + ' avatar-fallback' + color + '">' + initials + '</div>';
  }

  // Fill a coordinator chip (link/span) with a user's name, avatar, profile url
  function fillPersonChip(el, user) {
    var nameEl = el.querySelector('[data-coord-name]');
    if (nameEl) nameEl.textContent = user.username;
    var avatarEl = el.querySelector('[data-coord-avatar]');
    if (avatarEl) avatarEl.innerHTML = buildAvatarHtml(user, avatarEl.dataset.avatarSize || 'md');
    if (el.tagName === 'A' && user.profile_url) el.href = user.profile_url;
    if (el.dataset.coordTitle) {
      el.title = el.dataset.coordTitle + user.username;
      if (typeof bootstrap !== 'undefined') {
        var tip = bootstrap.Tooltip.getInstance(el);
        if (tip) { tip.dispose(); new bootstrap.Tooltip(el, { trigger: 'hover' }); }
      }
    }
  }

  function setHelperStatus(userId, inTeam) {
    if (userId == null) return;
    var item = document.querySelector('.helpers-voter-item[data-user-id="' + userId + '"]');
    var status = item && item.querySelector('.helper-status');
    if (!status) return;
    var i18n = window.TASK_HELPERS_I18N || {};
    var conf = inTeam
      ? { cls: 'helper-status--approved', icon: 'fa-check-circle', text: i18n.in_team || 'In team' }
      : { cls: 'helper-status--pending', icon: 'fa-clock', text: i18n.pending || 'Pending' };
    status.className = 'helper-status ' + conf.cls;
    status.title = conf.text;
    status.innerHTML = '<i class="fas ' + conf.icon + '"></i> ' + conf.text;
  }

  // After resign keep the detail-page helpers list consistent: drop the
  // approve toggles and demote the ex-coordinator's status (they may stay
  // in the team as an approved helper).
  function syncHelpersAfterCoordChange(data) {
    window.IS_COORDINATOR = data.is_coordinator === true;
    var list = document.querySelector('.helpers-voter-list[data-voter-list="helpers"]');
    if (!list || window.IS_COORDINATOR) return;
    list.querySelectorAll('.helper-toggle-form').forEach(function (f) { f.remove(); });
    setHelperStatus(window.CURRENT_USER && window.CURRENT_USER.id, data.in_team === true);
  }

  function updateCoordinatorUI(form, data) {
    var isAssigned = data.assigned_to !== null;
    // Scope to enclosing card on task list; document elsewhere (detail page has no .task-card)
    var card = form.closest('.task-card');
    var scope = card || document;

    scope.querySelectorAll('[data-coord-state="empty"]').forEach(function (el) {
      el.hidden = isAssigned;
    });
    scope.querySelectorAll('[data-coord-state="me"]').forEach(function (el) {
      el.hidden = !isAssigned;
    });

    // Card body "Coordinator:" row — link + name or 'n/a'
    var assignee = scope.querySelector('[data-coord-assignee]');
    if (assignee) {
      assignee.hidden = !isAssigned;
      if (isAssigned) fillPersonChip(assignee, data.assigned_to);
    }
    var assigneeEmpty = scope.querySelector('[data-coord-assignee-empty]');
    if (assigneeEmpty) {
      assigneeEmpty.hidden = isAssigned;
    }

    // Detail page coordinator label: update text in `Coordinator: <span>...</span>`
    var label = document.querySelector('[data-coord-label]');
    if (label) {
      var coordI18n = window.TASK_COORD_I18N || {};
      label.textContent = isAssigned
        ? (data.assigned_to.username || '')
        : (coordI18n.none_label || 'None');
    }

    syncHelpersAfterCoordChange(data);
  }

  document.addEventListener('submit', handleCoordSubmit, true);

  // ─── Coordinator helper approval toggle live update ─────────────────────
  function updateHelperApproval(userId, approved) {
    var item = document.querySelector('.helpers-voter-item[data-user-id="' + userId + '"]');
    if (!item) return;

    var status = item.querySelector('.helper-status');
    if (status) {
      if (approved) {
        status.className = 'helper-status helper-status--approved';
        status.innerHTML = '<i class="fas fa-check-circle"></i> ' + (window.TASK_HELPERS_I18N && window.TASK_HELPERS_I18N.in_team || 'In team');
      } else {
        status.className = 'helper-status helper-status--pending';
        status.innerHTML = '<i class="fas fa-clock"></i> ' + (window.TASK_HELPERS_I18N && window.TASK_HELPERS_I18N.pending || 'Pending');
      }
    }

    var checkbox = item.querySelector('input[data-helper-toggle]');
    if (checkbox && checkbox.checked !== approved) {
      checkbox.checked = approved;
    }
  }

  function handleHelperToggleChange(e) {
    var checkbox = e.target.closest && e.target.closest('input[data-helper-toggle]');
    if (!checkbox) return;

    var form = checkbox.closest('form.helper-toggle-form');
    if (!form) return;

    e.preventDefault();
    e.stopPropagation();

    var csrf = form.querySelector('[name="csrfmiddlewaretoken"]');
    if (!csrf) return;

    fetch(form.action, {
      method: 'POST',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({ csrfmiddlewaretoken: csrf.value }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data || !data.ok) {
          // Revert on failure so the switch reflects the server state.
          checkbox.checked = !checkbox.checked;
          return;
        }
        updateHelperApproval(data.user_id, data.approved);
      })
      .catch(function () {
        checkbox.checked = !checkbox.checked;
      });
  }

  document.addEventListener('change', handleHelperToggleChange, true);

  document.addEventListener('DOMContentLoaded', function () {
    if (typeof window.reinitTaskCards === 'function') window.reinitTaskCards();

    // Single document-level click listener closes any open voter popover when
    // clicking outside it (touch devices). Replaces N per-button listeners.
    if (!supportsHover) {
      document.addEventListener('click', function (e) {
        document.querySelectorAll('[data-task-helpers], [data-task-against]').forEach(function (btn) {
          var tipId = btn.getAttribute('aria-describedby');
          if (!tipId) return;
          var tip = document.getElementById(tipId);
          if (tip && !tip.contains(e.target) && !btn.contains(e.target)) {
            var popover = bootstrap.Popover.getInstance(btn);
            if (popover) popover.hide();
          }
        });
      });
    }
  });

  // ─── Helpers popover ──────────────────────────────────────────
  var helpersCache = new Map();
  var againstCache = new Map();
  var i18n = (window.TASK_HELPERS_I18N || {});
  var againstI18n = (window.TASK_AGAINST_I18N || {});
  var supportsHover = window.matchMedia('(hover: hover) and (pointer: fine)').matches;

  function sanitize(html) {
    if (typeof DOMPurify !== 'undefined') {
      return DOMPurify.sanitize(html, { ADD_ATTR: ['target'] });
    }
    return html;
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function renderVotersHtml(data, labels) {
    if (!data.total) {
      return '<div class="helpers-popover-empty">' + escapeHtml(labels.empty || 'No one helps yet') + '</div>';
    }
    var items = data.helpers.map(function (h) {
      var avatar = h.avatar_url
        ? '<img src="' + escapeHtml(h.avatar_url) + '" alt="">'
        : escapeHtml(h.username.slice(0, 2).toUpperCase());
      return '<a class="helpers-popover-item" href="' + escapeHtml(h.profile_url) + '">'
        + '<span class="avatar avatar-xl avatar-accent">' + avatar + '</span>'
        + '<span class="helpers-popover-name">' + escapeHtml(h.username) + '</span>'
        + '</a>';
    }).join('');
    var more = '';
    if (data.extra > 0) {
      var moreText = (labels.more || 'and {n} more — see all').replace('{n}', data.extra);
      more = '<a class="helpers-popover-more" href="' + escapeHtml(data.task_url) + '">'
           + escapeHtml(moreText) + '</a>';
    }
    return '<div class="helpers-popover-list">' + items + more + '</div>';
  }

  function loadHelpers(btn, popover) {
    var taskId = btn.dataset.taskHelpers;
    if (helpersCache.has(taskId)) {
      popover.setContent({ '.popover-body': sanitize(helpersCache.get(taskId)) });
      return;
    }
    fetch(btn.dataset.helpersUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var html = renderVotersHtml(data, i18n);
        helpersCache.set(taskId, html);
        popover.setContent({ '.popover-body': sanitize(html) });
      })
      .catch(function () {
        var err = '<div class="helpers-popover-empty">' + escapeHtml(i18n.error || 'Could not load helpers') + '</div>';
        popover.setContent({ '.popover-body': sanitize(err) });
      });
  }

  function loadAgainst(btn, popover) {
    var taskId = btn.dataset.taskAgainst;
    if (againstCache.has(taskId)) {
      popover.setContent({ '.popover-body': sanitize(againstCache.get(taskId)) });
      return;
    }
    fetch(btn.dataset.againstUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var html = renderVotersHtml(data, againstI18n);
        againstCache.set(taskId, html);
        popover.setContent({ '.popover-body': sanitize(html) });
      })
      .catch(function () {
        var err = '<div class="helpers-popover-empty">' + escapeHtml(againstI18n.error || 'Could not load opponents') + '</div>';
        popover.setContent({ '.popover-body': sanitize(err) });
      });
  }

  function initVoterPopover(btn, popoverOptions, loadFn) {
    var popover = new bootstrap.Popover(btn, popoverOptions);
    var hideTimer = null;
    var clearHide = function () { if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; } };
    var scheduleHide = function () {
      clearHide();
      hideTimer = setTimeout(function () { popover.hide(); }, 150);
    };

    btn.addEventListener('show.bs.popover', function () { loadFn(btn, popover); });

    if (supportsHover) {
      btn.addEventListener('mouseenter', function () { clearHide(); popover.show(); });
      btn.addEventListener('mouseleave', scheduleHide);
      btn.addEventListener('focus', function () { popover.show(); });
      btn.addEventListener('blur', scheduleHide);
      btn.addEventListener('shown.bs.popover', function () {
        var tip = document.getElementById(btn.getAttribute('aria-describedby'));
        if (!tip) return;
        tip.addEventListener('mouseenter', clearHide);
        tip.addEventListener('mouseleave', scheduleHide);
      });
    } else {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var tipId = btn.getAttribute('aria-describedby');
        if (tipId && document.getElementById(tipId)) {
          popover.hide();
        } else {
          popover.show();
        }
      });
    }
  }

  function initHelpersPopovers() {
    if (typeof bootstrap === 'undefined') return;
    document.querySelectorAll('[data-task-helpers]').forEach(function (btn) {
      initVoterPopover(btn, { sanitize: false, html: true, customClass: 'helpers-popover' }, loadHelpers);
    });
  }

  function initAgainstPopovers() {
    if (typeof bootstrap === 'undefined') return;
    document.querySelectorAll('[data-task-against]').forEach(function (btn) {
      initVoterPopover(btn, { sanitize: false, html: true, customClass: 'helpers-popover against-popover' }, loadAgainst);
    });
  }

  window.reinitTaskCards = function() {
    if (typeof bootstrap === 'undefined') return;

    // Tooltips
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
      var t = bootstrap.Tooltip.getInstance(el);
      if (t) t.dispose();
      new bootstrap.Tooltip(el, { trigger: 'hover' });
    });

    // Popovers
    document.querySelectorAll('[data-task-helpers], [data-task-against]').forEach(function (btn) {
      var p = bootstrap.Popover.getInstance(btn);
      if (p) p.dispose();
    });
    initHelpersPopovers();
    initAgainstPopovers();
  };
}());
