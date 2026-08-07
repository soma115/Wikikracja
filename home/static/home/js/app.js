/**
 * Main application JavaScript
 * Consolidates inline scripts from various templates
 */

// ============================================================
// Topbar search: remember the last query in localStorage so the field
// isn't cleared when navigating between pages. Shared key with the
// search page's own input, see search.html and search-keys.js.
// ============================================================
document.addEventListener('DOMContentLoaded', function() {
    var QUERY_KEY = window.WK_SEARCH_KEYS.QUERY;
    var input = document.getElementById('topbar-q');
    var form = document.getElementById('topbar-search-form');
    if (!input || !form) return;

    if (!input.value.trim()) {
        try {
            var stored = localStorage.getItem(QUERY_KEY);
            if (stored) input.value = stored;
        } catch (e) { /* storage unavailable */ }
    }

    form.addEventListener('submit', function() {
        try {
            var v = input.value.trim();
            if (v) localStorage.setItem(QUERY_KEY, v);
            else localStorage.removeItem(QUERY_KEY);
        } catch (e) { /* storage unavailable */ }
    });
});

// ============================================================
// Global notification permission banner handler - from base.html
// ============================================================
document.addEventListener('DOMContentLoaded', function() {
    const banner = document.getElementById('notification-permission-banner');
    const blockedBanner = document.getElementById('notification-blocked-banner');
    if (!banner || !blockedBanner) return;

    function showBanner(el) {
        el.parentElement.style.maxHeight = el.scrollHeight + 'px';
    }
    function hideBanner(el) {
        el.parentElement.style.maxHeight = '0';
    }

    // max-height zamraża wysokość w pikselach. Po resize/obrocie tekst banera może
    // zawinąć się na więcej linii — przelicz zamrożoną wysokość pokazanych banerów,
    // żeby overflow:hidden nie przyciął dołu.
    window.addEventListener('resize', function() {
        [banner, blockedBanner].forEach(function(el) {
            var wrap = el.parentElement;
            if (wrap.style.maxHeight && wrap.style.maxHeight !== '0px') {
                wrap.style.maxHeight = el.scrollHeight + 'px';
            }
        });
    });

    // Check if Notification API is supported
    if (!('Notification' in window)) {
        console.log('Notifications not supported');
        return;
    }

    // Check if user has already dismissed the banner
    const dismissed = localStorage.getItem('notification-banner-dismissed');
    const blockedDismissed = localStorage.getItem('notification-blocked-dismissed');

    // Show appropriate banner based on permission state
    if (Notification.permission === 'default' && !dismissed) {
        showBanner(banner);
    } else if (Notification.permission === 'denied' && !blockedDismissed) {
        showBanner(blockedBanner);
    }

    // Handle "Enable Notifications" button
    document.getElementById('enable-notifications-global')?.addEventListener('click', async function(e) {
        e.preventDefault();
        console.log('Enable notifications clicked, current permission:', Notification.permission);

        try {
            // Request permission
            const permission = await Notification.requestPermission();
            console.log('Permission result:', permission);

            if (permission === 'granted') {
                hideBanner(banner);
                localStorage.removeItem('notification-banner-dismissed');
                // Reload to initialize push notifications
                location.reload();
            } else if (permission === 'denied') {
                // Show blocked banner
                hideBanner(banner);
                showBanner(blockedBanner);
                // Remember that user denied
                localStorage.setItem('notification-blocked-dismissed', Date.now() + (30 * 24 * 60 * 60 * 1000));
            } else {
                // Permission is still 'default' - user dismissed the prompt
                console.log('User dismissed the permission prompt');
            }
        } catch (error) {
            console.error('Error requesting notification permission:', error);
            // Show blocked banner on error
            hideBanner(banner);
            showBanner(blockedBanner);
        }
    });

    // Handle "Not now" button
    document.getElementById('dismiss-notifications-banner')?.addEventListener('click', function() {
        hideBanner(banner);
        // Remember dismissal for 7 days
        const dismissedUntil = Date.now() + (7 * 24 * 60 * 60 * 1000);
        localStorage.setItem('notification-banner-dismissed', dismissedUntil);
    });

    // Handle "Dismiss" button on blocked banner
    document.getElementById('dismiss-blocked-banner')?.addEventListener('click', function() {
        hideBanner(blockedBanner);
        // Remember dismissal for 30 days
        const dismissedUntil = Date.now() + (30 * 24 * 60 * 60 * 1000);
        localStorage.setItem('notification-blocked-dismissed', dismissedUntil);
    });

    // Check if dismissal has expired
    if (dismissed && parseInt(dismissed) < Date.now()) {
        localStorage.removeItem('notification-banner-dismissed');
        if (Notification.permission === 'default') {
            showBanner(banner);
        }
    }

    if (blockedDismissed && parseInt(blockedDismissed) < Date.now()) {
        localStorage.removeItem('notification-blocked-dismissed');
        if (Notification.permission === 'denied') {
            showBanner(blockedBanner);
        }
    }

    // ============================================================
    // Year selector for bookkeeping report - from report_list.html
    // ============================================================
    const yearSelect = document.getElementById('yearSelect');
    if (yearSelect) {
        const reportListUrl = yearSelect.dataset.reportListUrl;
        yearSelect.addEventListener('change', function() {
            const selectedYear = this.value;
            window.location.href = reportListUrl + '?year=' + selectedYear;
        });
    }

    // ============================================================
    // Event form frequency toggle - from event_form.html
    // ============================================================
    const frequencyField = document.getElementById('id_frequency');
    const ordinalFieldsRow = document.getElementById('ordinal-fields-row');

    if (frequencyField && ordinalFieldsRow) {
        function toggleOrdinalFields() {
            if (frequencyField.value === 'monthly_ordinal') {
                ordinalFieldsRow.style.display = 'flex';
            } else {
                ordinalFieldsRow.style.display = 'none';
            }
        }

        // Initial state
        toggleOrdinalFields();

        // Listen for changes
        frequencyField.addEventListener('change', toggleOrdinalFields);
    }
});

