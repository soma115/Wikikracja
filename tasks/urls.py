from django.urls import path

from . import views

app_name = "tasks"

urlpatterns = [
    path("", views.TaskListView.as_view(), name="list"),
    path("help/", views.TaskHelpView.as_view(), name="help"),
    path("stats/", views.TaskStatsView.as_view(), name="stats"),
    path("add/", views.TaskCreateView.as_view(), name="add"),
    path("<int:pk>/", views.TaskDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.TaskEditView.as_view(), name="edit"),
    path("<int:pk>/close/", views.TaskCloseView.as_view(), name="close"),
    path("<int:pk>/delete/", views.delete_task, name="delete"),
    path("<int:pk>/reopen/", views.reopen_task, name="reopen"),
    path("<int:pk>/resign/", views.resign_task, name="resign"),
    path("<int:pk>/take/", views.take_task, name="take"),
    path("<int:pk>/vote/", views.vote_task, name="vote"),
    path("<int:pk>/helpers.json", views.task_helpers_json, name="helpers_json"),
    path("<int:pk>/against.json", views.task_against_json, name="against_json"),
    path("<int:pk>/evaluate/", views.evaluate_task, name="evaluate"),
    path("api/categories/", views.TaskCategoryAPI.as_view(), name="api_categories"),
    path("api/categories/reorder/", views.TaskCategoryReorderAPI.as_view(), name="api_category_reorder"),
    path("api/categories/<int:pk>/edit/", views.TaskCategoryEditAPI.as_view(), name="api_category_edit"),
    path("api/categories/<int:pk>/delete/", views.TaskCategoryDeleteAPI.as_view(), name="api_category_delete"),
]
