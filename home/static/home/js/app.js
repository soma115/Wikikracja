/**
 * Main application JavaScript
 * Consolidates inline scripts from various templates
 */

(function() {
    const cache = new Map();
    const waiting = new Map();
    let scheduled = false;

    function addAnchor(anchor) {
        if (!(anchor instanceof HTMLAnchorElement) || anchor.closest('[contenteditable="true"]')) return;
        const href = (anchor.getAttribute('href') || '').trim();
        const label = anchor.textContent.trim();
        if (!href || (label !== href && label !== anchor.href)) return;

        let url;
        try {
            url = new URL(anchor.href, window.location.href);
        } catch (_) {
            return;
        }
        if (!['http:', 'https:'].includes(url.protocol) || url.host !== window.location.host) return;

        const key = url.href;
        if (cache.has(key)) {
            const title = cache.get(key);
            if (title) anchor.textContent = title;
            return;
        }
        if (!waiting.has(key)) waiting.set(key, new Set());
        waiting.get(key).add(anchor);
        schedule();
    }

    function scan(root) {
        if (!(root instanceof Element)) return;
        if (root.matches('a')) addAnchor(root);
        root.querySelectorAll('a').forEach(addAnchor);
    }

    function schedule() {
        if (scheduled) return;
        scheduled = true;
        setTimeout(flush, 0);
    }

    function flush() {
        scheduled = false;
        const batch = new Map(Array.from(waiting.entries()).slice(0, 50));
        batch.forEach((_, url) => waiting.delete(url));
        if (!batch.size) return;

        fetch(window.LINK_TITLES_URL || '/link-titles/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': window.LINK_TITLES_CSRF_TOKEN || '',
            },
            body: JSON.stringify({ urls: Array.from(batch.keys()) }),
        }).then(function(response) {
            if (!response.ok) throw new Error('Link title request failed');
            return response.json();
        }).then(function(data) {
            const titles = data.titles || {};
            batch.forEach(function(anchors, url) {
                const title = titles[url] || null;
                cache.set(url, title);
                if (title) anchors.forEach(function(anchor) {
                    if (anchor.isConnected) anchor.textContent = title;
                });
            });
        }).catch(function() {
            return null;
        }).finally(function() {
            if (waiting.size) schedule();
        });
    }

    window.initLocalLinkTitles = function(root) {
        scan(root);
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                mutation.addedNodes.forEach(function(node) {
                    if (node instanceof Element) scan(node);
                });
            });
        });
        observer.observe(root, { childList: true, subtree: true });
        return observer;
    };

    document.addEventListener('DOMContentLoaded', function() {
        const main = document.querySelector('main');
        if (main) window.initLocalLinkTitles(main);
    });
})();

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
    const themeMedia = window.matchMedia('(prefers-color-scheme: dark)');
    function resolveTheme(pref) {
        return pref === 'auto' ? (themeMedia.matches ? 'dark' : 'light') : pref;
    }
    window.applyTheme = function applyTheme(pref) {
        localStorage.setItem('app-theme', pref);
        document.documentElement.setAttribute('data-theme', resolveTheme(pref));
    }
    // Preferencja 'auto' podąża za zmianą motywu systemu operacyjnego.
    themeMedia.addEventListener('change', function() {
        if ((localStorage.getItem('app-theme') || 'auto') === 'auto') applyTheme('auto');
    });

    const btn = document.getElementById('theme-toggle-btn');
    if (btn) {
        btn.addEventListener('click', function() {
            applyTheme(document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
        });
    }
});

document.addEventListener('DOMContentLoaded', function() {
    /* ── nawigacja kafelków do szczegółów ── */
    document.addEventListener('click', function(e) {
        if (e.target.closest('a, button')) return;
        var card = e.target.closest('[data-detail-url]');
        if (!card) return;
        window.location.href = card.dataset.detailUrl;
    });
    document.addEventListener('keydown', function(e) {
        if (e.key !== 'Enter' && e.key !== ' ') return;
        var card = document.activeElement.closest('[data-detail-url]');
        if (!card) return;
        e.preventDefault();
        window.location.href = card.dataset.detailUrl;
    });
});

