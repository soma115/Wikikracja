/** @type {import('jest').Config} */
module.exports = {
  testEnvironment: 'jsdom',
  testMatch: ['**/__tests__/**/*.test.js'],
  // Ignoruj root-owy katalog collectstatic (STATIC_ROOT, gitignorowany). Jest
  // kolekcjonowal stale kopie testow z static/ OBOK zrodel <app>/static/..., przez
  // co kazdy test chatu/home lecial 2x — ryzyko falszywego PASS ze starej kopii po
  // edycji testu bez ponownego collectstatic.
  // MUSI byc <rootDir>/static/, NIE samo /static/: goly /static/ (regex bez kotwicy)
  // zlapalby tez zrodla (chat/static/, home/static/ — konwencja static-per-app Django)
  // i wycial WSZYSTKIE testy -> 0 zebranych = gorszy falszywy green.
  testPathIgnorePatterns: ['/node_modules/', '<rootDir>/static/'],
  // Wspolne helpery window.* (escapeHtml, getCSRFToken, apiFetch, debounce,
  // delegaty data-tw-*) — zrodlo: home/static/common/js/dom-utils.js, ladowany
  // w base.html. Testy jsdom laduja moduly bez base.html, wiec helpery trzeba
  // podmienic tu, zeby moduly je widzialy tak jak w przegladarce.
  setupFiles: ['<rootDir>/home/static/common/js/dom-utils.js'],
  transform: {},
};
