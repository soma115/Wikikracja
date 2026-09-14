from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from categories.models import AbstractCategory
from chat.models import ChatRoomModel

User = get_user_model()


class PostCategory(AbstractCategory):
    priority = models.PositiveIntegerField(default=10, verbose_name=_("Priority"))

    def delete(self, *args, **kwargs):
        if self.is_protected:
            raise ValidationError(_("Protected categories cannot be deleted."))
        return super().delete(*args, **kwargs)

    class Meta(AbstractCategory.Meta):
        ordering = ['priority', 'name']
        verbose_name = _("Post Category")
        verbose_name_plural = _("Post Categories")


class Post(ChatRoomModel, models.Model):
    class Visibility(models.TextChoices):
        PRIVATE = 'private', _('Only me')
        GROUP = 'group', _('Group')
        PUBLIC = 'public', _('Public')
        ARCHIVE = 'archive', _('Archive')

    title = models.CharField(max_length=200, verbose_name=_("Title"))
    subtitle = models.CharField(max_length=200, null=True, blank=True, verbose_name=_("Subtitle"))
    text = models.TextField(verbose_name=_("Text"))
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name=_("Author"))
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="updated_board_posts", verbose_name=_("Updated by"))
    created = models.DateTimeField(auto_now_add=True, verbose_name=_("Created"))
    updated = models.DateTimeField(auto_now=True, verbose_name=_("Updated"))
    category = models.ForeignKey(PostCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name="posts", verbose_name=_("Category"))
    visibility = models.CharField(max_length=10, choices=Visibility.choices, default=Visibility.GROUP, verbose_name=_("Visibility"))
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

    def save(self, *args, **kwargs):
        original = type(self).objects.filter(pk=self.pk).values('system_key', 'category_id', 'visibility', 'is_important').first() if self.pk else None
        self._previous_visibility = original['visibility'] if original else None
        self._previous_is_important = original['is_important'] if original else None
        if original and original['system_key']:
            self.system_key = original['system_key']
            self.category_id = original['category_id']
            self.visibility = original['visibility']
            self.is_important = True
        if self.system_key:
            self.visibility = self.Visibility.PUBLIC
            self.is_important = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.system_key:
            raise ValidationError(_("System posts cannot be deleted."))
        return super().delete(*args, **kwargs)

    @classmethod
    def get_system_post(cls, system_key):
        return cls.objects.filter(system_key=system_key).first()

    @classmethod
    def visibility_filter_for_user(cls, user, *, include_archive=False):
        if not user.is_authenticated:
            return Q(visibility=cls.Visibility.PUBLIC)
        visible = Q(visibility__in=(cls.Visibility.GROUP, cls.Visibility.PUBLIC)) | Q(system_key__isnull=False)
        visible |= Q(visibility=cls.Visibility.PRIVATE, author=user)
        if include_archive:
            visible |= Q(visibility=cls.Visibility.ARCHIVE)
        return visible

    @classmethod
    def editable_filter_for_user(cls, user):
        return Q(visibility__in=(cls.Visibility.GROUP, cls.Visibility.PUBLIC)) | Q(visibility=cls.Visibility.PRIVATE, author=user)

    def can_edit(self, user):
        return user.is_authenticated and self.visibility != self.Visibility.ARCHIVE and (self.visibility != self.Visibility.PRIVATE or self.author_id == user.pk)


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