// ============================================================
// PagePrefs — globalny system zapamiętywania ustawień strony
// ------------------------------------------------------------
// Per-scope JSON w localStorage: { view, filters, tab }
//   - scope ustawia szablon przez `data-prefs-scope` na <html>
//   - tasks używa jednego scope 'tasks'; zakładka i kategoria trzymane są w 'filters'
//   - dla glosowan scope jest wzbogacany o podstronę (glosowania:proposition)
//   - filtry (URL params) restore'owane są w head-script (anti-FOUC)
//   - widok lista/grid/compact: data-view="list|grid|compact" + [data-view-container]
//   - tab persistence: Bootstrap tabs auto-wired
// ============================================================
(function() {
    'use strict';

    var KEY_PREFIX = 'wikikracja:prefs:';

    function baseScope() {
        return document.documentElement.dataset.prefsScope || '';
    }

    function scope() {
        var base = baseScope();
        if (!base) return '';
        var multiPage = ['glosowania', 'bookkeeping', 'obywatele'];
        if (multiPage.indexOf(base) !== -1) {
            var pathParts = window.location.pathname.split('/').filter(Boolean);
            var subpage = pathParts[pathParts.length - 1] || '';
            if (subpage && subpage !== base) return base + ':' + subpage;
        }
        return base;
    }

    function read(scopeName) {
        var s = scopeName || scope();
        if (!s) return {};
        try { return JSON.parse(localStorage.getItem(KEY_PREFIX + s) || '{}'); }
        catch (e) { return {}; }
    }

    function writeTo(scopeName, patch) {
        if (!scopeName) return;
        var data = Object.assign(read(scopeName), patch);
        localStorage.setItem(KEY_PREFIX + scopeName, JSON.stringify(data));
    }

    function write(patch) {
        writeTo(scope(), patch);
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

        // Show/hide view-specific sections (used by events and other atypical views)
        var viewOnlyEls = container.querySelectorAll('[data-view-only]');
        if (viewOnlyEls.length) {
            viewOnlyEls.forEach(function(el) {
                var show = el.dataset.viewOnly === mode;
                el.style.display = show ? '' : 'none';
                if (show) {
                    if (mode === 'grid') el.classList.add('view-grid');
                    else if (mode === 'compact') el.classList.add('view-compact');
                } else {
                    el.classList.remove('view-grid', 'view-compact');
                }
            });
        }
    }

    function setView(mode) {
        applyView(mode);
        var data = read();
        var tab = new URLSearchParams(window.location.search).get('tab');
        if (tab) {
            var views = data.views || {};
            views[tab] = mode;
            write({ view: mode, views: views });
        } else {
            write({ view: mode });
        }
    }

    function saveCurrentFilters() {
        var s = scope();
        var b = baseScope();
        if (!s || !b) return;
        var filters = window.location.search;
        if (filters) write({ filters: filters });
        if (s !== b || filters) writeTo(b, { lastUrl: window.location.pathname + filters });
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

        // 1. Widok lista/grid/compact per zakładka, fallback na globalny view
        var data = read();
        var tab = new URLSearchParams(window.location.search).get('tab');
        var savedView = (tab && data.views && data.views[tab]) || data.view || 'list';
        var availableViews = Array.from(document.querySelectorAll('[data-view]')).map(function(b) { return b.dataset.view; });
        if (availableViews.length && availableViews.indexOf(savedView) === -1) {
            savedView = availableViews[0];
        }
        applyView(savedView);

        // 2. Zapisz aktualny URL (gdy ma params — pokrywa reload, klik linka sortowania)
        saveCurrentFilters();

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

    function patchSidebarLinks() {
        document.querySelectorAll('[data-prefs-link-scope]').forEach(function(link) {
            var scopeName = link.dataset.prefsLinkScope;
            if (!scopeName) return;
            var data = read(scopeName);
            if (data && data.lastUrl) {
                link.setAttribute('href', data.lastUrl);
                return;
            }
            if (!data || !data.filters || data.filters === '?') return;
            var filters = data.filters;
            if (filters.charAt(0) !== '?') return;
            var base = link.dataset.prefsBaseHref || link.getAttribute('href') || '';
            if (!base || base.indexOf('?') !== -1) return;
            link.setAttribute('href', base + filters);
        });
    }

    migrateLegacyKeys();

    window.PagePrefs = {
        init: init,
        setView: setView,
        applyView: applyView,
        read: read,
        write: write,
        clear: clear,
        saveCurrentFilters: saveCurrentFilters,
        patchSidebarLinks: patchSidebarLinks
    };

    document.addEventListener('DOMContentLoaded', init);
    document.addEventListener('DOMContentLoaded', patchSidebarLinks);
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
        const sidebar = document.getElementById('sidebar');
        const toggle = document.getElementById('sidebar-toggle');
        const overlay = document.getElementById('sidebar-overlay');
        const closeBtn = document.getElementById('sidebar-close-btn');

        function setSidebarOpen(open) {
            if (sidebar) sidebar.classList.toggle('sidebar-open', open);
            if (overlay) overlay.style.display = open ? 'block' : 'none';
        }

        if (toggle) {
            toggle.addEventListener('click', function() {
                const willOpen = sidebar && !sidebar.classList.contains('sidebar-open');
                setSidebarOpen(!!willOpen);
            });
        }

        if (closeBtn) {
            closeBtn.addEventListener('click', function() {
                setSidebarOpen(false);
            });
        }

        if (overlay) {
            overlay.addEventListener('click', function() {
                setSidebarOpen(false);
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

// Live countdown for surveys — updates [data-countdown] every second.
document.addEventListener('DOMContentLoaded', function () {
    var elements = document.querySelectorAll('[data-countdown]');
    if (!elements.length) return;

    function formatRemaining(ms) {
        var totalSeconds = Math.max(0, Math.floor(ms / 1000));
        var days = Math.floor(totalSeconds / 86400);
        var hours = Math.floor((totalSeconds % 86400) / 3600);
        var minutes = Math.floor((totalSeconds % 3600) / 60);
        var seconds = totalSeconds % 60;
        var parts = [];
        if (days > 0) {
            parts.push(days + ' ' + (days === 1 ? 'dzień' : 'dni'));
        }
        parts.push(
            String(hours).padStart(2, '0') + ':' +
            String(minutes).padStart(2, '0') + ':' +
            String(seconds).padStart(2, '0')
        );
        return parts.join(' ');
    }

    function update() {
        var now = Date.now();
        elements.forEach(function (el) {
            var end = new Date(el.dataset.end.replace(/\.\d+/, '')).getTime();
            var remaining = end - now;
            if (remaining <= 0) {
                el.textContent = '00:00:00';
            } else {
                el.textContent = formatRemaining(remaining);
            }
        });
    }

    update();
    setInterval(update, 1000);
});

// Apply CSS custom properties from data-* attributes (avoids inline styles in HTML)
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-progress]').forEach(function (el) {
        el.style.setProperty('--progress', el.dataset.progress + '%');
    });
});

// ============================================================
// Quick links read-state (home page onboarding card)
// ============================================================
document.addEventListener('DOMContentLoaded', function () {
    var STORAGE_KEY = 'quick_links_read';
    var circles = document.querySelectorAll('.quick-link-circle');
    if (!circles.length) return;

    function getReadLinks() {
        try {
            var stored = localStorage.getItem(STORAGE_KEY);
            return stored ? JSON.parse(stored) : [];
        } catch (e) { return []; }
    }

    function saveReadLinks(readLinks) {
        try { localStorage.setItem(STORAGE_KEY, JSON.stringify(readLinks)); } catch (e) {}
    }

    function toggleReadStatus(linkId) {
        var readLinks = getReadLinks();
        var index = readLinks.indexOf(linkId);
        if (index > -1) readLinks.splice(index, 1);
        else readLinks.push(linkId);
        saveReadLinks(readLinks);
        return readLinks;
    }

    function updateUI(readLinks) {
        var total = document.querySelectorAll('.quick-link-row').length;
        var done = readLinks.length;

        document.querySelectorAll('.quick-link-row').forEach(function (row) {
            var circle = row.querySelector('.quick-link-circle');
            if (!circle) return;
            var linkId = parseInt(circle.dataset.linkId);
            var isRead = readLinks.indexOf(linkId) !== -1;

            row.classList.toggle('is-read', isRead);
            circle.classList.toggle('is-read', isRead);
            circle.classList.toggle('fas', isRead);
            circle.classList.toggle('fa-check-circle', isRead);
            circle.classList.toggle('far', !isRead);
            circle.classList.toggle('fa-circle', !isRead);
        });

        var bar = document.querySelector('#onboarding-card .progress-bar');
        var label = document.querySelector('#onboarding-card .progress-label');
        if (bar) bar.dataset.progress = Math.round(done / total * 100);
        if (label) label.textContent = done + '/' + total;
    }

    var readLinks = getReadLinks();
    updateUI(readLinks);

    circles.forEach(function (circle) {
        circle.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            var linkId = parseInt(circle.dataset.linkId);
            updateUI(toggleReadStatus(linkId));
        });
    });

    document.querySelectorAll('.quick-link-row a').forEach(function (link) {
        link.addEventListener('mousedown', function () {
            var row = link.closest('.quick-link-row');
            if (!row) return;
            var circle = row.querySelector('.quick-link-circle');
            if (!circle) return;
            var linkId = parseInt(circle.dataset.linkId);
            if (getReadLinks().indexOf(linkId) === -1) {
                updateUI(toggleReadStatus(linkId));
            }
        });
    });
});

