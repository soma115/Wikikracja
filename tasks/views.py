import math

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
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
from chat.models import Room
from chat.views import get_translations as get_chat_translations

from .forms import TaskForm, TaskStatusForm
from .models import Category, Task, TaskEvaluation, TaskVote

TASK_LIST_CACHE_TTL = 3600  # 1h — signals handle invalidation on data changes
TASK_LIST_GLOBAL_VERSION_KEY = "task_list_global_version"


def _task_list_cache_key(user_id):
    version = cache.get(TASK_LIST_GLOBAL_VERSION_KEY, 1)
    return f"task_list_data_v2_{version}_{user_id}"


def invalidate_task_list_cache(user_id=None):
    """Invalidate task list cache. Bumps global version to invalidate all users at once."""
    if user_id:
        cache.delete(_task_list_cache_key(user_id))
    else:
        # Bump global version — all per-user keys become stale immediately
        try:
            cache.incr(TASK_LIST_GLOBAL_VERSION_KEY)
        except ValueError:
            cache.set(TASK_LIST_GLOBAL_VERSION_KEY, 2, timeout=None)


def _get_pulse_room_ids(user):
    """Return set of chat room IDs that have unseen messages for user — single batch query."""

    # Rooms with at least one message, minus rooms the user has already seen
    rooms_with_msgs = Room.objects.filter(messages__isnull=False).values_list("id", flat=True).distinct()
    seen_room_ids = set(user.seen_rooms.filter(id__in=rooms_with_msgs).values_list("id", flat=True))
    return set(rooms_with_msgs) - seen_room_ids


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


def _filter_by_category(tasks, categories):
    if not categories:
        return tasks
    return [t for t in tasks if t.category and t.category.slug in categories]


def _apply_task_sort(tasks, sort, order):
    reverse = order == 'desc'
    if sort == 'date':
        return sorted(tasks, key=lambda t: t.created_at, reverse=reverse)
    elif sort == 'score':
        # 'Poparcie' = liczba helpers (votes_up), nie netto. Głosy sprzeciwu
        # są osobnym sygnałem (próg rejection przy votes_score <= -2),
        # nie obniżają rankingu helpers.
        return sorted(tasks, key=lambda t: t.votes_up or 0, reverse=reverse)
    elif sort == 'buzz':
        return sorted(tasks, key=lambda t: getattr(t, 'chat_msg_count', 0) or 0, reverse=reverse)
    return tasks


PRIORITY_LABELS = {"critical": gettext_lazy("Critical"), "important": gettext_lazy("Important"), "beneficial": gettext_lazy("Beneficial"), "rejected": gettext_lazy("Rejected")}


def _assign_priorities(tasks):
    for task in tasks:
        task.priority_label = None
        task.priority_category = None

    non_rejected = [t for t in tasks if (t.votes_score or 0) >= -1]
    rejected = [t for t in tasks if (t.votes_score or 0) <= -2]
    total = len(non_rejected)

    def mark(task, category):
        task.priority_category = category
        task.priority_label = PRIORITY_LABELS[category]

    if total == 0:
        for task in rejected:
            mark(task, "rejected")
        return

    critical_limit = max(1, math.ceil(total * 0.2))
    important_limit = critical_limit + math.ceil(total * 0.3)

    for idx, task in enumerate(non_rejected):
        if idx < critical_limit:
            mark(task, "critical")
        elif idx < important_limit:
            mark(task, "important")
        else:
            mark(task, "beneficial")

    for task in rejected:
        mark(task, "rejected")