// ============================================================
// Theme toggle — applyTheme exposed globally for other scripts
// ============================================================
document.addEventListener('DOMContentLoaded', function() {
    window.applyTheme = function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('app-theme', theme);
    }

    const btn = document.getElementById('theme-toggle-btn');
    if (btn) {
        btn.addEventListener('click', function() {
            applyTheme(document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
        });
    }
});

document.addEventListener('DOMContentLoaded', function() {
    /* ── toggle pojedynczego kafelka ── */
    window.toggleCard = function(pk) {
        const card = document.getElementById('card-' + pk);
        if (!card) return;
        card.classList.toggle('open');
    };
});

// ============================================================
// PagePrefs — globalny system zapamiętywania ustawień strony
// ------------------------------------------------------------
// Per-scope JSON w localStorage: { view, filters, tab }
//   - scope ustawia szablon przez `data-prefs-scope` na <html>
//   - filtry (URL params) restore'owane są w head-script (anti-FOUC)
//   - widok lista/grid/compact: data-view="list|grid|compact" + [data-view-container]
//   - tab persistence: Bootstrap tabs auto-wired
// ============================================================
(function() {
    'use strict';

    var KEY_PREFIX = 'wikikracja:prefs:';

    function scope() {
        return document.documentElement.dataset.prefsScope || '';
    }

    function read() {
        var s = scope();
        if (!s) return {};
        try { return JSON.parse(localStorage.getItem(KEY_PREFIX + s) || '{}'); }
        catch (e) { return {}; }
    }

    function write(patch) {
        var s = scope();
        if (!s) return;
        var data = Object.assign(read(), patch);
        localStorage.setItem(KEY_PREFIX + s, JSON.stringify(data));
    }

    function clear() {
        var s = scope();
        if (s) localStorage.removeItem(KEY_PREFIX + s);
    }

    function applyView(mode) {
        var container = document.querySelector('[data-view-container]');
        if (!container) return;
        container.classList.remove('view-grid', 'view-compact');
        if (mode === 'grid') container.classList.add('view-grid');
        else if (mode === 'compact') container.classList.add('view-compact');
        document.querySelectorAll('[data-view]').forEach(function(btn) {
            btn.classList.toggle('active', btn.dataset.view === mode);
        });
        if (mode === 'compact') {
            container.querySelectorAll('.proposal-card.open').forEach(function(card) {
                card.classList.remove('open');
            });
        }
    }

    function setView(mode) {
        applyView(mode);
        write({ view: mode });
    }

    function saveCurrentFilters() {
        if (scope()) write({ filters: window.location.search });
    }

    // One-shot migracja starych kluczy → nowy format JSON per scope
    function migrateLegacyKeys() {
        var migrations = {
            'tasks':      [{ k: 'tasks_view',     p: 'view' }, { k: 'tasks_tab', p: 'tab' }],
            'glosowania': [{ k: 'proposals_view', p: 'view' }],
            'board':      [{ k: 'board_view',     p: 'view' }],
            'activity':   [{ k: 'activity_view',  p: 'view' }]
        };
        Object.keys(migrations).forEach(function(scopeName) {
            var newKey = KEY_PREFIX + scopeName;
            if (localStorage.getItem(newKey) !== null) return; // już zmigrowano
            var data = {};
            var found = false;
            migrations[scopeName].forEach(function(m) {
                var v = localStorage.getItem(m.k);
                if (v !== null) { data[m.p] = v; found = true; }
            });
            if (found) {
                localStorage.setItem(newKey, JSON.stringify(data));
                migrations[scopeName].forEach(function(m) { localStorage.removeItem(m.k); });
            }
        });
    }

    function init() {
        if (!scope()) return;

        // 1. Widok lista/grid (filtry URL już zrestore'owane przez head-script)
        applyView(read().view || 'list');

        // 2. Zapisz aktualny URL (gdy ma params — pokrywa reload, klik linka sortowania)
        if (window.location.search) saveCurrentFilters();

        // 3. Patch history.pushState — łapie zmiany URL przez JS (kategoria filter w tasks/board)
        var origPush = history.pushState;
        history.pushState = function() {
            var ret = origPush.apply(this, arguments);
            saveCurrentFilters();
            return ret;
        };
        window.addEventListener('popstate', saveCurrentFilters);

        // 4. Auto-wire view toggle buttons
        document.querySelectorAll('[data-view]').forEach(function(btn) {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                setView(btn.dataset.view);
            });
        });

        // 5. Tab persistence (Bootstrap tabs) w tym samym JSON
        var savedTab = read().tab;
        if (savedTab && typeof bootstrap !== 'undefined') {
            var trigger = document.querySelector('[data-bs-target="#' + savedTab + '"]');
            if (trigger) new bootstrap.Tab(trigger).show();
        }
        document.querySelectorAll('button[data-bs-toggle="tab"]').forEach(function(tab) {
            tab.addEventListener('shown.bs.tab', function(e) {
                var targetId = e.target.getAttribute('data-bs-target').substring(1);
                write({ tab: targetId });
            });
        });
    }

    migrateLegacyKeys();

    window.PagePrefs = {
        init: init,
        setView: setView,
        read: read,
        write: write,
        clear: clear,
        saveCurrentFilters: saveCurrentFilters
    };

    document.addEventListener('DOMContentLoaded', init);
})();

