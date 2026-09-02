from django import forms
from django.utils.translation import gettext_lazy as _

from zzz.widgets import RichTextWidget

from .models import Category, Task


class TaskForm(forms.ModelForm):
    category = forms.ModelChoiceField(queryset=Category.objects.all(), required=False, empty_label=_("— no category —"), widget=forms.Select(attrs={"class": "form-select"}))

    class Meta:
        model = Task
        fields = ["title", "description", "category"]
        widgets = {"title": forms.TextInput(attrs={"class": "form-control"}), "description": RichTextWidget(placeholder=_("Describe the activity. Ctrl+B / Ctrl+I / Ctrl+U for formatting."))}


class TaskStatusForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = [(Task.Status.COMPLETED, Task.Status.COMPLETED.label), (Task.Status.CANCELLED, Task.Status.CANCELLED.label)]

    class Meta:
        model = Task
        fields = ["status"]
        widgets = {"status": forms.Select(attrs={"class": "form-control"})}

    def clean_status(self):
        status = self.cleaned_data["status"]
        if status not in (Task.Status.COMPLETED, Task.Status.CANCELLED):
            raise forms.ValidationError(_("Invalid closing status."))
        return status
