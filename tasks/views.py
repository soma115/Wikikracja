import math
from functools import wraps

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models, transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.text import slugify
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, TemplateView, UpdateView

from categories.views import CategoryAPIBase, CategoryDeleteAPI, CategoryEditAPI, CategoryReorderAPI
from chat.i18n import get_translations as get_chat_translations
from chat.services import get_unseen_room_ids
from zzz.templatetags.citizen_filters import citizen_color_class

from .forms import TaskForm, TaskStatusForm
from .models import Category, Task, TaskEvaluation, TaskVote

User = get_user_model()


def _task_sort_context(request):
    sort = request.GET.get('sort', 'date')
    if sort not in ('date', 'score', 'buzz'):
        sort = 'date'
    order = request.GET.get('order', 'desc')
    if order not in ('asc', 'desc'):
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
# są osobnym sygnałem (próg rejection przy votes_score <= -2), nie obniżają
# rankingu helpers.
TASK_SORT_FIELDS = {"date": "created_at", "score": "votes_up", "buzz": "chat_msg_count"}

# Klucze wtórne = kanoniczna kolejność, jaką zachowywał stabilny sorted() przy remisach.
TASK_SORT_TIEBREAK = ("-votes_score", "-updated_at")


def _task_list_queryset(user, categories, sort, order):
    """Annotated task queryset for the list view, with category filter and display sort."""
    qs = Task.objects.with_metrics().with_chat_count().with_user_vote(user).select_related("category", "assigned_to", "assigned_to__uzytkownik", "chat_room")
    if categories:
        qs = qs.filter(category__slug__in=categories)
    direction = "-" if order == "desc" else ""
    return qs.order_by(direction + TASK_SORT_FIELDS[sort], *TASK_SORT_TIEBREAK)


def _compute_priority_map(rows):
    """rows: [(task_id, votes_score)] w kanonicznej kolejności.
    Zwraca {task_id: (priority_label, priority_category)}."""
    result = {}
    non_rejected = []
    for task_id, score in rows:
        if (score or 0) <= -2:
            result[task_id] = (PRIORITY_LABELS["rejected"], "rejected")
        else:
            non_rejected.append(task_id)
    total = len(non_rejected)
    if not total:
        return result
    critical_limit = max(1, math.ceil(total * 0.2))
    important_limit = critical_limit + math.ceil(total * 0.3)
    for idx, task_id in enumerate(non_rejected):
        category = "critical" if idx < critical_limit else "important" if idx < important_limit else "beneficial"
        result[task_id] = (PRIORITY_LABELS[category], category)
    return result


def _priority_map(active: bool):
    """Priority mapa dla świata aktywnych albo zakończonych zadań.

    Liczona na zbiorze niefiltrowanym (przed filtrem kategorii) — progi
    percentylowe muszą dotyczyć wszystkich zadań, nie tylko wyświetlanych.
    """
    qs = Task.objects.with_metrics()
    qs = qs.filter(status=Task.Status.ACTIVE) if active else qs.exclude(status=Task.Status.ACTIVE)
    rows = list(qs.order_by("-votes_score", "-updated_at").values_list("id", "votes_score"))
    return _compute_priority_map(rows)


def _prepare_task_cards(tasks, pulse_room_ids, priority_map=None):
    """Attach per-request display attributes: priority badge and chat pulse."""
    for task in tasks:
        task.priority_label, task.priority_category = priority_map.get(task.id, (None, None)) if priority_map else (None, None)
        task.chat_room_pulse_class = "chat-room-pulse" if task.chat_room_id in pulse_room_ids else ""
    return tasks


