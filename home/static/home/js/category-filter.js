// Shared category dropdown filter (tasks + board)
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

    var catRows = Array.from(panel.querySelectorAll('.tw-cat-filter-item:not(.tw-cat-filter-all)'));

    var itemsSelector = options.itemsSelector;
    if (!itemsSelector) {
        if (document.querySelector('.tw-content-card[data-category]')) {
            itemsSelector = '.tw-content-card[data-category]';
        } else if (document.querySelector('.tw-board-category-group[data-category-pk]')) {
            itemsSelector = '.tw-board-category-group[data-category-pk]';
        }
    }
    var items = [];
    var sections = [];
    if (itemsSelector) {
        items = Array.from(document.querySelectorAll(itemsSelector));
        var sectionSelector = options.sectionSelector;
        if (!sectionSelector) {
            if (itemsSelector.indexOf('tw-content-card') !== -1) {
                sectionSelector = '.tw-tasks-section-label';
            }
        }
        if (sectionSelector) sections = Array.from(document.querySelectorAll(sectionSelector));
    }
    var LABEL_ALL = labelEl.textContent;

    var pageScope = document.documentElement.dataset.prefsScope || '';
    var reloadOnChange = options.reloadOnChange || pageScope === 'tasks';
    var onNavigate = options.onNavigate;

    function selected() {
        return catRows.filter(function(r) { return r.classList.contains('tw-active'); })
                      .map(function(r) { return r.dataset.key; });
    }

    function updateUI() {
        var sel = selected();
        var all = sel.length === 0;

        allRow.classList.toggle('tw-active', all);

        items.forEach(function(item) {
            var key = item.dataset.category || item.dataset.categoryPk || '';
            item.classList.toggle('tw-d-none', !(all || sel.indexOf(String(key)) !== -1));
        });

        sections.forEach(function(label) {
            var sib = label.nextElementSibling;
            var vis = false;
            while (sib && !sib.classList.contains('tw-tasks-section-label')) {
                if (sib.matches(itemsSelector) && !sib.classList.contains('tw-d-none')) { vis = true; break; }
                sib = sib.nextElementSibling;
            }
            label.classList.toggle('tw-d-none', !vis);
        });

        if (all) {
            labelEl.textContent = LABEL_ALL;
            btn.classList.remove('tw-active');
        } else {
            labelEl.textContent = LABEL_ALL + ' (' + sel.length + ')';
            btn.classList.add('tw-active');
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

        document.querySelectorAll('.tw-stepper-nav a[href]').forEach(function(link) { refresh(link, true); });
        document.querySelectorAll('.tw-toolbar .tw-sort-btn[href]').forEach(function(link) { refresh(link, false); });
    }

    function fetchTasksList(url) {
        var container = document.getElementById('tw-tasks-list-container');
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
                window.PagePrefs.write({ lastUrl: url, filters: url.slice(window.location.pathname.length) });
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
            if (String(row.dataset.key) === String(val)) row.classList.add('tw-active');
        });
    });

    panel.addEventListener('click', function(e) { e.stopPropagation(); });

    allRow.addEventListener('click', function() {
        catRows.forEach(function(r) { r.classList.remove('tw-active'); });
        updateUI();
        updateHistory(reloadOnChange);
    });

    catRows.forEach(function(row) {
        row.addEventListener('click', function() {
            row.classList.toggle('tw-active');
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
            if (modal && typeof TwModal !== 'undefined') {
                TwModal.show(modal);
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

window.wkOnReady(function() {
    window.initCategoryFilter();
});
