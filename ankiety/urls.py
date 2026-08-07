from django.urls import path

from . import views

app_name = "ankiety"

urlpatterns = [
    path("", views.survey_list, name="list"),
    path("dodaj/", views.survey_create, name="create"),
    path("<int:pk>/", views.survey_detail, name="detail"),
    path("<int:pk>/edytuj/", views.survey_edit, name="edit"),
    path("<int:pk>/usun/", views.survey_delete, name="delete"),
]
