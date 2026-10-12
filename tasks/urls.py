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
    path("<int:pk>/start/", views.start_task, name="start"),
    path("<int:pk>/return-to-proposal/", views.return_to_proposal, name="return_to_proposal"),
    path("<int:pk>/subtasks/add/", views.add_subtask, name="subtask_add"),
    path("<int:pk>/subtasks/reorder/", views.reorder_subtasks, name="subtask_reorder"),
    path("<int:pk>/subtasks/<int:subtask_pk>/indent/", views.indent_subtask, name="subtask_indent"),
    path("<int:pk>/subtasks/<int:subtask_pk>/outdent/", views.outdent_subtask, name="subtask_outdent"),
    path("<int:pk>/subtasks/<int:subtask_pk>/edit/", views.edit_subtask, name="subtask_edit"),
    path("<int:pk>/subtasks/<int:subtask_pk>/toggle/", views.toggle_subtask, name="subtask_toggle"),
    path("<int:pk>/subtasks/<int:subtask_pk>/delete/", views.delete_subtask, name="subtask_delete"),
    path("<int:pk>/subtasks/<int:subtask_pk>/move/<str:direction>/", views.move_subtask, name="subtask_move"),
    path("<int:pk>/resign/", views.resign_task, name="resign"),
    path("<int:pk>/take/", views.take_task, name="take"),
    path("<int:pk>/vote/", views.vote_task, name="vote"),
    path("<int:pk>/approve/<int:user_id>/", views.approve_helper, name="approve_helper"),
    path("<int:pk>/remove/<int:user_id>/", views.remove_helper, name="remove_helper"),
    path("<int:pk>/toggle/<int:user_id>/", views.toggle_helper, name="toggle_helper"),
    path("<int:pk>/helpers.json", views.task_helpers_json, name="helpers_json"),
    path("<int:pk>/against.json", views.task_against_json, name="against_json"),
    path("<int:pk>/evaluate/", views.evaluate_task, name="evaluate"),
    path("api/categories/", views.TaskCategoryAPI.as_view(), name="api_categories"),
    path("api/categories/reorder/", views.TaskCategoryReorderAPI.as_view(), name="api_category_reorder"),
    path("api/categories/<int:pk>/edit/", views.TaskCategoryEditAPI.as_view(), name="api_category_edit"),
    path("api/categories/<int:pk>/delete/", views.TaskCategoryDeleteAPI.as_view(), name="api_category_delete"),
]
