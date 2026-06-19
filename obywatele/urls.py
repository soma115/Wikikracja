from django.contrib.auth.decorators import login_required
from django.urls import path

from obywatele import views as v

app_name = 'obywatele'

urlpatterns = (
    path('', v.obywatele, name='obywatele'),
    path('onboarding/', v.onboarding_details, name='onboarding_details'),
    path('onboarding/waiting/', v.onboarding_waiting, name='onboarding_waiting'),
    path('poczekalnia/', v.poczekalnia, name='poczekalnia'),
    path('poczekalnia/<int:pk>/', v.obywatele_szczegoly, name='poczekalnia_szczegoly'),
    path('poczekalnia/<int:pk>/edit/', v.candidate_edit, name='candidate_edit'),
    path('<int:pk>/', v.obywatele_szczegoly, name='obywatele_szczegoly'),
    path('<int:pk>/czaty/', v.citizen_czaty, name='citizen_czaty'),
    path('<int:pk>/zadania/', v.citizen_zadania, name='citizen_zadania'),
    path('<int:pk>/aktywnosc/', v.citizen_aktywnosc, name='citizen_aktywnosc'),
    path('<int:pk>/zalozono/', v.citizen_zalozono, name='citizen_zalozono'),
    path('settings/', v.my_profile, name='my_profile'),
    path('settings/avatar/', v.upload_avatar, name='upload_avatar'),
    path('settings/language/', v.set_user_language, name='set_language'),
    path('toggle_notification/', v.toggle_notification, name='toggle_notification'),
    path('my_assets/', v.my_assets, name='my_assets'),
    path('nowy/', v.dodaj, name='zaproponuj_osobe'),
    path('change_username/', v.change_username, name='change_username'),
    path('change_email/', v.change_email, name='change_email'),
    path("assets/", login_required(v.AssetListView.as_view()), name='assets'),
    path('parameters/', v.parameters, name='parameters'),
    path('wspolnota/', v.wspolnota, name='wspolnota'),
    path('wspolnota/calendar/', v.wspolnota_calendar, name='wspolnota_calendar'),
    path('settings/delete/', v.request_deletion, name='request_deletion'),
    path('settings/delete/cancel/', v.cancel_deletion, name='cancel_deletion'),
)