document.addEventListener('DOMContentLoaded', function() {
    // Board category filter
    const categoryChips = document.querySelectorAll('.category-chip');
    categoryChips.forEach(function(chip) {
        chip.addEventListener('click', function() {
            const category = this.dataset.category;
            const url = new URL(window.location);
            const currentCategory = url.searchParams.get('category');

            if (currentCategory === category) {
                // Toggle off - remove category parameter
                url.searchParams.delete('category');
            } else {
                // Set new category
                url.searchParams.set('category', category);
            }

            window.location.href = url.toString();
        });
    });
});

document.addEventListener('DOMContentLoaded', function() {
    (function() {
        const toggle = document.getElementById('sidebar-toggle');
        if (toggle) {
            toggle.addEventListener('click', function() {
                document.getElementById('sidebar').classList.toggle('sidebar-open');
                const overlay = document.getElementById('sidebar-overlay');
                overlay.style.display = overlay.style.display === 'none' ? 'block' : 'none';
            });
        }
    })();
});

document.addEventListener('DOMContentLoaded', function() {
    const sidebar = document.getElementById('sidebar');
    const mainArea = document.querySelector('.main-area');
    const btn = document.getElementById('sidebar-collapse-btn');
    const icon = document.getElementById('sidebar-collapse-icon');
    if (!sidebar || !btn) return;

    const STORAGE_KEY = 'sidebar_collapsed';

    function applyState(collapsed) {
        if (collapsed) {
            sidebar.classList.add('collapsed');
            mainArea.classList.add('sidebar-collapsed');
            icon.classList.replace('fa-angles-left', 'fa-angles-right');
        } else {
            sidebar.classList.remove('collapsed');
            mainArea.classList.remove('sidebar-collapsed');
            icon.classList.replace('fa-angles-right', 'fa-angles-left');
        }
    }
    applyState(localStorage.getItem(STORAGE_KEY) === 'true');

    // Toggle sidebar state on button click
    btn.addEventListener('click', function() {
        const isCollapsed = sidebar.classList.contains('collapsed');
        applyState(!isCollapsed);
        localStorage.setItem(STORAGE_KEY, String(!isCollapsed));
    });
});