// Shared chip filter logic for search/ and activity/ pages.
// Options: formId, storageKey, queryInputId, submitOnlyWithQuery, restore
window.initChipFilters = function(options) {
    options = options || {};
    var form = document.getElementById(options.formId);
    if (!form) return;

    var allBtn = form.querySelector('#sp-select-all');
    var cbs = form.querySelectorAll('.sp-cb:not([value="all"])');
    var qInput = options.queryInputId ? document.getElementById(options.queryInputId) : null;
    var restore = options.restore !== false;

    function setChip(cb, on) {
        cb.checked = on;
        var chip = cb.closest('.sp-chip');
        if (chip) {
            if (on) chip.classList.add('on');
            else chip.classList.remove('on');
        }
    }

    function syncSelectAll() {
        if (!allBtn) return;
        var allChecked = Array.prototype.every.call(cbs, function (cb) { return cb.checked; });
        setChip(allBtn.querySelector('.sp-cb'), allChecked);
    }

    function currentValues() {
        return Array.prototype.filter.call(cbs, function (cb) { return cb.checked; })
                                  .map(function (cb) { return cb.value; });
    }

    function saveValues() {
        if (!options.storageKey) return;
        try { localStorage.setItem(options.storageKey, JSON.stringify(currentValues())); } catch (e) { /* storage unavailable */ }
    }

    function loadValues() {
        if (!options.storageKey) return null;
        try { return JSON.parse(localStorage.getItem(options.storageKey)); } catch (e) { return null; }
    }

    function submitForm() {
        if (typeof form.requestSubmit === 'function') {
            form.requestSubmit();
        } else {
            form.submit();
        }
    }

    function shouldAutoSubmit() {
        return !options.submitOnlyWithQuery || (qInput && qInput.value.trim());
    }

    function tryAutoSubmit() {
        if (shouldAutoSubmit()) setTimeout(submitForm, 80);
    }

    if (allBtn) {
        allBtn.addEventListener('change', function () {
            var allCb = allBtn.querySelector('.sp-cb');
            var on = allCb.checked;
            setChip(allCb, on);
            cbs.forEach(function (cb) { setChip(cb, on); });
            saveValues();
            tryAutoSubmit();
        });
    }

    cbs.forEach(function (cb) {
        cb.addEventListener('change', function () {
            setChip(cb, cb.checked);
            syncSelectAll();
            saveValues();
            tryAutoSubmit();
        });
    });

    if (qInput && window.WK_SEARCH_KEYS) {
        form.addEventListener('submit', function () {
            try {
                var v = qInput.value.trim();
                if (v) localStorage.setItem(window.WK_SEARCH_KEYS.QUERY, v);
                else localStorage.removeItem(window.WK_SEARCH_KEYS.QUERY);
            } catch (e) { /* storage unavailable */ }
        });
    }

    if (restore && options.storageKey) {
        (function restoreFromStorage() {
            if (new URLSearchParams(window.location.search).has('filtered')) return;

            var changed = false;
            var stored = loadValues();
            if (Array.isArray(stored) && stored.length <= cbs.length) {
                cbs.forEach(function (cb) { setChip(cb, stored.indexOf(cb.value) !== -1); });
                syncSelectAll();
                changed = true;
            }

            if (qInput && !qInput.value.trim() && window.WK_SEARCH_KEYS) {
                try {
                    var storedQuery = localStorage.getItem(window.WK_SEARCH_KEYS.QUERY);
                    if (storedQuery) { qInput.value = storedQuery; changed = true; }
                } catch (e) { /* storage unavailable */ }
            }

            if (changed && shouldAutoSubmit()) tryAutoSubmit();
        })();
    }

    syncSelectAll();
};

