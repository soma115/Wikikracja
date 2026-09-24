from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from tinymce.widgets import TinyMCE

from .models import Post


class PostForm(forms.ModelForm):
    SYSTEM_LOCKED_FIELDS = ('title', 'category', 'visibility', 'is_important')

    text = forms.CharField(
        widget=TinyMCE(mce_attrs={"content_style": "ul { list-style-type: disc; padding-left: 2rem; } ol { list-style-type: decimal; padding-left: 2rem; } li { margin-bottom: .35rem; }"}), label=_("Text")
    )

    attachments = forms.FileField(required=False, label=_("Attachments"))

    class Meta:
        model = Post
        fields = ('title', 'subtitle', 'category', 'text', 'visibility', 'is_important', 'featured_image', 'slug')

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_enctype = 'multipart/form-data'
        self.helper.add_input(Submit('submit', _('Save')))
        self.fields['visibility'].required = False
        self.fields['visibility'].help_text = _('Who can see this document')
        if self.instance and self.instance.pk and self.instance.system_key:
            self.initial['title'] = self.instance.get_display_title()
        self.fields['is_important'].help_text = _('The Important chat room will be notified')
        if self.instance and self.instance.pk and self.instance.system_key:
            for field_name in self.SYSTEM_LOCKED_FIELDS:
                self.fields[field_name].disabled = True
                self.fields[field_name].help_text = _('This field cannot be changed for a system document.')
        self.fields['featured_image'].help_text = _("Maximum image size: %(max_size)s MB.") % {'max_size': settings.UPLOAD_IMAGE_MAX_SIZE_MB}
        self.fields['featured_image'].widget.attrs['data-max-size-mb'] = settings.UPLOAD_IMAGE_MAX_SIZE_MB
        self.fields['featured_image'].widget.attrs['data-max-size-error'] = _("Image is too large (max %s MB).")
        self.fields['attachments'].help_text = _("Maximum file size: %(max_size)s MB.") % {'max_size': settings.UPLOAD_ATTACHMENT_MAX_SIZE_MB}

    def clean_featured_image(self):
        image = self.cleaned_data.get('featured_image')
        if image:
            max_size = settings.UPLOAD_IMAGE_MAX_SIZE_MB * 1_000_000
            if image.size > max_size:
                raise ValidationError(_("Image is too large (max %(max_size)s MB)."), code='file_too_large', params={'max_size': settings.UPLOAD_IMAGE_MAX_SIZE_MB})
        return image

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('visibility'):
            cleaned_data['visibility'] = self.instance.visibility if self.instance.pk else Post.Visibility.GROUP
        if cleaned_data.get('visibility') == Post.Visibility.PRIVATE and self.instance.pk and self.instance.author_id != getattr(self.user, 'pk', None):
            self.add_error('visibility', _('Only the author can make a document private.'))
        files = getattr(self, 'files', None)
        if files:
            max_size = settings.UPLOAD_ATTACHMENT_MAX_SIZE_MB * 1_000_000
            errors = []
            for attachment in files.getlist('attachments'):
                if attachment.size > max_size:
                    errors.append(
                        ValidationError(
                            _("File '%(filename)s' is too large (max %(max_size)s MB)."), code='file_too_large', params={'filename': attachment.name, 'max_size': settings.UPLOAD_ATTACHMENT_MAX_SIZE_MB}
                        )
                    )
            if errors:
                self.add_error('attachments', errors)
        return cleaned_data
