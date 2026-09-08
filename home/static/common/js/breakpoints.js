/**
 * Jedno źródło breakpointu mobile — musi odpowiadać
 * `@media (max-width: 767.98px)` w home/static/home/css/tailwind.css.
 * Skrypt klasyczny ładowany przed modułami ES: dostępny jako
 * `window.wkMobileMedia` dla app.js i reeksportowany przez chat/utility.js.
 * Fallback bez matchMedia dotyczy tylko środowisk testowych (jsdom).
 */
window.wkMobileMedia = typeof window.matchMedia === 'function'
    ? window.matchMedia('(max-width: 767.98px)')
    : { matches: false, addEventListener() {}, removeEventListener() {} };