// ============================================================
// Mark activity feed items as read - shared function
// ============================================================
window.initActivityFeedMarkRead = function(containerSelector, linkSelector) {
    var container = document.querySelector(containerSelector);
    if (!container) return;

    container.addEventListener('click', function(e) {
        // Don't navigate when the user clicked the read/unread toggle.
        if (e.target.closest('.feed-toggle-read')) return;

        var link = e.target.closest(linkSelector);
        if (!link) return;
        e.preventDefault();
        var contentType = link.getAttribute('data-content-type');
        var objectId = link.getAttribute('data-object-id');
        var url = link.getAttribute('href');
        if (!contentType || !objectId) {
            window.location.href = url;
            return;
        }
        fetch(window.MARK_AS_READ_URL || '/mark-as-read/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': window.CSRF_TOKEN || '',
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: new URLSearchParams({
                content_type: contentType,
                object_id: objectId
            })
        }).finally(function() {
            window.location.href = url;
        });
    });
};

// ============================================================
// Toggle activity feed items read/unread - small per-row control
// ============================================================
window.initActivityFeedToggleRead = function(containerSelector) {
    var container = document.querySelector(containerSelector);
    if (!container) return;

    function toggle(btn) {
        var contentType = btn.getAttribute('data-content-type');
        var objectId = btn.getAttribute('data-object-id');
        var isRead = btn.getAttribute('data-is-read') === 'true';
        if (!contentType || !objectId) return;

        var url = isRead
            ? (window.MARK_UNREAD_URL || '/mark-unread/')
            : (window.MARK_AS_READ_URL || '/mark-as-read/');

        fetch(url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': window.CSRF_TOKEN || '',
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: new URLSearchParams({
                content_type: contentType,
                object_id: objectId
            })
        }).then(function(r) { return r.json(); }).then(function(data) {
            if (!data.success) return;

            var row = btn.closest('.feed-row');
            var newRead = !isRead;
            btn.setAttribute('data-is-read', newRead ? 'true' : 'false');

            // Update icon, title and aria-label
            var icon = btn.querySelector('i');
            var readTitle = btn.getAttribute('data-mark-read-title') || 'Mark as read';
            var unreadTitle = btn.getAttribute('data-mark-unread-title') || 'Mark as unread';
            var label = newRead ? unreadTitle : readTitle;
            if (icon) {
                icon.classList.toggle('fa-eye', !newRead);
                icon.classList.toggle('fa-eye-slash', newRead);
            }
            btn.setAttribute('title', label);
            btn.setAttribute('aria-label', label);

            if (row) {
                // Visual unread styling
                if (newRead) {
                    row.classList.remove('unread-item');
                    var title = row.querySelector('.feed-title');
                    if (title) title.classList.remove('fw-semibold');
                } else {
                    row.classList.add('unread-item');
                    var title = row.querySelector('.feed-title');
                    if (title) title.classList.add('fw-semibold');
                }

                // For chat rooms, also show/hide the message-count badge
                if (row.getAttribute('data-content-type') === 'room_messages') {
                    var chatCount = row.querySelector('.chat-message-count');
                    if (chatCount) {
                        chatCount.classList.toggle('d-none', newRead);
                    }
                }
            }

            // If the user is filtering to unread only and just marked as read,
            // reload so the row disappears from the filtered list.
            if (newRead && window.ACTIVITY_FILTER_UNREAD) {
                window.location.reload();
                return;
            }

            // Update unread counter badge in the filter toolbar
            var counter = document.querySelector('#unread-count-badge');
            if (counter) {
                var current = parseInt(counter.textContent.replace(/[()]/g, ''), 10) || 0;
                var delta = newRead ? -1 : 1;
                var next = Math.max(0, current + delta);
                if (next === 0) {
                    counter.textContent = '';
                    counter.classList.add('d-none');
                } else {
                    counter.textContent = '(' + next + ')';
                    counter.classList.remove('d-none');
                }
            }
        });
    }

    container.addEventListener('click', function(e) {
        var btn = e.target.closest('.feed-toggle-read');
        if (!btn) return;
        e.preventDefault();
        e.stopPropagation();
        toggle(btn);
    });

    container.addEventListener('keydown', function(e) {
        var btn = e.target.closest('.feed-toggle-read');
        if (!btn) return;
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            e.stopPropagation();
            toggle(btn);
        }
    });
};

