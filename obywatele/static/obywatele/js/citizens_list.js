document.addEventListener('DOMContentLoaded', function () {
    const listView = document.getElementById('citizens-list-view');
    const gridView = document.getElementById('citizens-grid-view');
    const countEl  = document.getElementById('citizens-count');
    const searchInput = document.getElementById('citizens-search');

    // ── Sync filter dropdown → PagePrefs (prevents head-script from restoring old filter) ──
    document.querySelectorAll('.citizens-toolbar .tw-dropdown-item').forEach(link => {
        link.addEventListener('click', function () {
            if (!window.PagePrefs) return;
            const url = new URL(this.href, window.location.origin);
            const params = url.searchParams.toString();
            window.PagePrefs.write({ filters: params ? '?' + params : '' });
        });
    });

    if (searchInput) {
        let searchTimer;
        searchInput.addEventListener('input', function () {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => {
                const q = this.value.trim().toLowerCase();
                const rows  = listView ? listView.querySelectorAll('.user-row') : [];
                const cards = gridView ? gridView.querySelectorAll('.citizen-card') : [];
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
            }, 150);
        });
    }

    const rowContainer = listView || document;
    rowContainer.querySelectorAll('.user-row').forEach(row => {
        row.addEventListener('click', function (e) {
            if (!e.target.closest('button, a')) {
                window.location.href = this.dataset.href;
            }
        });
    });

    if (gridView) gridView.querySelectorAll('.citizen-card').forEach(card => {
        card.addEventListener('click', function (e) {
            if (!e.target.closest('button, a')) {
                window.location.href = this.dataset.href;
            }
        });
    });

    document.querySelectorAll('.tw-copy-btn').forEach(button => {
        button.addEventListener('click', function (e) {
            e.stopPropagation();
            navigator.clipboard.writeText(this.dataset.email).then(() => {
                const orig = this.innerHTML;
                this.innerHTML = '<i class="fas fa-check"></i>';
                this.classList.remove('tw-btn-outline-light');
                this.classList.add('tw-btn-success');
                setTimeout(() => {
                    this.innerHTML = orig;
                    this.classList.remove('tw-btn-success');
                    this.classList.add('tw-btn-outline-light');
                }, 1500);
            });
        });
    });
});
