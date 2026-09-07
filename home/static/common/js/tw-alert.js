/**
 * Lightweight Tailwind alert dismiss.
 */
(function () {
  'use strict';

  document.addEventListener('click', function (e) {
    const dismiss = e.target.closest('[data-tw-dismiss="alert"]');
    if (!dismiss) return;
    const alert = dismiss.closest('[role="alert"]');
    if (alert) alert.remove();
  });
})();