// ============================================================
// Shared category dropdown filter (tasks + board)
// ============================================================
window.initCategoryFilter = function(options) {
    options = options || {};
    var filterEl = document.getElementById(options.filterId || 'catFilter');
    if (!filterEl) return;

    var btn = document.getElementById('catFilterBtn');
    var panel = document.getElementById('catFilterPanel');
    var labelEl = document.getElementById('catFilterLabel');
    var allRow = document.getElementById('catAllRow');
    var manageBtn = document.getElementById('catManageBtn');
    if (!btn || !panel || !labelEl || !allRow) return;

    var catRows = Array.from(panel.querySelectorAll('.cat-filter__item:not(.cat-filter__all)'));

    var itemsSelector = options.itemsSelector;
    if (!itemsSelector) {
        if (document.querySelector('.task-card[data-category]')) {
            itemsSelector = '.task-card[data-category]';
        } else if (document.querySelector('.proposal-card[data-category]')) {
            itemsSelector = '.proposal-card[data-category]';
        } else if (document.querySelector('.board-category-group[data-category-pk]')) {
            itemsSelector = '.board-category-group[data-category-pk]';
        }
    }
    var items = [];
    var sections = [];
    if (itemsSelector) {
        items = Array.from(document.querySelectorAll(itemsSelector));
        var sectionSelector = options.sectionSelector;
        if (!sectionSelector) {
            if (itemsSelector.indexOf('task-card') !== -1 || itemsSelector.indexOf('proposal-card') !== -1) {
                sectionSelector = '.tasks-section-label';
            }
        }
        if (sectionSelector) sections = Array.from(document.querySelectorAll(sectionSelector));
    }
    var LABEL_ALL = labelEl.textContent;

    var pageScope = document.documentElement.dataset.prefsScope || '';
    var reloadOnChange = options.reloadOnChange || pageScope === 'tasks';
    var onNavigate = options.onNavigate;

    function selected() {
        return catRows.filter(function(r) { return r.classList.contains('selected'); })
                      .map(function(r) { return r.dataset.key; });
    }

    function updateUI() {
        var sel = selected();
        var all = sel.length === 0;

        allRow.classList.toggle('selected', all);

        items.forEach(function(item) {
            var key = item.dataset.category || item.dataset.categoryPk || '';
            item.style.display = (all || sel.indexOf(String(key)) !== -1) ? '' : 'none';
        });

        sections.forEach(function(label) {
            var sib = label.nextElementSibling;
            var vis = false;
            while (sib && !sib.classList.contains('tasks-section-label')) {
                if (sib.matches(itemsSelector) && sib.style.display !== 'none') { vis = true; break; }
                sib = sib.nextElementSibling;
            }
            label.style.display = vis ? '' : 'none';
        });

        if (all) {
            labelEl.textContent = LABEL_ALL;
            btn.classList.remove('active');
        } else {
            labelEl.textContent = LABEL_ALL + ' (' + sel.length + ')';
            btn.classList.add('active');
        }
    }

    function buildCategoryUrl(sel) {
        var p = new URLSearchParams(window.location.search);
        p.delete('category');
        sel.forEach(function(v) { p.append('category', v); });
        return window.location.pathname + (p.toString() ? '?' + p.toString() : '');
    }

    function updateTaskPageLinks() {
        var params = new URLSearchParams(window.location.search);
        var categories = params.getAll('category');
        var sort = params.get('sort');
        var order = params.get('order');

        function refresh(link, updateSortOrder) {
            var u = new URL(link.href, window.location.href);
            var tab = u.searchParams.get('tab');
            var linkSort = u.searchParams.get('sort');
            var linkOrder = u.searchParams.get('order');
            u.searchParams.delete('category');
            u.searchParams.delete('tab');
            u.searchParams.delete('sort');
            u.searchParams.delete('order');
            categories.forEach(function(c) { u.searchParams.append('category', c); });
            if (tab) u.searchParams.set('tab', tab);
            if (updateSortOrder) {
                if (sort) u.searchParams.set('sort', sort);
                if (order) u.searchParams.set('order', order);
            } else {
                if (linkSort) u.searchParams.set('sort', linkSort);
                if (linkOrder) u.searchParams.set('order', linkOrder);
            }
            link.href = u.pathname + u.search;
        }

        document.querySelectorAll('.stepper-nav a[href]').forEach(function(link) { refresh(link, true); });
        document.querySelectorAll('.proposals-toolbar .sort-btn[href]').forEach(function(link) { refresh(link, false); });
    }

    function fetchTasksList(url) {
        var container = document.getElementById('tasks-list-container');
        if (!container) {
            window.location.href = url;
            return;
        }
        if (typeof sessionStorage !== 'undefined') sessionStorage.setItem('catFilterOpen', '1');
        fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(function(r) { if (!r.ok) throw new Error('fetch failed'); return r.text(); })
            .then(function(html) {
                container.innerHTML = html;
                history.pushState(null, '', url);
                if (typeof window.reinitTaskCards === 'function') window.reinitTaskCards();
                updateTaskPageLinks();
                if (typeof window.PagePrefs !== 'undefined' && typeof window.PagePrefs.applyView === 'function') {
                    var currentTab = new URLSearchParams(window.location.search).get('tab') || 'mine';
                    var p = window.PagePrefs.read();
                    window.PagePrefs.applyView((p.views && p.views[currentTab]) || p.view || 'list');
                }
                if (typeof window.PagePrefs !== 'undefined' && typeof window.PagePrefs.saveCurrentFilters === 'function') {
                    window.PagePrefs.saveCurrentFilters();
                }
            })
            .catch(function() { window.location.href = url; });
    }

    function updateHistory(reload) {
        var sel = selected();
        var url = buildCategoryUrl(sel);

        if (url === window.location.pathname + window.location.search) return;

        if (reload) {
            // Save the new filter string before leaving so the next load/redirect uses it.
            if (window.PagePrefs && typeof window.PagePrefs.write === 'function') {
                window.PagePrefs.write({ filters: url.slice(window.location.pathname.length) });
            }
            if (typeof onNavigate === 'function') { onNavigate(url); }
            else if (pageScope === 'tasks') { fetchTasksList(url); }
            else {
                if (typeof sessionStorage !== 'undefined') sessionStorage.setItem('catFilterOpen', '1');
                window.location.href = url;
            }
        } else {
            history.pushState(null, '', url);
        }
    }

    // restore from URL
    var params = new URLSearchParams(window.location.search);
    var initial = params.getAll('category');
    initial.forEach(function(val) {
        catRows.forEach(function(row) {
            if (String(row.dataset.key) === String(val)) row.classList.add('selected');
        });
    });

    panel.addEventListener('click', function(e) { e.stopPropagation(); });

    allRow.addEventListener('click', function() {
        catRows.forEach(function(r) { r.classList.remove('selected'); });
        updateUI();
        updateHistory(reloadOnChange);
    });

    catRows.forEach(function(row) {
        row.addEventListener('click', function() {
            row.classList.toggle('selected');
            updateUI();
            updateHistory(reloadOnChange);
        });
    });

    btn.addEventListener('click', function(e) {
        e.stopPropagation();
        var opening = panel.hidden;
        panel.hidden = !opening;
        btn.setAttribute('aria-expanded', String(opening));
    });

    document.addEventListener('click', function(e) {
        if (!filterEl.contains(e.target)) {
            panel.hidden = true;
            btn.setAttribute('aria-expanded', 'false');
        }
    });

    if (manageBtn) {
        manageBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            panel.hidden = true;
            btn.setAttribute('aria-expanded', 'false');
            var modal = document.getElementById('manageCategoriesModal');
            if (modal && typeof bootstrap !== 'undefined') {
                new bootstrap.Modal(modal).show();
            }
        });
    }

    // Reopen the panel after a category-driven reload (tasks) so multi-select is easier.
    if (typeof sessionStorage !== 'undefined' && sessionStorage.getItem('catFilterOpen') === '1') {
        panel.hidden = false;
        btn.setAttribute('aria-expanded', 'true');
        sessionStorage.removeItem('catFilterOpen');
    }

    updateUI();
};

