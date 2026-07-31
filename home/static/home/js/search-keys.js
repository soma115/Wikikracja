/**
 * Shared localStorage key names for the "remember last search" feature.
 * Used by both app.js (topbar search box) and search.html's inline script
 * (search page's own query + category filters), which are separate <script>
 * contexts with no module system between them — this file is the single
 * source of truth so the two never drift apart.
 */
window.WK_SEARCH_KEYS = {
    QUERY: 'wk_last_search_q',
    CATS: 'wk_search_cats'
};
