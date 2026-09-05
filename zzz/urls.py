from typing import List

from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.urls import URLPattern, URLResolver, include, path, re_path
from django.views.generic import RedirectView
from django.views.static import serve

from board import views as bv
from home import views as hv
from obywatele import views as ov

urlpatterns: List[URLPattern | URLResolver] = [
    path('', include('home.urls')),
    path('logout/', auth_views.LogoutView.as_view(next_page='/login/'), name='logout'),
    path('login/', RedirectView.as_view(url='/accounts/login/'), name='login'),
    path('haslo/', hv.haslo, name='haslo'),
    path('change_email/', ov.change_email, name='change_email'),
    path('kandydaci/', RedirectView.as_view(url='/obywatele/poczekalnia/'), name='kandydaci'),
    path('accounts/confirm-email/', RedirectView.as_view(url='/obywatele/onboarding/', permanent=False)),
    path('accounts/', include('allauth.urls')),
    path('favicon.ico', RedirectView.as_view(url='/static/home/images/favicon.ico')),  # TODO: robots.txt this way?
    path('captcha/', include('captcha.urls')),
    path('glosowania/', include('glosowania.urls', namespace='glosowania')),
    path('obywatele/', include('obywatele.urls', namespace='obywatele')),
    path('chat/', include('chat.urls', namespace='chat')),
    path('bookkeeping/', include('bookkeeping.urls', namespace='bookkeeping')),
    path('board/', include('board.urls', namespace='board')),
    path('events/', include('events.urls', namespace='events')),
    path('tasks/', include('tasks.urls', namespace='tasks')),
    path('ankiety/', include('ankiety.urls', namespace='ankiety')),
    path('i18n/', include('django.conf.urls.i18n')),
    path('<slug:slug>/', bv.view_post_by_slug, name='board_post_by_slug'),
]

# Serve static files only in DEBUG mode (WhiteNoise handles this in production)
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    if settings.DEBUG_TOOLBAR:
        from debug_toolbar.toolbar import debug_toolbar_urls

        urlpatterns += debug_toolbar_urls()
    urlpatterns += [path("__reload__/", include("django_browser_reload.urls"))]

# Media files (user uploads) - must be served in all environments
# In production, Django will serve these (inefficient but works)
# TODO: Consider adding nginx sidecar for better performance

urlpatterns += [re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT})]
'''
allauth:
Note that you do not necessarily need the URLs provided by django.contrib.auth.urls.
Instead of the URLs login, logout, and password_change (among others),
you can use the URLs provided by allauth: account_login, account_logout, account_set_password…
'''
