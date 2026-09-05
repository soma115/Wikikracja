from django.conf import settings
from django.db import models, transaction
from django.db.models import Count, F, Q
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
            eval_success=Count("evaluations", filter=Q(evaluations__value=TaskEvaluation.Value.SUCCESS), distinct=True),
            eval_failure=Count("evaluations", filter=Q(evaluations__value=TaskEvaluation.Value.FAILURE), distinct=True),
        ).annotate(votes_score=F("votes_up") - F("votes_down"))


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

    # Nowe działania używają trybu zespołowego: koordynator decyduje, kto może pisać w czacie.
    team_mode = models.BooleanField(default=False, verbose_name=_("Team mode"))
    approved_helpers = models.ManyToManyField(User, related_name="tasks_approved", blank=True, verbose_name=_("Approved helpers"))

    objects = TaskQuerySet.as_manager()

    class Meta:
        ordering = ("-updated_at",)

    def save(self, *args, **kwargs):
        with transaction.atomic():
            super().save(*args, **kwargs)

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

    def is_user_helper(self, user):
        """Return True if the user clicked "I want to help" (TaskVote.Value.UP)."""
        if not user or not user.is_authenticated:
            return False
        return self.votes.filter(user=user, value=TaskVote.Value.UP).exists()

    def is_user_approved(self, user):
        """Return True if the coordinator approved this user as a team member."""
        if not user or not user.is_authenticated:
            return False
        if self.assigned_to_id == user.id:
            return True
        return self.approved_helpers.filter(id=user.id).exists()

    def can_user_post(self, user):
        """Return True if the user may write in the task chat room.

        In team mode only the coordinator and approved helpers can post.
        Old tasks (team_mode=False) keep the previous behaviour where every
        group member can write.
        """
        if not user or not user.is_authenticated:
            return False
        if not self.team_mode:
            return True
        return self.is_user_approved(user)

    def approve_helper(self, user):
        """Coordinator action: add a willing helper to the team."""
        if not self.is_user_helper(user):
            raise ValueError(_("User is not a willing helper for this activity."))
        self.approved_helpers.add(user)

    def remove_helper(self, user):
        """Coordinator action: remove a user from the approved team (not from helpers list)."""
        self.approved_helpers.remove(user)


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