document.addEventListener('DOMContentLoaded', function() {
    window.initCategoryFilter();
});

// ============================================================
// Toggle argument form visibility (voting details)
// ============================================================
window.toggleArgForm = function toggleArgForm(id) {
    var el = document.getElementById(id);
    if (!el) return;
    el.classList.toggle('visible');
    if (el.classList.contains('visible')) {
        var ta = el.querySelector('textarea');
        if (ta) ta.focus();
    }
};

// ============================================================
// Citizen profile section toggles (lazy-loaded via AJAX)
// ============================================================
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.citizen-section-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var targetId = btn.dataset.target;
            var section = document.getElementById(targetId);
            if (!section) return;
            var isOpen = section.style.display !== 'none';
            document.querySelectorAll('.citizen-section').forEach(function (s) { s.style.display = 'none'; });
            document.querySelectorAll('.citizen-section-btn').forEach(function (b) { b.classList.remove('active'); });
            if (isOpen) return;
            btn.classList.add('active');
            if (section.dataset.loaded) {
                section.style.display = 'block';
                return;
            }
            section.innerHTML = '<div class="p-3 text-muted text-sm">...</div>';
            section.style.display = 'block';
            fetch(btn.dataset.url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
                .then(function (r) { return r.text(); })
                .then(function (html) {
                    section.innerHTML = html;
                    section.dataset.loaded = '1';
                });
        });
    });

    // Open the default section (Tasks) automatically when the profile loads.
    var defaultBtn = document.querySelector('.citizen-section-btn[data-default="true"]')
                     || document.querySelector('.citizen-section-btn');
    if (defaultBtn) defaultBtn.click();
});

