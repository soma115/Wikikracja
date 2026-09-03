from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from categories.models import AbstractCategory
from chat.models import ChatRoomModel

User = get_user_model()


class PostCategory(AbstractCategory):
    priority = models.PositiveIntegerField(default=10, verbose_name=_("Priority"))

    class Meta(AbstractCategory.Meta):
        ordering = ['priority', 'name']
        verbose_name = _("Post Category")
        verbose_name_plural = _("Post Categories")


class Post(ChatRoomModel, models.Model):
    title = models.CharField(max_length=200, verbose_name=_("Title"))
    subtitle = models.CharField(max_length=200, null=True, blank=True, verbose_name=_("Subtitle"))
    text = models.TextField(verbose_name=_("Text"))
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name=_("Author"))
    created = models.DateTimeField(auto_now_add=True, verbose_name=_("Created"))
    updated = models.DateTimeField(auto_now=True, verbose_name=_("Updated"))
    category = models.ForeignKey(PostCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name="posts", verbose_name=_("Category"))
    is_public = models.BooleanField(default=False, verbose_name=_("Public"))
    is_important = models.BooleanField(default=False, verbose_name=_("Important"))
    featured_image = models.ImageField(upload_to='board/featured/', null=True, blank=True, verbose_name=_("Featured Image"))
    system_key = models.CharField(max_length=50, unique=True, null=True, blank=True, verbose_name=_("System Key"))
    slug = models.SlugField(max_length=200, unique=True, null=True, blank=True, verbose_name=_("Link Alias"))

    def __str__(self):
        return self.title

    def get_chat_room_title(self):
        return f"Document #{self.id}: {self.title}"[:90]

    def get_chat_room_url(self):
        if self.chat_room_id:
            return f"{reverse('chat:chat')}#room_id={self.chat_room_id}"
        return None

    @property
    def chat_room_url(self):
        return self.get_chat_room_url()

    def delete(self, *args, **kwargs):
        if self.system_key:
            raise ValidationError(_("System posts cannot be deleted."))
        return super().delete(*args, **kwargs)

    @classmethod
    def get_system_post(cls, system_key):
        return cls.objects.filter(system_key=system_key).first()


class PostAttachment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='attachments', verbose_name=_("Post"))
    file = models.FileField(upload_to='board/attachments/', verbose_name=_("File"))
    filename = models.CharField(max_length=255, verbose_name=_("Filename"))
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Uploaded At"))

    class Meta:
        verbose_name = _("Post Attachment")
        verbose_name_plural = _("Post Attachments")
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.filename
