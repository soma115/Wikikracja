import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Count, IntegerField, Value
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View


class CategoryAPIMixin(LoginRequiredMixin, View):
    """Shared no-op write hook for the Category API views below.

    Override `after_write()` in a subclass to invalidate caches or trigger other
    side effects after a create/update/delete/reorder.
    """

    def after_write(self):
        pass


class CategoryAPIBase(CategoryAPIMixin):
    """GET: list categories with item count. POST: create new category."""
    model = None
    related_count_field = None  # e.g. 'tasks' or 'post_set'
    order_field = "order"       # field name used for ordering; override if different (e.g. 'priority')

    def _get_queryset(self):
        qs = self.model.objects.all()
        if self.related_count_field:
            qs = qs.annotate(item_count=Count(self.related_count_field, distinct=True))
        else:
            qs = qs.annotate(item_count=Value(0, output_field=IntegerField()))
        return qs

    def serialize(self, cat):
        return {
            "id": cat.id,
            "name": cat.name,
            "description": cat.description,
            "order": getattr(cat, self.order_field, 0),
            "is_protected": cat.is_protected,
            "item_count": getattr(cat, "item_count", 0),
        }

    def get(self, request):
        cats = [self.serialize(c) for c in self._get_queryset()]
        return JsonResponse({"categories": cats})

    def post(self, request):
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        if not name:
            return JsonResponse({"error": "Name is required."}, status=400)
        cat = self.model.objects.create(name=name, description=description)
        self.after_write()
        data = self.serialize(cat)
        data["item_count"] = 0
        return JsonResponse(data)


class CategoryEditAPI(CategoryAPIMixin):
    """POST: update name and description."""
    model = None

    def serialize(self, cat):
        return {
            "id": cat.id,
            "name": cat.name,
            "description": cat.description,
        }

    def post(self, request, pk):
        cat = get_object_or_404(self.model, pk=pk)
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        if not name:
            return JsonResponse({"error": "Name is required."}, status=400)
        cat.name = name
        cat.description = description
        cat.save(update_fields=["name", "description"])
        self.after_write()
        return JsonResponse(self.serialize(cat))


class CategoryDeleteAPI(CategoryAPIMixin):
    """POST: delete category. Blocks if protected or (block_if_in_use and has items)."""
    model = None
    related_count_field = None
    block_if_in_use = False

    def post(self, request, pk):
        cat = get_object_or_404(self.model, pk=pk)
        if cat.is_protected:
            return JsonResponse(
                {"error": "This category is protected and cannot be deleted."},
                status=403,
            )
        if self.block_if_in_use and self.related_count_field:
            count = getattr(cat, self.related_count_field).count()
            if count:
                return JsonResponse(
                    {"error": f"Cannot delete: {count} document(s) use this category. Reassign them first."},
                    status=409,
                )
        cat.delete()
        self.after_write()
        return JsonResponse({"ok": True})


class CategoryItemsAPI(LoginRequiredMixin, View):
    """GET: labels (titles/names) of items assigned to a category, plus total count.

    Reusable across apps (board uses posts/title; tasks could use tasks/title). The label
    list is capped at `limit`; `count` is always the true total so the UI can show "and N more".
    """
    model = None
    related_field = None      # e.g. 'posts'
    item_label_field = None   # e.g. 'title' (Post) / 'name'
    limit = 50

    def get(self, request, pk):
        cat = get_object_or_404(self.model, pk=pk)
        qs = getattr(cat, self.related_field).all()
        total = qs.count()
        # order_by keeps the truncated preview stable across calls (slice without ordering
        # is DB-plan-dependent), so the user sees a consistent list of affected items.
        labels = list(
            qs.order_by(self.item_label_field).values_list(self.item_label_field, flat=True)[: self.limit]
        )
        return JsonResponse({"items": labels, "count": total})


class CategoryReorderAPI(CategoryAPIMixin):
    """POST body: JSON array [{id, order}, ...]. Updates order of categories."""
    model = None
    order_field = "order"

    def post(self, request):
        try:
            items = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({"error": "Invalid JSON."}, status=400)
        with transaction.atomic():
            for item in items:
                self.model.objects.filter(pk=item["id"]).update(
                    **{self.order_field: item["order"]}
                )
        self.after_write()
        return JsonResponse({"ok": True})
