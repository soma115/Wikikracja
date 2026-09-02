from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from tinymce.widgets import TinyMCE

from .models import Post


class PostForm(forms.ModelForm):
    text = forms.CharField(widget=TinyMCE(), label=_("Text"))
    attachments = forms.FileField(required=False, label=_("Attachments"))

    class Meta:
        model = Post
        fields = ('title', 'subtitle', 'category', 'text', 'is_public', 'is_important', 'featured_image', 'slug')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_enctype = 'multipart/form-data'
        self.helper.add_input(Submit('submit', _('Save'), css_class='btn-primary'))
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