def _load_task_lists(user):
    """
    Fetch and categorise all tasks. Result is cached in Redis per user (TTL=60s).
    Returns a dict with pre-categorised task lists and per-task user-specific attributes
    (user_vote_value, chat_room_pulse_class) already set on the objects.
    """
    cache_key = _task_list_cache_key(user.id)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    queryset = Task.objects.with_metrics().annotate(chat_msg_count=Count('chat_room__messages', distinct=True)).order_by("-votes_score", "-updated_at")

    active_tasks = list(queryset.filter(status=Task.Status.ACTIVE))
    _assign_priorities(active_tasks)
    rejected_active = [t for t in active_tasks if t.priority_category == "rejected"]
    active_non_rejected = [t for t in active_tasks if t.priority_category != "rejected"]
    active_with_owner = [t for t in active_non_rejected if t.assigned_to and ((t.votes_up or 0) - (t.votes_down or 0) >= 2)]
    awaiting_tasks = [t for t in active_non_rejected if t not in active_with_owner]

    finished_tasks = list(queryset.exclude(status=Task.Status.ACTIVE))
    _assign_priorities(finished_tasks)
    rejected_tasks = [t for t in finished_tasks if t.priority_category == "rejected"]
    completed_tasks = [t for t in finished_tasks if t.priority_category != "rejected" and t.status == Task.Status.COMPLETED]
    cancelled_tasks = [t for t in finished_tasks if t.priority_category != "rejected" and t.status == Task.Status.CANCELLED]

    all_tasks = active_tasks + finished_tasks

    # Batch: user votes (1 query)
    vote_by_task_id = dict(TaskVote.objects.filter(user=user, task_id__in=[t.id for t in all_tasks]).values_list("task_id", "value"))
    for t in all_tasks:
        t.user_vote_value = vote_by_task_id.get(t.id)

    # Batch: unseen chat rooms (2 queries instead of 2N)
    pulse_room_ids = _get_pulse_room_ids(user)
    for t in all_tasks:
        t.chat_room_pulse_class = "chat-room-pulse" if t.chat_room_id in pulse_room_ids else ""

    # My tasks (separate queryset — user-specific, also annotated)
    my_tasks_qs = list(
        Task.objects.filter(Q(assigned_to=user) | Q(votes__user=user, votes__value=1))
        .filter(status=Task.Status.ACTIVE)
        .distinct()
        .with_metrics()
        .annotate(chat_msg_count=Count('chat_room__messages', distinct=True))
        .order_by("-votes_score", "-updated_at")
    )
    my_vote_map = dict(TaskVote.objects.filter(user=user, task_id__in=[t.id for t in my_tasks_qs]).values_list("task_id", "value"))
    for t in my_tasks_qs:
        t.user_vote_value = my_vote_map.get(t.id)
        t.chat_room_pulse_class = "chat-room-pulse" if t.chat_room_id in pulse_room_ids else ""

    result = {
        "active_with_owner": active_with_owner,
        "awaiting_tasks": awaiting_tasks,
        "completed_tasks": completed_tasks,
        "rejected_tasks": rejected_tasks,
        "rejected_active": rejected_active,
        "cancelled_tasks": cancelled_tasks,
        "my_tasks_own": [t for t in my_tasks_qs if t.assigned_to_id == user.id],
        "my_tasks_supporting": [t for t in my_tasks_qs if t.assigned_to_id != user.id],
    }
    cache.set(cache_key, result, TASK_LIST_CACHE_TTL)
    return result


class TaskListView(LoginRequiredMixin, TemplateView):
    template_name = "tasks/task_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sort, order, tab, categories = _task_sort_context(self.request)

        data = _load_task_lists(self.request.user)

        def prepare(tasks):
            return _apply_task_sort(_filter_by_category(tasks, categories), sort, order)

        context.update(
            {
                "active_tasks": prepare(data["active_with_owner"]),
                "awaiting_tasks": prepare(data["awaiting_tasks"]),
                "finished_completed": prepare(data["completed_tasks"]),
                "finished_rejected": prepare(data["rejected_tasks"] + data["rejected_active"]),
                "finished_cancelled": prepare(data["cancelled_tasks"]),
                "my_tasks_own": prepare(data["my_tasks_own"]),
                "my_tasks_supporting": prepare(data["my_tasks_supporting"]),
                "current_tab": tab,
                "current_sort": sort,
                "current_order": order,
                "current_categories": categories,
                "category_list": list(Category.objects.values("id", "slug", "name", "description", "order", "is_protected")),
            }
        )
        return context


