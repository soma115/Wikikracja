from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Survey(models.Model):
    title = models.CharField(max_length=200, verbose_name=_("Title"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    end_date = models.DateTimeField(
        verbose_name=_("End date"),
        help_text=_("After this moment the survey will be closed."),
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="surveys",
        verbose_name=_("Author"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Survey")
        verbose_name_plural = _("Surveys")

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("ankiety:detail", kwargs={"pk": self.pk})

    @property
    def is_active(self):
        return self.end_date >= timezone.now()


class SurveyOption(models.Model):
    survey = models.ForeignKey(
        Survey,
        on_delete=models.CASCADE,
        related_name="options",
        verbose_name=_("Survey"),
    )
    text = models.CharField(max_length=200, verbose_name=_("Option text"))
    order = models.PositiveSmallIntegerField(default=0, verbose_name=_("Order"))

    class Meta:
        ordering = ["order", "id"]
        verbose_name = _("Survey option")
        verbose_name_plural = _("Survey options")

    def __str__(self):
        return self.text


class SurveyVote(models.Model):
    survey = models.ForeignKey(
        Survey,
        on_delete=models.CASCADE,
        related_name="votes",
        verbose_name=_("Survey"),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="survey_votes",
        verbose_name=_("User"),
    )
    option = models.ForeignKey(
        SurveyOption,
        on_delete=models.CASCADE,
        related_name="votes",
        verbose_name=_("Chosen option"),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["survey", "user"],
                name="%(app_label)s_%(class)s_unique_vote",
            )
        ]
        ordering = ["-created_at"]
        verbose_name = _("Survey vote")
        verbose_name_plural = _("Survey votes")

    def __str__(self):
        return f"{self.user} -> {self.survey}: {self.option}"
