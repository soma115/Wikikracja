import json
import math
from functools import wraps
from urllib.parse import quote_plus

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models, transaction
from django.db.models import Count, Max, Q, Sum
from django.db.models.functions import Coalesce
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, TemplateView, UpdateView

from categories.views import CategoryAPIBase, CategoryDeleteAPI, CategoryEditAPI, CategoryReorderAPI
from chat.i18n import get_translations as get_chat_translations
from chat.services import get_unread_message_counts_for_rooms, get_unseen_room_ids
from core.presence import presence_data
from core.signals import task_status_changed
from core.utils import build_detail_navigation
from home.navigation import default_toolbar_views
from zzz.templatetags.citizen_filters import citizen_color_class, user_display_name, user_initials

from .activity import get_task_status_label
from .forms import TaskForm, TaskMetadataForm, TaskStatusForm
from .models import Category, Task, TaskEvaluation, TaskSubtask, TaskVote

User = get_user_model()


def _safe_next_url(request):
    next_url = request.POST.get("next")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return next_url
    return None


def _task_action_denied(request, task, error="action not allowed"):
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": False, "error": error}, status=403)
    return redirect(_safe_next_url(request) or "tasks:detail", pk=task.pk)


def _task_sort_context(request):
    sort = request.GET.get('sort', 'date')
    if sort not in ('date', 'score', 'buzz', 'none'):
        sort = 'date'
    order = request.GET.get('order', 'desc') if sort != 'none' else None
    if order not in ('asc', 'desc', None):
        order = 'desc'
    tab = request.GET.get('tab', 'mine')
    if tab not in ('mine', 'awaiting', 'active', 'finished'):
        tab = 'mine'
    valid_slugs = set(Category.objects.values_list('slug', flat=True))
    categories = [c for c in request.GET.getlist('category') if c in valid_slugs]
    return sort, order, tab, categories


