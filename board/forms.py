from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
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
