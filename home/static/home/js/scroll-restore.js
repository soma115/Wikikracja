// Przywraca pozycję scrolla po przeładowaniu strony wywołanym przez form submit.
// Użycie: dodaj data-preserve-scroll do <form>.
// Dodatkowo: auto-ukrywa toast messages po 4 sekundach.
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('#django-toasts .toast-msg:not(.toast-persist)').forEach(function (el) {
    setTimeout(function () {
      el.style.transition = 'opacity .4s';
      el.style.opacity = '0';
      setTimeout(function () { el.remove(); }, 400);
    }, 4000);
  });
});
(function () {
  var KEY = 'scroll_restore:' + location.pathname;

  // restore po window.load — layout musi być stabilny zanim scrollujemy
  window.addEventListener('load', function () {
    var saved = sessionStorage.getItem(KEY);
    if (saved !== null) {
      sessionStorage.removeItem(KEY);
      window.scrollTo({ top: parseInt(saved, 10), left: 0, behavior: 'instant' });
    }
  });

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('form[data-preserve-scroll]').forEach(function (form) {
      form.addEventListener('submit', function () {
        sessionStorage.setItem(KEY, window.scrollY);
      });
    });
  });
})();
