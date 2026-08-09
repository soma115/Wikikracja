from django.conf import settings
from django.db import models
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from categories.models import AbstractCategory
from chat.models import ChatRoomModel

User = settings.AUTH_USER_MODEL


class Category(AbstractCategory):
    slug = models.SlugField(max_length=64, unique=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(AbstractCategory.Meta):
        ordering = ("order", "name")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class TaskQuerySet(models.QuerySet):
    def with_metrics(self):
        return self.annotate(
            votes_up=Count("votes", filter=Q(votes__value=TaskVote.Value.UP), distinct=True),
            votes_down=Count("votes", filter=Q(votes__value=TaskVote.Value.DOWN), distinct=True),
            votes_score=Coalesce(Sum("votes__value"), 0),
            eval_success=Count("evaluations", filter=Q(evaluations__value=TaskEvaluation.Value.SUCCESS), distinct=True),
            eval_failure=Count("evaluations", filter=Q(evaluations__value=TaskEvaluation.Value.FAILURE), distinct=True),
        )


class Task(ChatRoomModel, models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        COMPLETED = "completed", _("Completed")
        CANCELLED = "cancelled", _("Cancelled")
        REJECTED = "rejected", _("Rejected")

    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL, related_name="tasks")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="tasks_created", null=True, blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="tasks_assigned", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TaskQuerySet.as_manager()

    class Meta:
        ordering = ("-updated_at",)

    def __str__(self):
        return self.title

    @property
    def is_active(self) -> bool:
        return self.status == self.Status.ACTIVE

    def get_chat_room_title(self):
        return f"Task #{self.id}: {self.title}"[:90]

    def get_chat_room_url(self):
        if self.chat_room_id:
            return f"{reverse('chat:chat')}#room_id={self.chat_room_id}"
        return None

    @property
    def chat_room_url(self):
        return self.get_chat_room_url()

    def get_chat_room_pulse_class(self, user):
        """Return CSS class for chat room pulse indicator if there are unseen messages"""
        room = self.chat_room
        if room and room.messages.exists() and not room.seen_by.filter(id=user.id).exists():
            return "chat-room-pulse"
        return ""


class TaskVote(models.Model):
    class Value(models.IntegerChoices):
        DOWN = -1, _("Against")
        UP = 1, _("For")

    task = models.ForeignKey(Task, related_name="votes", on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name="task_votes", on_delete=models.CASCADE)
    value = models.IntegerField(choices=Value.choices)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("task", "user")

    def __str__(self):
        return f"{self.user} -> {self.task} ({self.get_value_display()})"


class TaskEvaluation(models.Model):
    class Value(models.TextChoices):
        SUCCESS = "success", _("Success")
        FAILURE = "failure", _("Failure")

    task = models.ForeignKey(Task, related_name="evaluations", on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name="task_evaluations", on_delete=models.CASCADE)
    value = models.CharField(max_length=16, choices=Value.choices)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("task", "user")

    def __str__(self):
        return f"{self.user} -> {self.task} ({self.get_value_display()})"
