from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('mark-as-read/', views.mark_as_read, name='mark_as_read'),
    path('mark-all-read/', views.mark_all_read, name='mark_all_read'),
    path('mark-unread/', views.mark_unread, name='mark_unread'),
    path('save-filter-state/', views.save_filter_state, name='save_filter_state'),
    path('aktywnosc/', views.activity_page, name='activity'),
    path('site-settings/', views.site_admin, name='site_admin'),
    path('site-settings/remove-brand-mark/', views.remove_brand_mark, name='remove_brand_mark'),
    path('site-settings/remove-brand-mark-dark/', views.remove_brand_mark_dark, name='remove_brand_mark_dark'),
    path('search/', views.global_search, name='search'),

    # not in use at this point. Contact through https://wikikracja.pl/kontakt/
    # path('contact/', TemplateView.as_view(template_name="home/contact.html"), name='contact'),

    # reset password
    # https://simpleisbetterthancomplex.com/tutorial/2016/09/19/how-to-create-password-reset-view.html
    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='home/password_reset_form.html'), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='home/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='home/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='home/password_reset_complete.html'), name='password_reset_complete'),

    # for generating dynamic manifest content
    path('manifest.json', views.manifest, name='manifest'),

    # Service Worker - serve with correct MIME type
    path('firebase-messaging-sw.js', views.firebase_messaging_sw, name='firebase-messaging-sw'),
    path('dynamic-settings.js', views.dynamic_settings_js, name='dynamic-settings'),
]
