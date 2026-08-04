from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import HttpResponsePermanentRedirect
from django.utils import timezone, translation

User = get_user_model()


class CanonicalDomainMiddleware:
    """
    Przekierowuje (301) kazdy request, ktorego host znajduje sie na scisle
    okreslonej liscie DOMAIN_ALIASES, na glowna domene SITE_DOMAIN.

    Bez regex - dopasowanie po dokladnej nazwie hosta. Sciezka, query string
    i scheme sa zachowane.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.site_domain = getattr(settings, "SITE_DOMAIN", "")
        self.aliases = set(getattr(settings, "DOMAIN_ALIASES", []))

    def __call__(self, request):
        if self.site_domain and self.aliases:
            host = request.get_host().split(":")[0]
            if host in self.aliases:
                target = f"{request.scheme}://{self.site_domain}{request.get_full_path()}"
                response = HttpResponsePermanentRedirect(target)
                # Empty body + explicit Content-Length stops daphne from using
                # Transfer-Encoding: chunked, which Traefik rejects (HTTP 500)
                # when proxying a 3xx response over HTTP/2.
                response.content = b""
                response["Content-Length"] = "0"
                return response
        return self.get_response(request)


class UserLanguageMiddleware:
    """
    Activates the language saved in the user's profile (Uzytkownik.language).
    Runs after LocaleMiddleware so it can override the auto-detected language
    for authenticated users who have set an explicit preference.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                lang = request.user.uzytkownik.language
                if lang:
                    translation.activate(lang)
                    request.LANGUAGE_CODE = lang
            except Exception:
                pass
        return self.get_response(request)


class UpdateLastSeenMiddleware:
    """
    Aktualizuje user.last_login przy kazdym requescie zalogowanego usera,
    ale max raz na 5 min (throttling przez cache).

    Django domyslnie aktualizuje last_login tylko przy formalnym logowaniu
    (signal user_logged_in). Przy dlugich sesjach (SESSION_COOKIE_AGE = 90 dni)
    pole przestaje odzwierciedlac rzeczywista aktywnosc - middleware to naprawia.

    is_active jest sprawdzane, bo Django nie uniewaznia sesji po deaktywacji
    konta - user z is_active=False moze nadal miec aktywna sesje, a jego
    aktualizacje odraczalyby usuniecie przez count_citizens.delete_inactive_users().
    """
    THROTTLE_SECONDS = 300

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.user.is_active:
            try:
                cache_key = f'last_seen:{request.user.pk}'
                # cache.add jest atomic - chroni przed race condition gdy dwa
                # rownolegle requesty tego samego usera trafia w pusty klucz.
                if cache.add(cache_key, True, self.THROTTLE_SECONDS):
                    User.objects.filter(pk=request.user.pk).update(last_login=timezone.now())
            except Exception:
                pass
        return self.get_response(request)
