from django import forms
from django.utils.translation import gettext_lazy as _

from core.widgets import RichTextWidget

from .models import Category, Task


class TaskForm(forms.ModelForm):
    category = forms.ModelChoiceField(queryset=Category.objects.all(), required=False, empty_label=_("— no category —"), widget=forms.Select(attrs={"class": "tw-form-select"}))
    estimated_cost = forms.DecimalField(min_value=0, max_digits=12, decimal_places=2, widget=forms.NumberInput(attrs={"class": "tw-form-control", "step": "0.01"}))
    currency = forms.CharField(max_length=16, required=False, widget=forms.TextInput(attrs={"class": "tw-form-control"}))
    required_people = forms.IntegerField(min_value=1, max_value=32767, widget=forms.NumberInput(attrs={"class": "tw-form-control", "min": "1", "max": "32767", "step": "1"}))
    requires_external_approval = forms.TypedChoiceField(choices=(("true", _("Yes")), ("false", _("No"))), coerce=lambda value: value == "true", required=True, widget=forms.RadioSelect)
    success_criteria = forms.CharField(widget=forms.Textarea(attrs={"class": "tw-form-control", "rows": 3}))
    due_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"class": "tw-form-control", "type": "date"}))

    class Meta:
        model = Task
        fields = ["title", "description", "estimated_cost", "currency", "required_people", "requires_external_approval", "success_criteria", "due_date", "category"]
        widgets = {"title": forms.TextInput(attrs={"class": "tw-form-control"}), "description": RichTextWidget(placeholder=_("Describe the activity. Ctrl+B / Ctrl+I / Ctrl+U for formatting."))}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound and self.instance.requires_external_approval is not None:
            value = "true" if self.instance.requires_external_approval else "false"
            self.initial["requires_external_approval"] = value

    def clean_currency(self):
        return self.cleaned_data["currency"].strip()

    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get("estimated_cost")
        currency = cleaned_data.get("currency")
        if amount is not None and amount > 0 and not currency:
            self.add_error("currency", _("Enter a currency when the estimated cost is greater than zero."))
        return cleaned_data


class TaskMetadataForm(TaskForm):
    class Meta(TaskForm.Meta):
        fields = ["due_date", "category"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields = {name: field for name, field in self.fields.items() if name in self.Meta.fields}


class TaskStatusForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = [(Task.Status.COMPLETED, Task.Status.COMPLETED.label), (Task.Status.CANCELLED, Task.Status.CANCELLED.label)]

    class Meta:
        model = Task
        fields = ["status"]
        widgets = {"status": forms.Select(attrs={"class": "tw-form-control"})}

    def clean_status(self):
        status = self.cleaned_data["status"]
        if status not in (Task.Status.COMPLETED, Task.Status.CANCELLED):
            raise forms.ValidationError(_("Invalid closing status."))
        return status
