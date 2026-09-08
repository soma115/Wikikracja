document.addEventListener('DOMContentLoaded', function () {
    const listView = document.getElementById('citizens-list-view');
    const gridView = document.getElementById('citizens-grid-view');
    const countEl  = document.getElementById('citizens-count');
    const searchInput = document.getElementById('citizens-search');

    // ── Sync filter dropdown → PagePrefs (prevents head-script from restoring old filter) ──
    document.querySelectorAll('.tw-citizens-toolbar .tw-dropdown-item').forEach(link => {
        link.addEventListener('click', function () {
            if (!window.PagePrefs) return;
            const url = new URL(this.href, window.location.origin);
            const params = url.searchParams.toString();
            window.PagePrefs.write({ filters: params ? '?' + params : '' });
        });
    });

    if (searchInput) {
        searchInput.addEventListener('input', window.debounce(function () {
                const q = this.value.trim().toLowerCase();
                const rows  = listView ? listView.querySelectorAll('.tw-user-row') : [];
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
        }, 150));
    }

});