// ============================================================
// Clickable table rows (data-href)
// ============================================================
document.addEventListener('click', function (e) {
    var tr = e.target.closest('.table-hover-rows tbody tr[data-href]');
    if (tr && !e.target.closest('a')) window.location = tr.dataset.href;
});

// ============================================================
// Trim activity feed rows to fit card height (home + activity widgets)
// ============================================================
document.addEventListener('DOMContentLoaded', function () {
    var body = document.getElementById('activity-feed-body');
    if (!body) return;

    function trimActivityFeed() {
        var card = body.closest('.card');
        if (!card) return;
        var rows = body.querySelectorAll('.activity-feed-row');
        var more = document.getElementById('activity-feed-more');
        if (!rows.length) return;
        rows.forEach(function (r) { r.style.display = ''; });
        if (more) more.style.display = 'none';
        var cardH = card.clientHeight;
        var header = card.querySelector('.card-header');
        var headerH = header ? header.offsetHeight : 0;
        var available = cardH - headerH;
        var used = 0;
        var hidden = false;
        var moreH = 20;
        for (var i = 0; i < rows.length; i++) {
            var rowH = rows[i].offsetHeight;
            var remaining = rows.length - i - 1;
            var needMore = remaining > 0;
            if (used + rowH + (needMore ? moreH : 0) <= available) {
                used += rowH;
            } else {
                rows[i].style.display = 'none';
                hidden = true;
                for (var j = i + 1; j < rows.length; j++) rows[j].style.display = 'none';
                break;
            }
        }
        if (more) more.style.display = hidden ? 'block' : 'none';
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', trimActivityFeed);
    } else {
        trimActivityFeed();
    }
    window.addEventListener('resize', trimActivityFeed);
});

