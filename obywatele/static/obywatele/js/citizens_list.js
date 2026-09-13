window.wkOnReady(function () {
    let listView;
    let gridView;
    let countEl;
    const searchInput = document.getElementById('citizens-search');
    let refreshTimer;
    let refreshDebounce;
    let refreshInFlight = false;
    let refreshQueued = false;

    const updateReferences = () => {
        listView = document.getElementById('citizens-list-view');
        gridView = document.getElementById('citizens-grid-view');
        countEl = document.getElementById('citizens-count');
    };

    const getActivityFilter = () => new URL(window.location.href).searchParams.get('aktywnosc') || '';
    const hasDynamicFilter = () => ['online', '7d', 'nieaktywni'].includes(getActivityFilter());

    const applySearch = () => {
        const q = searchInput ? searchInput.value.trim().toLowerCase() : '';
        const rows = listView ? listView.querySelectorAll('.tw-user-row') : [];
        const cards = gridView ? gridView.querySelectorAll('.tw-citizen-card') : [];
        let visible = 0;

        rows.forEach(row => {
            const match = !q || row.dataset.search.toLowerCase().includes(q);
            row.classList.toggle('tw-d-none', !match);
            if (match) visible++;
        });
        cards.forEach(card => {
            const match = !q || card.dataset.search.toLowerCase().includes(q);
            card.classList.toggle('tw-d-none', !match);
        });

        if (countEl) countEl.textContent = q ? visible : rows.length;
    };

    const refreshList = async () => {
        if (!hasDynamicFilter()) return;
        if (refreshInFlight) {
            refreshQueued = true;
            return;
        }

        const currentContainer = document.querySelector('[data-view-container]');
        if (!currentContainer) return;
        const viewMode = currentContainer.classList.contains('tw-view-grid') ? 'grid' : 'list';
        const url = new URL(window.location.href);
        url.searchParams.set('partial', '1');
        refreshInFlight = true;

        try {
            const response = await fetch(url, {
                headers: {'X-Requested-With': 'XMLHttpRequest', Accept: 'text/html'},
                credentials: 'same-origin',
            });
            if (!response.ok) return;
            const html = await response.text();
            const documentFragment = new DOMParser().parseFromString(html, 'text/html');
            const nextContainer = documentFragment.querySelector('[data-view-container]');
            const container = document.querySelector('[data-view-container]');
            if (!nextContainer || !container) return;

            container.replaceWith(nextContainer);
            updateReferences();
            applySearch();
            if (window.PagePrefs?.applyView) window.PagePrefs.applyView(viewMode);
        } catch (_) {
        } finally {
            refreshInFlight = false;
            if (refreshQueued) {
                refreshQueued = false;
                window.setTimeout(refreshList, 0);
            }
        }
    };

    const scheduleRefresh = () => {
        if (!hasDynamicFilter()) return;
        window.clearTimeout(refreshDebounce);
        refreshDebounce = window.setTimeout(refreshList, 250);
    };

    const scheduleExpiryRefresh = () => {
        window.clearTimeout(refreshTimer);
        if (!hasDynamicFilter()) return;
        refreshTimer = window.setTimeout(() => {
            refreshList();
            scheduleExpiryRefresh();
        }, 60 * 1000);
    };

    updateReferences();

    // ── Sync filter dropdown → PagePrefs (prevents head-script from restoring old filter) ──
    document.querySelectorAll('[data-citizens-filter-menu] .tw-dropdown-item').forEach(link => {
        link.addEventListener('click', function () {
            if (!window.PagePrefs) return;
            const url = new URL(this.href, window.location.origin);
            const params = url.searchParams.toString();
            window.PagePrefs.write({ filters: params ? '?' + params : '' });
        });
    });

    if (searchInput) searchInput.addEventListener('input', window.debounce(applySearch, 150));

    document.addEventListener('wk:presence-update', scheduleRefresh);
    scheduleExpiryRefresh();
});