def _task_toolbar_data(sort, order, tab, categories):
    """Generate sort and view toggle data for the shared toolbar template."""
    labels = {"date": gettext_lazy("Date"), "score": gettext_lazy("Score"), "buzz": gettext_lazy("Buzz")}
    icons = {"date": "clock-rotate-left", "score": "pen-nib", "buzz": "fire"}
    params = []
    if tab:
        params.append(f"tab={tab}")
    for c in categories:
        params.append(f"category={c}")
    base_qs = "&".join(params)

    sort_items = []
    for s in ("date", "score", "buzz"):
        active = sort == s
        next_order = "asc" if (active and order == "desc") else "desc"
        query = f"sort={s}&order={next_order}"
        if base_qs:
            query = base_qs + "&" + query
        url = reverse("tasks:list") + "?" + query
        icon = None
        if active:
            icon = "up" if next_order == "desc" else "down"
        sort_items.append({"url": url, "label": str(labels[s]), "active": active, "pre_icon": icons[s], "icon": icon})

    views = [{"name": "compact", "icon": "bars", "title": gettext_lazy("Compact")}, {"name": "list", "icon": "list", "title": gettext_lazy("List")}]
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
        user = self.request.user

        qs = _task_list_queryset(user, categories, sort, order)
        pulse_room_ids = get_unseen_room_ids(user)

        # Szablon renderuje wyłącznie aktywną zakładkę — budujemy tylko jej listy.
        lists = {}
        if tab == "mine":
            # pk__in zamiast joina na votes: filtr relacji nie może zawęzić agregatów with_metrics().
            supported = TaskVote.objects.filter(user=user, value=TaskVote.Value.UP).values("task_id")
            mine = _prepare_task_cards(list(qs.filter(Q(assigned_to=user) | Q(pk__in=supported), status=Task.Status.ACTIVE)), pulse_room_ids)
            lists = {"my_tasks_own": [t for t in mine if t.assigned_to_id == user.id], "my_tasks_supporting": [t for t in mine if t.assigned_to_id != user.id]}
        elif tab == "awaiting":
            lists["awaiting_tasks"] = _prepare_task_cards(
                list(qs.filter(status=Task.Status.ACTIVE, votes_score__gte=-1).filter(Q(assigned_to__isnull=True) | Q(votes_score__lt=2))), pulse_room_ids, _priority_map(active=True)
            )
        elif tab == "active":
            lists["active_tasks"] = _prepare_task_cards(list(qs.filter(status=Task.Status.ACTIVE, assigned_to__isnull=False, votes_score__gte=2)), pulse_room_ids, _priority_map(active=True))
        else:  # finished
            priority_map = _priority_map(active=False)
            lists["finished_completed"] = _prepare_task_cards(list(qs.filter(status=Task.Status.COMPLETED, votes_score__gte=-1)), pulse_room_ids, priority_map)
            lists["finished_cancelled"] = _prepare_task_cards(list(qs.filter(status=Task.Status.CANCELLED, votes_score__gte=-1)), pulse_room_ids, priority_map)
            rejected = _prepare_task_cards(list(qs.filter(votes_score__lte=-2)), pulse_room_ids)
            for task in rejected:
                task.priority_label = PRIORITY_LABELS["rejected"]
                task.priority_category = "rejected"
            lists["finished_rejected"] = rejected

        sort_items, views = _task_toolbar_data(sort, order, tab, categories)
        context.update(
            {
                **lists,
                "current_tab": tab,
                "current_sort": sort,
                "current_order": order,
                "current_categories": categories,
                "category_list": list(Category.objects.values("id", "slug", "name", "description", "order", "is_protected")),
                "toolbar_sort_items": sort_items,
                "toolbar_views": views,
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
        "avatar_url": avatar_url,
        "profile_url": reverse("obywatele:obywatele_szczegoly", args=[user.pk]),
        "citizen_color_class": citizen_color_class(user.username),
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
    if is_ajax:
        return JsonResponse({"ok": True, "user_id": helper.id, "approved": True})
    return redirect(request.POST.get("next") or "tasks:detail", pk=task.pk)


@require_POST
@login_required
@require_coordinator("remove")
def remove_helper(request: HttpRequest, task: Task, user_id: int, is_ajax: bool) -> HttpResponse:
    helper = get_object_or_404(User, pk=user_id)
    task.remove_helper(helper)
    if is_ajax:
        return JsonResponse({"ok": True, "user_id": helper.id, "approved": False})
    return redirect(request.POST.get("next") or "tasks:detail", pk=task.pk)


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

    if is_ajax:
        return JsonResponse({"ok": True, "user_id": helper.id, "approved": approved})
    return redirect(request.POST.get("next") or "tasks:detail", pk=task.pk)


@require_POST
@login_required
def take_task(request: HttpRequest, pk: int) -> HttpResponse:
    task = get_object_or_404(Task, pk=pk)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    task.assigned_to = request.user
    task.save(update_fields=["assigned_to", "updated_at"])
    if is_ajax:
        return JsonResponse({"ok": True, "assigned_to": _serialize_user(request.user), "is_coordinator": True})
    return redirect(request.POST.get("next") or "tasks:list")


@require_POST
@login_required
def resign_task(request: HttpRequest, pk: int) -> HttpResponse:
    task = get_object_or_404(Task, pk=pk)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    next_url = request.POST.get("next")
    if task.assigned_to != request.user:
        if is_ajax:
            return JsonResponse({"ok": False, "error": "not coordinator"}, status=403)
        if next_url:
            return redirect(next_url)
        return redirect("tasks:detail", pk=pk)

    task.assigned_to = None
    task.save(update_fields=["assigned_to", "updated_at"])
    if is_ajax:
        return JsonResponse({"ok": True, "assigned_to": None, "is_coordinator": False, "in_team": task.is_user_approved(request.user)})
    if next_url:
        return redirect(next_url)
    return redirect("tasks:list")


class TaskDetailView(LoginRequiredMixin, DetailView):
    model = Task
    template_name = "tasks/task_detail.html"
    context_object_name = "task"

    def get_queryset(self):
        return Task.objects.with_metrics()

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

            # Check if chat room has unseen messages
            task.chat_room_pulse_class = task.get_chat_room_pulse_class(self.request.user)
            context["can_post_in_chat"] = task.can_user_post(self.request.user)
        else:
            context["can_post_in_chat"] = False
        context["task"] = task
        context["MESSAGE_MAX_LENGTH"] = settings.MESSAGE_MAX_LENGTH
        context["ec_translations"] = get_chat_translations()
        return context


class TaskEditView(CategoryContextMixin, LoginRequiredMixin, UpdateView):
    model = Task
    form_class = TaskForm
    template_name = "tasks/task_form.html"

    def dispatch(self, request, *args, **kwargs):
        task = self.get_object()
        if task.assigned_to != request.user:
            return redirect("tasks:detail", pk=task.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy("tasks:detail", kwargs={"pk": self.object.pk})


class TaskCloseView(LoginRequiredMixin, UpdateView):
    model = Task
    form_class = TaskStatusForm
    template_name = "tasks/task_close.html"

    def dispatch(self, request, *args, **kwargs):
        task = self.get_object()
        if task.assigned_to != request.user:
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
    try:
        value = int(request.POST.get("value", 0))
    except (ValueError, TypeError):
        value = 0
    if value not in (TaskVote.Value.DOWN, TaskVote.Value.UP):
        if is_ajax:
            return JsonResponse({"error": "invalid value"}, status=400)
        return redirect(request.POST.get("next") or "tasks:list")

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

        # Refresh score and set rejected if sum of votes <= -2
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
        if votes_score <= -2 and task.status != Task.Status.REJECTED:
            Task.objects.filter(pk=task.pk).update(status=Task.Status.REJECTED, updated_at=models.F("updated_at"))
            task.status = Task.Status.REJECTED

    if is_ajax:
        return JsonResponse({"vote": new_vote, "votes_score": votes_score, "votes_up": votes_up, "votes_down": votes_down})
    return redirect(request.POST.get("next") or "tasks:list")


@require_POST
@login_required
def reopen_task(request: HttpRequest, pk: int) -> HttpResponse:
    task = get_object_or_404(Task, pk=pk)
    next_url = request.POST.get("next")
    if task.is_active:
        if next_url:
            return redirect(next_url)
        return redirect("tasks:detail", pk=pk)

    task.status = Task.Status.ACTIVE
    task.save(update_fields=["status", "updated_at"])
    if next_url:
        return redirect(next_url)
    return redirect("tasks:list")


@require_POST
@login_required
def evaluate_task(request: HttpRequest, pk: int) -> HttpResponse:
    task = get_object_or_404(Task, pk=pk)
    value = request.POST.get("value")
    if value not in (TaskEvaluation.Value.SUCCESS, TaskEvaluation.Value.FAILURE):
        return redirect(request.POST.get("next") or "tasks:list")

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
    return redirect(request.POST.get("next") or "tasks:list")


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
            }
        )
        return context