// ============================================================
// Survey vote withdrawal — clear selected options and submit
// ============================================================
document.addEventListener('click', function(e) {
    var withdrawBtn = e.target.closest('[data-withdraw-vote]');
    if (!withdrawBtn) return;
    e.preventDefault();
    var form = withdrawBtn.closest('form');
    if (!form) return;
    form.querySelectorAll('input[name="option"]').forEach(function(input) {
        input.checked = false;
    });
    form.submit();
});

// ============================================================
// File upload size validation
// ============================================================
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('input[type="file"][data-max-size-mb]').forEach(function(input) {
        input.addEventListener('change', function() {
            var maxSizeMb = parseInt(input.dataset.maxSizeMb, 10);
            var errorTemplate = input.dataset.maxSizeError || 'File is too large (max %s MB).';
            var maxSizeBytes = maxSizeMb * 1000000;
            var invalidFiles = [];
            for (var i = 0; i < input.files.length; i++) {
                if (input.files[i].size > maxSizeBytes) {
                    invalidFiles.push(input.files[i].name);
                }
            }
            if (invalidFiles.length > 0) {
                var message = errorTemplate.replace('%s', maxSizeMb);
                if (window.showToast) {
                    window.showToast(message);
                } else {
                    alert(message);
                }
                input.value = '';
                input.classList.add('is-invalid');
            } else {
                input.classList.remove('is-invalid');
            }
        });
    });
});