// Toggle .expandable blocks — clicking body toggles open/close (only when overflow detected).
function hasSelectedTextInside(container) {
    const selection = window.getSelection?.();
    if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return false;
    if (!(selection.toString() || '').trim()) return false;
    const range = selection.getRangeAt(0);

    if (typeof range.intersectsNode === 'function') {
        try {
            return range.intersectsNode(container);
        } catch (err) {
            // Fall through to compatibility checks below.
        }
    }

    if (container.contains(range.startContainer) || container.contains(range.endContainer)) {
        return true;
    }

    const ancestor = range.commonAncestorContainer;
    const ancestorEl = ancestor.nodeType === Node.ELEMENT_NODE ? ancestor : ancestor.parentElement;
    return !!(ancestorEl && container.contains(ancestorEl));
}

document.addEventListener('click', function(e) {
    if (e.target.closest('a')) return;
    const body = e.target.closest('.expandable-body');
    const el = body?.closest('.expandable');
    if (!el?.classList.contains('has-overflow')) return;
    if (hasSelectedTextInside(body)) return;
    el.classList.toggle('is-open');
});

// Globalna inicjalizacja Bootstrap tooltipów — każdy [data-bs-toggle="tooltip"] działa
// bez per-page boilerplate'u. Trigger 'hover' (bez focus) żeby chip nie zostawał
// "kliknięty" po tap'ie na mobile.
document.addEventListener('DOMContentLoaded', function () {
    if (typeof bootstrap === 'undefined' || !bootstrap.Tooltip) return;
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
        new bootstrap.Tooltip(el, { trigger: 'hover' });
    });
});