class TaskFilterContextMixin:
    """Mixin zapewniający menu zadań stan filtrów (sort/order/category)."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sort, order, tab, categories = _task_sort_context(self.request)
        context.update(
            {
                "current_tab": "",  # help/stats nie mają listy zakładek
                "current_sort": sort,
                "current_order": order,
                "current_categories": categories,
            }
        )
        return context


PRIORITY_LABELS = {"critical": gettext_lazy("Critical"), "important": gettext_lazy("Important"), "beneficial": gettext_lazy("Beneficial"), "rejected": gettext_lazy("Rejected")}

# 'Poparcie' (score) = liczba helpers (votes_up), nie netto. Głosy sprzeciwu
# są osobnym sygnałem blokującym (votes_score <= TASK_REJECTION_SCORE), nie obniżają
# rankingu helpers.
TASK_SORT_FIELDS = {"date": "created_at", "score": "votes_up", "buzz": "chat_msg_count"}

# Klucze wtórne = kanoniczna kolejność, jaką zachowywał stabilny sorted() przy remisach.
TASK_SORT_TIEBREAK = ("-votes_score", "-updated_at")

TASK_PRIORITY_ORDERING = ("-votes_up", "created_at", "id")
TASK_REJECTION_SCORE = -1


def _task_list_queryset(user, categories, sort, order, search_query=''):
    """Annotated task queryset for the list view, with category filter and display sort."""
    qs = Task.objects.with_metrics().with_chat_count().with_user_vote(user).select_related("category", "assigned_to", "assigned_to__uzytkownik", "chat_room")
    if categories:
        qs = qs.filter(category__slug__in=categories)
    if search_query:
        qs = qs.filter(Q(title__icontains=search_query) | Q(description__icontains=search_query))
    if sort == 'none':
        return qs.order_by(*TASK_PRIORITY_ORDERING)
    direction = "-" if order == "desc" else ""
    return qs.order_by(direction + TASK_SORT_FIELDS[sort], *TASK_SORT_TIEBREAK)


def _task_tab_counts(user, categories, search_query=''):
    """Return counts for the task list tabs using the same filters as the list."""
    qs = Task.objects.with_metrics()
    if categories:
        qs = qs.filter(category__slug__in=categories)
    if search_query:
        qs = qs.filter(Q(title__icontains=search_query) | Q(description__icontains=search_query))

    supported = TaskVote.objects.filter(user=user, value=TaskVote.Value.UP).values('task_id')
    return {
        'mine': qs.filter(status=Task.Status.ACTIVE).filter(Q(assigned_to=user) | Q(pk__in=supported)).distinct().count(),
        'awaiting': qs.filter(status=Task.Status.ACTIVE, phase=Task.Phase.PROPOSAL).count(),
        'active': qs.filter(status=Task.Status.ACTIVE, phase=Task.Phase.REALIZATION).count(),
        'finished': qs.filter(Q(status__in=(Task.Status.COMPLETED, Task.Status.CANCELLED), votes_score__gt=TASK_REJECTION_SCORE) | Q(votes_score__lte=TASK_REJECTION_SCORE)).count(),
    }


def _compute_priority_map(task_ids):
    """Return labels for task IDs in canonical order."""
    result = {}
    total = len(task_ids)
    if not total:
        return result
    critical_limit = max(1, math.ceil(total * 0.2))
    important_limit = critical_limit + math.ceil(total * 0.3)
    for idx, task_id in enumerate(task_ids):
        category = "critical" if idx < critical_limit else "important" if idx < important_limit else "beneficial"
        result[task_id] = (PRIORITY_LABELS[category], category)
    return result


def _priority_map(active: bool):
    """Priority mapa dla świata aktywnych albo zakończonych zadań.

    Liczona na zbiorze niefiltrowanym (przed filtrem kategorii) — progi
    percentylowe muszą dotyczyć wszystkich zadań, nie tylko wyświetlanych.
    """
    qs = Task.objects.with_metrics()
    if active:
        qs = qs.filter(status=Task.Status.ACTIVE)
    else:
        qs = qs.filter(status__in=(Task.Status.COMPLETED, Task.Status.CANCELLED))
    task_ids = list(qs.order_by(*TASK_PRIORITY_ORDERING).values_list("id", flat=True))
    return _compute_priority_map(task_ids)


def _prepare_task_cards(tasks, pulse_room_ids, priority_map=None):
    """Attach per-request display attributes for priority and chat pulse."""
    for task in tasks:
        task.priority_label, task.priority_category = priority_map.get(task.id, (None, None)) if priority_map else (None, None)
        task.chat_room_pulse_class = "tw-chat-room-pulse" if task.chat_room_id in pulse_room_ids else ""
    return tasks


def _task_toolbar_data(sort, order, tab, categories, search_query=''):
    """Generate sort and view toggle data for the shared toolbar template."""
    labels = {"date": gettext_lazy("Date")}
    icons = {"date": "clock"}
    params = []
    if tab:
        params.append(f"tab={tab}")
    for c in categories:
        params.append(f"category={c}")
    base_qs = "&".join(params)
    if search_query:
        base_qs = f"{base_qs}&q={quote_plus(search_query)}" if base_qs else f"q={quote_plus(search_query)}"

    sort_items = []
    for s in ("date",):
        state = order if sort == s else 'none'
        next_state = 'asc' if state == 'none' else 'desc' if state == 'asc' else 'none'
        query = f"sort={s}&order={next_state}" if next_state != 'none' else 'sort=none'
        if base_qs:
            query = base_qs + "&" + query
        url = reverse("tasks:list") + "?" + query
        icon = "up" if state == "asc" else "down" if state == "desc" else None
        sort_items.append({"url": url, "label": str(labels[s]), "active": state != 'none', "state": state, "pre_icon": icons[s], "icon": icon})

    views = default_toolbar_views()
    return sort_items, views


class TaskListView(LoginRequiredMixin, TemplateView):
    template_name = "tasks/task_list.html"

    def get_template_names(self):
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return ["tasks/_task_list_partial.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sort, order, tab, categories = _task_sort_context(self.request)
        search_query = self.request.GET.get('q', '').strip()
        user = self.request.user

        qs = _task_list_queryset(user, categories, sort, order, search_query)
        pulse_room_ids = get_unseen_room_ids(user)

        # Szablon renderuje wyłącznie aktywną zakładkę — budujemy tylko jej listy.
        lists = {}
        if tab == "mine":
            # pk__in zamiast joina na votes: filtr relacji nie może zawęzić agregatów with_metrics().
            supported = TaskVote.objects.filter(user=user, value=TaskVote.Value.UP).values("task_id")
            mine = _prepare_task_cards(list(qs.filter(Q(assigned_to=user) | Q(pk__in=supported), status=Task.Status.ACTIVE)), pulse_room_ids)
            lists = {"my_tasks_own": [t for t in mine if t.assigned_to_id == user.id], "my_tasks_supporting": [t for t in mine if t.assigned_to_id != user.id]}
        elif tab == "awaiting":
            lists["awaiting_tasks"] = _prepare_task_cards(list(qs.filter(status=Task.Status.ACTIVE, phase=Task.Phase.PROPOSAL)), pulse_room_ids, _priority_map(active=True))
        elif tab == "active":
            lists["active_tasks"] = _prepare_task_cards(list(qs.filter(status=Task.Status.ACTIVE, phase=Task.Phase.REALIZATION)), pulse_room_ids, _priority_map(active=True))
        else:  # finished
            priority_map = _priority_map(active=False)
            lists["finished_completed"] = _prepare_task_cards(list(qs.filter(status=Task.Status.COMPLETED, votes_score__gt=TASK_REJECTION_SCORE)), pulse_room_ids, priority_map)
            lists["finished_cancelled"] = _prepare_task_cards(list(qs.filter(status=Task.Status.CANCELLED, votes_score__gt=TASK_REJECTION_SCORE)), pulse_room_ids, priority_map)
            rejected = _prepare_task_cards(list(qs.filter(votes_score__lte=TASK_REJECTION_SCORE)), pulse_room_ids)
            for task in rejected:
                task.priority_label = PRIORITY_LABELS["rejected"]
                task.priority_category = "rejected"
            lists["finished_rejected"] = rejected

        displayed_tasks = [task for task_list in lists.values() for task in task_list]
        unread_counts = get_unread_message_counts_for_rooms(user, [task.chat_room_id for task in displayed_tasks])
        for task in displayed_tasks:
            task.chat_unread_count = unread_counts.get(task.chat_room_id, 0)

        sort_items, views = _task_toolbar_data(sort, order, tab, categories, search_query)
        context.update(
            {
                **lists,
                "current_tab": tab,
                "current_sort": sort,
                "current_order": order,
                "current_categories": categories,
                "search_query": search_query,
                "task_counts": _task_tab_counts(user, categories, search_query),
                "category_list": list(Category.objects.values("id", "slug", "name", "description", "order", "is_protected")),
                "toolbar_sort_items": sort_items,
                "toolbar_views": views,
                "detail_query": self.request.GET.urlencode(),
            }
        )
        return context


class TaskHelpView(LoginRequiredMixin, TaskFilterContextMixin, TemplateView):
    template_name = "tasks/task_help.html"


class CategoryContextMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["category_list"] = list(Category.objects.values("id", "slug", "name", "description"))
        return context


class TaskCreateView(CategoryContextMixin, LoginRequiredMixin, CreateView):
    model = Task
    form_class = TaskForm
    template_name = "tasks/task_form.html"
    success_url = reverse_lazy("tasks:list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.assigned_to = self.request.user
        form.instance.team_mode = True
        response = super().form_valid(form)
        TaskVote.objects.get_or_create(task=self.object, user=self.request.user, defaults={"value": TaskVote.Value.UP})
        return response


HELPERS_POPOVER_LIMIT = 10


def _serialize_user(user):
    avatar_url = ""
    uzy = getattr(user, "uzytkownik", None)
    if uzy and getattr(uzy, "avatar", None):
        try:
            avatar_url = uzy.avatar.url
        except ValueError:
            avatar_url = ""
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user_display_name(user),
        "initials": user_initials(user),
        "avatar_url": avatar_url,
        "profile_url": reverse("obywatele:obywatele_szczegoly", args=[user.pk]),
        "citizen_color_class": citizen_color_class(user.username),
        **presence_data(user),
    }


def _voters_json(task: Task, value: int) -> dict:
    qs = TaskVote.objects.filter(task=task, value=value).select_related("user", "user__uzytkownik").order_by("updated_at", "id")
    total = qs.count()
    helpers = [_serialize_user(vote.user) for vote in qs[:HELPERS_POPOVER_LIMIT]]
    return {"helpers": helpers, "total": total, "extra": max(0, total - HELPERS_POPOVER_LIMIT), "task_url": reverse("tasks:detail", args=[task.pk])}


@login_required
def task_helpers_json(request: HttpRequest, pk: int) -> JsonResponse:
    task = get_object_or_404(Task, pk=pk)
    return JsonResponse(_voters_json(task, TaskVote.Value.UP))


@login_required
def task_against_json(request: HttpRequest, pk: int) -> JsonResponse:
    task = get_object_or_404(Task, pk=pk)
    return JsonResponse(_voters_json(task, TaskVote.Value.DOWN))


def require_coordinator(action):
    """Shared pre-checks for coordinator-only helper endpoints.

    Resolves the task, verifies request.user is the coordinator and that the
    target user is not the coordinator. On success calls the wrapped view as
    view(request, task, user_id, is_ajax).
    """

    def decorator(view):
        @wraps(view)
        def wrapper(request, pk, user_id):
            task = get_object_or_404(Task, pk=pk)
            is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
            if task.assigned_to != request.user:
                if is_ajax:
                    return JsonResponse({"ok": False, "error": "not coordinator"}, status=403)
                return redirect("tasks:detail", pk=pk)
            if task.assigned_to_id == user_id:
                if is_ajax:
                    return JsonResponse({"ok": False, "error": f"cannot {action} coordinator"}, status=400)
                return redirect("tasks:detail", pk=pk)
            return view(request, task, user_id, is_ajax)

        return wrapper

    return decorator


@require_POST
@login_required
@require_coordinator("approve")
def approve_helper(request: HttpRequest, task: Task, user_id: int, is_ajax: bool) -> HttpResponse:
    helper = get_object_or_404(User, pk=user_id)
    if not task.is_user_helper(helper):
        if is_ajax:
            return JsonResponse({"ok": False, "error": "not a helper"}, status=400)
        return redirect("tasks:detail", pk=task.pk)

    task.approve_helper(helper)
    task.sync_realization_phase()
    if is_ajax:
        return JsonResponse({"ok": True, "user_id": helper.id, "approved": True, "phase": task.phase})
    return redirect(_safe_next_url(request) or "tasks:detail", pk=task.pk)


@require_POST
@login_required
@require_coordinator("remove")
def remove_helper(request: HttpRequest, task: Task, user_id: int, is_ajax: bool) -> HttpResponse:
    helper = get_object_or_404(User, pk=user_id)
    task.remove_helper(helper)
    task.sync_realization_phase()
    if is_ajax:
        return JsonResponse({"ok": True, "user_id": helper.id, "approved": False, "phase": task.phase})
    return redirect(_safe_next_url(request) or "tasks:detail", pk=task.pk)


@require_POST
@login_required
@require_coordinator("approve")
def toggle_helper(request: HttpRequest, task: Task, user_id: int, is_ajax: bool) -> HttpResponse:
    """Coordinator toggle: approve/remove a helper from the team with one switch."""
    helper = get_object_or_404(User, pk=user_id)
    if task.is_user_approved(helper):
        task.remove_helper(helper)
        approved = False
    else:
        if not task.is_user_helper(helper):
            if is_ajax:
                return JsonResponse({"ok": False, "error": "not a helper"}, status=400)
            return redirect("tasks:detail", pk=task.pk)
        task.approve_helper(helper)
        approved = True
    task.sync_realization_phase()

    if is_ajax:
        return JsonResponse({"ok": True, "user_id": helper.id, "approved": approved, "phase": task.phase})
    return redirect(_safe_next_url(request) or "tasks:detail", pk=task.pk)


@require_POST
@login_required
def take_task(request: HttpRequest, pk: int) -> HttpResponse:
    with transaction.atomic():
        task = get_object_or_404(Task.objects.select_for_update(), pk=pk)
        if not task.is_active:
            return _task_action_denied(request, task, "task is not active")
        if task.assigned_to_id and task.assigned_to_id != request.user.id:
            return _task_action_denied(request, task, "task already has a coordinator")

        task.assigned_to = request.user
        task.save(update_fields=["assigned_to", "updated_at"])
        task.sync_realization_phase()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "assigned_to": _serialize_user(request.user), "is_coordinator": True, "phase": task.phase})
    return redirect(_safe_next_url(request) or "tasks:list")


def _normalize_subtask_orders(task, parent_id):
    siblings = TaskSubtask.objects.filter(task=task, parent_id=parent_id).order_by("order", "pk")
    for order, subtask in enumerate(siblings):
        if subtask.order != order:
            TaskSubtask.objects.filter(pk=subtask.pk).update(order=order)


@require_POST
@login_required
def add_subtask(request: HttpRequest, pk: int) -> HttpResponse:
    title = request.POST.get("title", "").strip()
    with transaction.atomic():
        task = get_object_or_404(Task.objects.select_for_update(), pk=pk)
        if not task.can_manage_subtasks(request.user):
            return _task_action_denied(request, task)
        if not title or len(title) > 240:
            messages.error(request, gettext_lazy("Enter a task title of at most 240 characters."))
            return redirect("tasks:detail", pk=task.pk)

        max_order = task.subtasks.filter(parent__isnull=True).aggregate(max_order=Max("order"))["max_order"]
        TaskSubtask.objects.create(task=task, title=title, order=(max_order + 1) if max_order is not None else 0)
        task.save(update_fields=["updated_at"])
    return redirect(_safe_next_url(request) or "tasks:detail", pk=task.pk)


@require_POST
@login_required
def edit_subtask(request: HttpRequest, pk: int, subtask_pk: int) -> HttpResponse:
    title = request.POST.get("title", "").strip()
    with transaction.atomic():
        task = get_object_or_404(Task.objects.select_for_update(), pk=pk)
        if not task.can_manage_subtasks(request.user):
            return _task_action_denied(request, task)
        if not title or len(title) > 240:
            messages.error(request, gettext_lazy("Enter a task title of at most 240 characters."))
            return redirect("tasks:detail", pk=task.pk)

        subtask = get_object_or_404(TaskSubtask.objects.select_for_update(), pk=subtask_pk, task=task)
        subtask.title = title
        subtask.save(update_fields=["title"])
        task.save(update_fields=["updated_at"])
    return redirect(_safe_next_url(request) or "tasks:detail", pk=task.pk)


@require_POST
@login_required
def toggle_subtask(request: HttpRequest, pk: int, subtask_pk: int) -> HttpResponse:
    with transaction.atomic():
        task = get_object_or_404(Task.objects.select_for_update(), pk=pk)
        if not task.can_manage_subtasks(request.user):
            return _task_action_denied(request, task)

        subtask = get_object_or_404(TaskSubtask.objects.select_for_update(), pk=subtask_pk, task=task)
        subtask.is_completed = not subtask.is_completed
        subtask.save(update_fields=["is_completed"])
        updated = {subtask.pk: subtask}
        if subtask.parent_id:
            parent = get_object_or_404(TaskSubtask.objects.select_for_update(), pk=subtask.parent_id, task=task)
            parent.is_completed = not parent.children.filter(is_completed=False).exists()
            parent.save(update_fields=["is_completed"])
            updated[parent.pk] = parent
        else:
            children = list(subtask.children.select_for_update())
            for child in children:
                child.is_completed = subtask.is_completed
                child.save(update_fields=["is_completed"])
                updated[child.pk] = child
        task.save(update_fields=["updated_at"])

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "states": [{"id": item.pk, "is_completed": item.is_completed} for item in updated.values()]})
    return redirect(_safe_next_url(request) or "tasks:detail", pk=task.pk)


@require_POST
@login_required
def delete_subtask(request: HttpRequest, pk: int, subtask_pk: int) -> HttpResponse:
    with transaction.atomic():
        task = get_object_or_404(Task.objects.select_for_update(), pk=pk)
        if not task.can_manage_subtasks(request.user):
            return _task_action_denied(request, task)

        subtask = get_object_or_404(TaskSubtask.objects.select_for_update(), pk=subtask_pk, task=task)
        if subtask.children.exists():
            messages.error(request, gettext_lazy("Move or remove this task's nested tasks before deleting it."))
            return redirect("tasks:detail", pk=task.pk)
        subtask.delete()
        task.save(update_fields=["updated_at"])
    return redirect(_safe_next_url(request) or "tasks:detail", pk=task.pk)


@require_POST
@login_required
def move_subtask(request: HttpRequest, pk: int, subtask_pk: int, direction: str) -> HttpResponse:
    with transaction.atomic():
        task = get_object_or_404(Task.objects.select_for_update(), pk=pk)
        if not task.can_manage_subtasks(request.user) or direction not in ("up", "down"):
            return _task_action_denied(request, task)

        current = get_object_or_404(TaskSubtask.objects.select_for_update(), pk=subtask_pk, task=task)
        subtasks = list(TaskSubtask.objects.select_for_update().filter(task=task, parent_id=current.parent_id))
        index = next((i for i, item in enumerate(subtasks) if item.pk == current.pk), None)
        if index is None:
            return _task_action_denied(request, task)
        target = index - 1 if direction == "up" else index + 1
        if 0 <= target < len(subtasks):
            subtasks[index], subtasks[target] = subtasks[target], subtasks[index]
            for order, item in enumerate(subtasks):
                TaskSubtask.objects.filter(pk=item.pk, task=task).update(order=order)
            task.save(update_fields=["updated_at"])
    return redirect(_safe_next_url(request) or "tasks:detail", pk=task.pk)


@require_POST
@login_required
def indent_subtask(request: HttpRequest, pk: int, subtask_pk: int) -> HttpResponse:
    with transaction.atomic():
        task = get_object_or_404(Task.objects.select_for_update(), pk=pk)
        if not task.can_manage_subtasks(request.user):
            return _task_action_denied(request, task)

        roots = list(TaskSubtask.objects.select_for_update().filter(task=task, parent__isnull=True))
        index = next((i for i, item in enumerate(roots) if item.pk == subtask_pk), None)
        if index is None or index == 0:
            return _task_action_denied(request, task)

        subtask = roots[index]
        if subtask.children.exists():
            messages.error(request, gettext_lazy("Move this task's nested tasks before nesting it."))
            return redirect("tasks:detail", pk=task.pk)

        parent = roots[index - 1]
        next_order = parent.children.aggregate(max_order=Max("order"))["max_order"]
        subtask.parent = parent
        subtask.order = (next_order + 1) if next_order is not None else 0
        subtask.save(update_fields=["parent", "order"])
        _normalize_subtask_orders(task, None)
        task.save(update_fields=["updated_at"])
    return redirect(_safe_next_url(request) or "tasks:detail", pk=task.pk)


@require_POST
@login_required
def outdent_subtask(request: HttpRequest, pk: int, subtask_pk: int) -> HttpResponse:
    with transaction.atomic():
        task = get_object_or_404(Task.objects.select_for_update(), pk=pk)
        if not task.can_manage_subtasks(request.user):
            return _task_action_denied(request, task)

        subtask = get_object_or_404(TaskSubtask.objects.select_for_update(), pk=subtask_pk, task=task)
        if not subtask.parent_id:
            return _task_action_denied(request, task)

        parent_id = subtask.parent_id
        roots = list(TaskSubtask.objects.select_for_update().filter(task=task, parent__isnull=True))
        parent_index = next((i for i, item in enumerate(roots) if item.pk == parent_id), None)
        if parent_index is None:
            return _task_action_denied(request, task)

        subtask.parent = None
        roots.insert(parent_index + 1, subtask)
        for order, item in enumerate(roots):
            item_order = order
            if item.pk == subtask.pk:
                item.order = item_order
                item.save(update_fields=["parent", "order"])
            elif item.order != item_order:
                TaskSubtask.objects.filter(pk=item.pk).update(order=item_order)
        _normalize_subtask_orders(task, parent_id)
        task.save(update_fields=["updated_at"])
    return redirect(_safe_next_url(request) or "tasks:detail", pk=task.pk)


@require_POST
@login_required
def reorder_subtasks(request: HttpRequest, pk: int) -> JsonResponse:
    try:
        items = json.loads(request.body)
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise ValueError
        if any(set(item) != {"id", "parent_id", "order"} for item in items):
            raise ValueError
        item_ids = [item["id"] for item in items]
        parent_ids = [item["parent_id"] for item in items]
        orders = [item["order"] for item in items]
        if any(type(value) is not int for value in item_ids + orders):
            raise ValueError
        if any(parent_id is not None and type(parent_id) is not int for parent_id in parent_ids):
            raise ValueError
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "invalid order"}, status=400)

    with transaction.atomic():
        task = get_object_or_404(Task.objects.select_for_update(), pk=pk)
        if not task.can_manage_subtasks(request.user):
            return JsonResponse({"ok": False, "error": "not allowed"}, status=403)
        subtasks = list(TaskSubtask.objects.select_for_update().filter(task=task))
        subtasks_by_id = {subtask.pk: subtask for subtask in subtasks}
        if len(item_ids) != len(subtasks_by_id) or set(item_ids) != set(subtasks_by_id):
            return JsonResponse({"ok": False, "error": "invalid order"}, status=400)

        items_by_id = {item["id"]: item for item in items}
        sibling_orders = {}
        for item in items:
            item_id, parent_id, order = item["id"], item["parent_id"], item["order"]
            if parent_id is not None:
                parent = items_by_id.get(parent_id)
                if parent is None or parent_id == item_id or parent["parent_id"] is not None:
                    return JsonResponse({"ok": False, "error": "invalid hierarchy"}, status=400)
            sibling_orders.setdefault(parent_id, []).append(order)

        if any(sorted(orders) != list(range(len(orders))) for orders in sibling_orders.values()):
            return JsonResponse({"ok": False, "error": "invalid order"}, status=400)

        for item in items:
            subtask = subtasks_by_id[item["id"]]
            subtask.parent_id = item["parent_id"]
            subtask.order = item["order"]
        TaskSubtask.objects.bulk_update(subtasks, ("parent", "order"))
        task.save(update_fields=["updated_at"])
    return JsonResponse({"ok": True})


@require_POST
@login_required
def resign_task(request: HttpRequest, pk: int) -> HttpResponse:
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    next_url = _safe_next_url(request)
    with transaction.atomic():
        task = get_object_or_404(Task.objects.select_for_update(), pk=pk)
        if not task.is_active:
            return _task_action_denied(request, task, "task is not active")
        if task.assigned_to_id != request.user.id:
            if is_ajax:
                return JsonResponse({"ok": False, "error": "not coordinator"}, status=403)
            if next_url:
                return redirect(next_url)
            return redirect("tasks:detail", pk=pk)

        successor_vote = TaskVote.objects.filter(task=task, value=TaskVote.Value.UP).exclude(user_id=request.user.id).select_related("user", "user__uzytkownik").order_by("updated_at", "id").first()
        successor = successor_vote.user if successor_vote else None
        task.assigned_to = successor
        task.save(update_fields=["assigned_to", "updated_at"])
        task.sync_realization_phase()

    if is_ajax:
        return JsonResponse({"ok": True, "assigned_to": _serialize_user(successor) if successor else None, "is_coordinator": False, "in_team": task.is_user_approved(request.user), "phase": task.phase})
    if next_url:
        return redirect(next_url)
    return redirect("tasks:list")


class TaskDetailView(LoginRequiredMixin, DetailView):
    model = Task
    template_name = "tasks/task_detail.html"
    context_object_name = "task"

    def get_queryset(self):
        return Task.objects.with_metrics().select_related('created_by', 'created_by__uzytkownik', 'assigned_to', 'assigned_to__uzytkownik', 'category', 'chat_room')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        task = context["task"]
        priority_map = _priority_map(active=task.is_active)
        current_label, current_category = priority_map.get(task.id, (None, None))
        task.priority_label = current_label or task.get_status_display()
        task.priority_category = current_category
        helping_votes = list(TaskVote.objects.filter(task=task, value=TaskVote.Value.UP).select_related("user", "user__uzytkownik").order_by("updated_at", "id"))
        approved_ids = set(task.approved_helpers.values_list("id", flat=True))
        for hv in helping_votes:
            hv.is_coordinator = hv.user_id == task.assigned_to_id
            hv.is_approved = hv.is_coordinator or hv.user_id in approved_ids
            hv.is_me = hv.user_id == self.request.user.id
        helping_votes.sort(key=lambda hv: (0 if hv.is_coordinator else 1, hv.updated_at, hv.id))
        context["helping_votes"] = helping_votes
        context["against_votes"] = TaskVote.objects.filter(task=task, value=TaskVote.Value.DOWN).select_related("user", "user__uzytkownik").order_by("updated_at", "id")
        context["is_coordinator"] = self.request.user.is_authenticated and task.assigned_to == self.request.user
        if self.request.user.is_authenticated:
            vote = TaskVote.objects.filter(task=task, user=self.request.user).first()
            context["user_vote_value"] = vote.value if vote else None

            task.chat_unread_count = get_unread_message_counts_for_rooms(self.request.user, [task.chat_room_id]).get(task.chat_room_id, 0)
            task.chat_room_pulse_class = "tw-chat-room-pulse" if task.chat_unread_count else ""
            context["can_post_in_chat"] = task.can_user_post(self.request.user)
        else:
            context["can_post_in_chat"] = False
        context["task"] = task
        context["task_status_label"] = get_task_status_label(task)
        context["team_size"] = task.get_team_size()
        context["required_team_size"] = task.required_people or 1
        context["realization_vote_threshold"] = Task.REALIZATION_VOTE_THRESHOLD
        context["can_manage_subtasks"] = task.can_manage_subtasks(self.request.user)
        context["subtask_roots"] = task.subtasks.filter(parent__isnull=True).prefetch_related("children")
        sort, order, tab, categories = _task_sort_context(self.request)
        search_query = self.request.GET.get("q", "").strip()
        navigation_queryset = _task_list_queryset(self.request.user, categories, sort, order, search_query)
        if tab == "mine":
            supported = TaskVote.objects.filter(user=self.request.user, value=TaskVote.Value.UP).values("task_id")
            navigation_queryset = navigation_queryset.filter(Q(assigned_to=self.request.user) | Q(pk__in=supported), status=Task.Status.ACTIVE).distinct()
        elif tab == "awaiting":
            navigation_queryset = navigation_queryset.filter(status=Task.Status.ACTIVE, phase=Task.Phase.PROPOSAL)
        elif tab == "active":
            navigation_queryset = navigation_queryset.filter(status=Task.Status.ACTIVE, phase=Task.Phase.REALIZATION)
        else:
            navigation_queryset = navigation_queryset.filter(
                Q(status=Task.Status.COMPLETED, votes_score__gt=TASK_REJECTION_SCORE) | Q(status=Task.Status.CANCELLED, votes_score__gt=TASK_REJECTION_SCORE) | Q(votes_score__lte=TASK_REJECTION_SCORE)
            )
        context.update({"current_tab": tab, "current_sort": sort, "current_order": order, "current_categories": categories, "task_counts": _task_tab_counts(self.request.user, categories, search_query)})
        context.update(build_detail_navigation(self.request, navigation_queryset, task.pk, "tasks:detail"))
        context["MESSAGE_MAX_LENGTH"] = settings.MESSAGE_MAX_LENGTH
        context["ec_translations"] = get_chat_translations()
        return context


class TaskEditView(CategoryContextMixin, LoginRequiredMixin, UpdateView):
    model = Task
    form_class = TaskForm
    template_name = "tasks/task_form.html"

    def dispatch(self, request, *args, **kwargs):
        task = self.get_object()
        if task.assigned_to != request.user or not task.is_active:
            return redirect("tasks:detail", pk=task.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_form_class(self):
        if self.object.phase == Task.Phase.REALIZATION:
            return TaskMetadataForm
        return super().get_form_class()

    def form_valid(self, form):
        response = super().form_valid(form)
        self.object.sync_realization_phase()
        messages.success(self.request, gettext_lazy("Saved."))
        return response

    def get_success_url(self):
        return reverse_lazy("tasks:detail", kwargs={"pk": self.object.pk})


class TaskCloseView(LoginRequiredMixin, UpdateView):
    model = Task
    form_class = TaskStatusForm
    template_name = "tasks/task_close.html"

    def dispatch(self, request, *args, **kwargs):
        task = self.get_object()
        if task.assigned_to != request.user or not task.is_active:
            return redirect("tasks:detail", pk=task.pk)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("tasks:detail", kwargs={"pk": self.object.pk})


@require_POST
@login_required
def vote_task(request: HttpRequest, pk: int) -> HttpResponse:
    task = get_object_or_404(Task.objects.with_metrics(), pk=pk)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if not task.is_active:
        return _task_action_denied(request, task, "task is not active")
    try:
        value = int(request.POST.get("value", 0))
    except (ValueError, TypeError):
        value = 0
    if value not in (TaskVote.Value.DOWN, TaskVote.Value.UP):
        if is_ajax:
            return JsonResponse({"error": "invalid value"}, status=400)
        return redirect(_safe_next_url(request) or "tasks:list")

    new_vote = None
    with transaction.atomic():
        vote = TaskVote.objects.filter(task=task, user=request.user).first()
        if vote and vote.value == value:
            vote.delete()
        else:
            if not vote:
                vote = TaskVote(task=task, user=request.user, value=value)
                vote.save()
            else:
                vote.value = value
                vote.save(update_fields=["value", "updated_at"])
            new_vote = value

        # Reject once votes against outnumber votes for by at least one.
        task.refresh_from_db(fields=["status", "updated_at"])
        metrics = (
            Task.objects.filter(pk=task.pk)
            .annotate(votes_score=Coalesce(Sum("votes__value"), 0), votes_up=Count("votes", filter=Q(votes__value=1)), votes_down=Count("votes", filter=Q(votes__value=-1)))
            .values("votes_score", "votes_up", "votes_down", "status")
            .first()
        )
        votes_score = metrics["votes_score"] if metrics else 0
        votes_up = metrics["votes_up"] if metrics else 0
        votes_down = metrics["votes_down"] if metrics else 0
        if votes_score <= TASK_REJECTION_SCORE and task.status != Task.Status.REJECTED:
            previous_status = task.status
            Task.objects.filter(pk=task.pk).update(status=Task.Status.REJECTED, updated_at=models.F("updated_at"))
            task.status = Task.Status.REJECTED
            transaction.on_commit(lambda: task_status_changed.send(sender=Task, task=task, previous_status=previous_status))
        else:
            task.sync_realization_phase()

    if is_ajax:
        return JsonResponse({"vote": new_vote, "votes_score": votes_score, "votes_up": votes_up, "votes_down": votes_down, "phase": task.phase, "status": task.status})
    return redirect(_safe_next_url(request) or "tasks:list")


@require_POST
@login_required
def reopen_task(request: HttpRequest, pk: int) -> HttpResponse:
    next_url = _safe_next_url(request)
    with transaction.atomic():
        task = get_object_or_404(Task.objects.select_for_update(), pk=pk)
        if task.is_active:
            return redirect(next_url or "tasks:detail", pk=pk)
        if task.created_by_id != request.user.id and task.assigned_to_id != request.user.id:
            return _task_action_denied(request, task, "only the creator or coordinator may reopen a task")

        TaskVote.objects.filter(task=task).delete()
        task.status = Task.Status.ACTIVE
        task.phase = Task.Phase.PROPOSAL
        task.save(update_fields=["status", "phase", "updated_at"])
    return redirect(next_url or "tasks:list")


@require_POST
@login_required
def evaluate_task(request: HttpRequest, pk: int) -> HttpResponse:
    task = get_object_or_404(Task, pk=pk)
    value = request.POST.get("value")
    if value not in (TaskEvaluation.Value.SUCCESS, TaskEvaluation.Value.FAILURE):
        return redirect(_safe_next_url(request) or "tasks:list")

    evaluation = TaskEvaluation.objects.filter(task=task, user=request.user).first()
    if evaluation and evaluation.value == value:
        evaluation.delete()
    else:
        if not evaluation:
            evaluation = TaskEvaluation(task=task, user=request.user, value=value)
            evaluation.save()
        else:
            evaluation.value = value
            evaluation.save(update_fields=["value", "updated_at"])
    return redirect(_safe_next_url(request) or "tasks:list")


@require_POST
@login_required
def delete_task(request: HttpRequest, pk: int) -> HttpResponse:
    task = get_object_or_404(Task, pk=pk)
    if task.created_by != request.user:
        return redirect("tasks:detail", pk=pk)

    if task.status == Task.Status.COMPLETED:
        return redirect("tasks:detail", pk=pk)

    task.delete()
    return redirect("tasks:list")


class TaskCategoryAPI(CategoryAPIBase):
    model = Category
    related_count_field = "tasks"
    order_field = "order"

    def serialize(self, cat):
        data = super().serialize(cat)
        data["slug"] = cat.slug
        return data

    def post(self, request):
        # Unikalny slug generuje Category.save() — tutaj tylko walidacja nazwy.
        name = request.POST.get("name", "").strip()
        if name and not slugify(name):
            return JsonResponse({"error": "Invalid name."}, status=400)
        return super().post(request)


class TaskCategoryEditAPI(CategoryEditAPI):
    model = Category

    def serialize(self, cat):
        data = super().serialize(cat)
        data["slug"] = cat.slug
        return data


class TaskCategoryDeleteAPI(CategoryDeleteAPI):
    model = Category
    related_count_field = "tasks"
    block_if_in_use = False


class TaskCategoryReorderAPI(CategoryReorderAPI):
    model = Category
    order_field = "order"


def _coordinator_ranking():
    statuses = (Task.Status.COMPLETED, Task.Status.CANCELLED, Task.Status.REJECTED)
    coordinators = {}
    closed_tasks = Task.objects.filter(status__in=statuses, assigned_to__isnull=False).with_metrics().select_related("assigned_to", "assigned_to__uzytkownik")
    for task in closed_tasks:
        coordinator_id = task.assigned_to_id
        row = coordinators.setdefault(
            coordinator_id,
            {
                "coordinator": task.assigned_to,
                "total_closed": 0,
                "successful_outcomes": 0,
                "outcomes": {status: {"total": 0, "success": 0, "failure": 0, "mixed": 0, "no_evaluations": 0} for status in statuses},
            },
        )
        outcome = row["outcomes"][task.status]
        row["total_closed"] += 1
        outcome["total"] += 1

        success = task.eval_success or 0
        failure = task.eval_failure or 0
        if success > failure:
            row["successful_outcomes"] += 1
            outcome["success"] += 1
        elif failure > success:
            outcome["failure"] += 1
        elif success:
            outcome["mixed"] += 1
        else:
            outcome["no_evaluations"] += 1

    return sorted(coordinators.values(), key=lambda row: (-row["successful_outcomes"], -row["total_closed"], user_display_name(row["coordinator"]).casefold(), row["coordinator"].pk))


class TaskStatsView(LoginRequiredMixin, TaskFilterContextMixin, TemplateView):
    template_name = "tasks/task_stats.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from datetime import timedelta

        from django.utils import timezone

        completed_tasks = Task.objects.filter(status=Task.Status.COMPLETED).with_metrics()

        total_completed = completed_tasks.count()

        success_count = sum(1 for t in completed_tasks if (t.eval_success or 0) > (t.eval_failure or 0))
        failure_count = sum(1 for t in completed_tasks if (t.eval_failure or 0) > (t.eval_success or 0))
        mixed_count = sum(1 for t in completed_tasks if (t.eval_success or 0) == (t.eval_failure or 0) and (t.eval_success or 0) > 0)
        no_eval_count = sum(1 for t in completed_tasks if (t.eval_success or 0) == 0 and (t.eval_failure or 0) == 0)

        success_rate = (success_count / total_completed * 100) if total_completed > 0 else 0

        one_week_ago = timezone.now() - timedelta(days=7)
        completed_last_week = Task.objects.filter(status=Task.Status.COMPLETED, updated_at__gte=one_week_ago).count()

        context.update(
            {
                "total_completed": total_completed,
                "success_count": success_count,
                "failure_count": failure_count,
                "mixed_count": mixed_count,
                "no_eval_count": no_eval_count,
                "success_rate": int(success_rate),
                "completed_last_week": completed_last_week,
                "coordinator_ranking": _coordinator_ranking(),
            }
        )
        return context
