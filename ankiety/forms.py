from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from home.widgets import RichTextWidget

from .models import Survey, SurveyOption


class DateTimeLocalInput(forms.DateTimeInput):
    input_type = "datetime-local"

    def format_value(self, value):
        if value is None:
            return ""
        if hasattr(value, "strftime"):
            if timezone.is_naive(value):
                local_time = value
            else:
                local_time = timezone.localtime(value)
            return local_time.strftime("%Y-%m-%dT%H:%M")
        return value


class SurveyForm(forms.ModelForm):
    options_text = forms.CharField(
        required=False,
        label=_("Options"),
        help_text=_("One option per line. At least 2 options are required."),
        widget=forms.Textarea(attrs={"rows": 6, "class": "form-control", "placeholder": _("e.g.\nOption A\nOption B\nOption C")}),
    )

    class Meta:
        model = Survey
        fields = ["title", "description", "end_date", "allow_multiple_choice"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": RichTextWidget(placeholder=_("Describe the survey."), max_length=3000),
            "end_date": DateTimeLocalInput(attrs={"class": "form-control"}),
            "allow_multiple_choice": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["options_text"].initial = self._options_to_text(self.instance.options.order_by("order", "id"))
            if not self.instance.is_active:
                self.fields["options_text"].disabled = True
                self.fields["options_text"].help_text = _("The survey is closed; options cannot be changed.")
            elif self.instance.votes.exists():
                self.fields["options_text"].help_text = _("You can change options while the survey is ongoing. Renaming or removing an option will delete votes cast for it.")

    @staticmethod
    def _options_to_text(options):
        return "\n".join(opt.text for opt in options)

    def clean_end_date(self):
        end_date = self.cleaned_data.get("end_date")
        if end_date:
            if timezone.is_naive(end_date):
                end_date = timezone.make_aware(end_date)
            if end_date <= timezone.now():
                raise forms.ValidationError(_("End date must be in the future."))
        return end_date

    def clean_options_text(self):
        options_text = self.cleaned_data.get("options_text", "")

        options = [line.strip() for line in options_text.splitlines()]
        options = [line for line in options if line]

        if len(options) < 2:
            raise forms.ValidationError(_("Enter at least 2 options."))

        seen = set()
        unique = []
        for opt in options:
            if opt not in seen:
                seen.add(opt)
                unique.append(opt)

        if len(unique) != len(options):
            raise forms.ValidationError(_("Each option must be unique."))

        return unique

    def create_options(self, survey):
        """Create or update survey options from the parsed options_text."""
        options = self.cleaned_data.get("options_text", [])
        if not options:
            return

        # Options of a closed survey are locked.
        if survey.options.exists() and not survey.is_active:
            return

        existing = {opt.text: opt for opt in survey.options.order_by("order", "id")}
        kept_ids = set()
        to_create = []

        for idx, text in enumerate(options):
            if text in existing:
                opt = existing[text]
                if opt.order != idx:
                    opt.order = idx
                    opt.save(update_fields=["order"])
                kept_ids.add(opt.pk)
            else:
                to_create.append(SurveyOption(survey=survey, text=text, order=idx))

        # Remove options that no longer appear (and their votes via CASCADE).
        survey.options.exclude(pk__in=kept_ids).delete()

        if to_create:
            SurveyOption.objects.bulk_create(to_create)
