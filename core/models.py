from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

User = get_user_model()


class ReadStatus(models.Model):
    """Track which users have read which content"""

    class ContentType(models.TextChoices):
        POST = 'post', _('Post')
        TASK = 'task', pgettext_lazy('task', 'Activity')
        EVENT = 'event', _('Event')
        MESSAGE = 'message', _('Message')
        DECISION = 'decision', _('Decision')
        CITIZEN = 'citizen', _('Citizen Activity')
        SURVEY = 'survey', _('Survey')

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content_type = models.CharField(max_length=20, choices=ContentType.choices)
    object_id = models.PositiveIntegerField()
    read_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'home_readstatus'
        unique_together = ['user', 'content_type', 'object_id']
        indexes = [models.Index(fields=['user', 'content_type'], name='readstatus_user_content_idx')]

    def __str__(self):
        return f"{self.user.username} read {self.content_type} #{self.object_id}"