class TaskHelpView(LoginRequiredMixin, TemplateView):
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
    return {"id": user.id, "username": user.username, "avatar_url": avatar_url, "profile_url": reverse("obywatele:obywatele_szczegoly", args=[user.pk])}


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


@require_POST
@login_required
def take_task(request: HttpRequest, pk: int) -> HttpResponse:
    task = get_object_or_404(Task, pk=pk)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    task.assigned_to = request.user
    task.save(update_fields=["assigned_to", "updated_at"])
    if is_ajax:
        return JsonResponse({"ok": True, "assigned_to": _serialize_user(request.user)})
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
        return JsonResponse({"ok": True, "assigned_to": None})
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
        if task.is_active:
            reference_tasks = list(Task.objects.with_metrics().filter(status=Task.Status.ACTIVE).order_by("-votes_score", "-updated_at"))
        else:
            reference_tasks = list(Task.objects.with_metrics().exclude(status=Task.Status.ACTIVE).order_by("-votes_score", "-updated_at"))
        _assign_priorities(reference_tasks)
        priority_map = {t.id: getattr(t, "priority_label", None) for t in reference_tasks}
        current_label = getattr(task, "priority_label", None)
        task.priority_label = priority_map.get(task.id, current_label or task.get_status_display())
        priority_map = {t.id: (getattr(t, "priority_label", None), getattr(t, "priority_category", None)) for t in reference_tasks}
        current_label, current_category = priority_map.get(task.id, (getattr(task, "priority_label", None), getattr(task, "priority_category", None)))
        task.priority_label = current_label or task.get_status_display()
        task.priority_category = current_category
        context["helping_votes"] = TaskVote.objects.filter(task=task, value=TaskVote.Value.UP).select_related("user", "user__uzytkownik").order_by("updated_at", "id")
        context["against_votes"] = TaskVote.objects.filter(task=task, value=TaskVote.Value.DOWN).select_related("user", "user__uzytkownik").order_by("updated_at", "id")
        if self.request.user.is_authenticated:
            vote = TaskVote.objects.filter(task=task, user=self.request.user).first()
            context["user_vote_value"] = vote.value if vote else None

            # Check if chat room has unseen messages
            task.chat_room_pulse_class = task.get_chat_room_pulse_class(self.request.user)
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
    except ValueError, TypeError:
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
        name = request.POST.get("name", "").strip()
        if not name:
            return JsonResponse({"error": "Name is required."}, status=400)
        base_slug = slugify(name)
        if not base_slug:
            return JsonResponse({"error": "Invalid name."}, status=400)
        slug = base_slug
        counter = 1
        while Category.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        description = request.POST.get("description", "").strip()
        cat = Category.objects.create(name=name, slug=slug, description=description)
        self.after_write()
        data = self.serialize(cat)
        data["item_count"] = 0
        return JsonResponse(data)

    def after_write(self):
        invalidate_task_list_cache()


class TaskCategoryEditAPI(CategoryEditAPI):
    model = Category

    def serialize(self, cat):
        data = super().serialize(cat)
        data["slug"] = cat.slug
        return data

    def after_write(self):
        invalidate_task_list_cache()


class TaskCategoryDeleteAPI(CategoryDeleteAPI):
    model = Category
    related_count_field = "tasks"
    block_if_in_use = False

    def after_write(self):
        invalidate_task_list_cache()


class TaskCategoryReorderAPI(CategoryReorderAPI):
    model = Category
    order_field = "order"

    def after_write(self):
        invalidate_task_list_cache()


class TaskStatsView(LoginRequiredMixin, TemplateView):
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
