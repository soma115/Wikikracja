from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Field, Layout, Row, Submit
from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from home.widgets import RichTextWidget

from .models import Event


class DateTimeLocalInput(forms.DateTimeInput):
    input_type = 'datetime-local'

    def format_value(self, value):
        if value is None:
            return ''
        if hasattr(value, 'strftime'):
            # Convert to local timezone for datetime-local input
            if timezone.is_naive(value):
                # If naive, assume it's already in local timezone
                local_time = value
            else:
                # If aware, convert to local timezone
                local_time = timezone.localtime(value)
            return local_time.strftime('%Y-%m-%dT%H:%M')
        return value


class EventForm(forms.ModelForm):
    # Separate fields for ordinal and weekday selection
    ordinal = forms.ChoiceField(
        required=False,
        label=_('Week of month'),
        help_text=_('Which occurrence in the month?'),
        choices=[('', '----'), ('1', _('First')), ('2', _('Second')), ('3', _('Third')), ('4', _('Fourth')), ('-1', _('Last'))],
    )

    weekday = forms.ChoiceField(
        required=False,
        label=_('Day of week'),
        help_text=_('Which day of the week?'),
        choices=[('', '----'), ('0', _('Monday')), ('1', _('Tuesday')), ('2', _('Wednesday')), ('3', _('Thursday')), ('4', _('Friday')), ('5', _('Saturday')), ('6', _('Sunday'))],
    )

    class Meta:
        model = Event
        fields = ['title', 'description', 'link', 'place', 'start_date', 'end_date', 'frequency', 'is_active', 'is_public']
        widgets = {
            'start_date': DateTimeLocalInput(),
            'end_date': DateTimeLocalInput(),
            'description': RichTextWidget(),
            'link': forms.URLInput(attrs={'placeholder': 'https://example.com'}),
            'place': forms.TextInput(attrs={'placeholder': _('Event location or venue')}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # If editing an existing event with ordinal values, set both fields
        if self.instance.pk:
            if self.instance.monthly_ordinal is not None:
                self.fields['ordinal'].initial = str(self.instance.monthly_ordinal)
            if self.instance.monthly_weekday is not None:
                self.fields['weekday'].initial = str(self.instance.monthly_weekday)

        # Add helpful labels and help text (these will override model help_text if needed)
        # Note: Since we now have help_text in the model, these are optional overrides
        # The model's help_text will be used automatically

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Field('title', css_class='form-control'),
            Field('description', css_class='form-control'),
            Row(Column('link', css_class='mb-3 col-md-6'), Column('place', css_class='mb-3 col-md-6')),
            Row(Column('start_date', css_class='mb-3 col-md-6'), Column('end_date', css_class='mb-3 col-md-6')),
            Field('frequency', css_class='form-control', wrapper_class='mb-3'),
            Row(Column('ordinal', css_class='mb-3 col-md-6'), Column('weekday', css_class='mb-3 col-md-6'), css_id='ordinal-fields-row', css_class='ordinal-fields-row'),
            Row(Column('is_active', css_class='mb-3 col-md-6'), Column('is_public', css_class='mb-3 col-md-6')),
            Submit('submit', _('Save Event'), css_class='btn btn-primary'),
        )

    def clean_start_date(self):
        start_date = self.cleaned_data.get('start_date')
        if start_date:
            # datetime-local input comes without timezone info
            # Django treats it as current timezone, which is correct
            if timezone.is_naive(start_date):
                # Make timezone-aware using current timezone
                start_date = timezone.make_aware(start_date)
        return start_date

    def clean_end_date(self):
        end_date = self.cleaned_data.get('end_date')
        if end_date:
            # datetime-local input comes without timezone info
            # Django treats it as current timezone, which is correct
            if timezone.is_naive(end_date):
                # Make timezone-aware using current timezone
                end_date = timezone.make_aware(end_date)
        return end_date

    def clean(self):
        cleaned_data = super().clean()
        frequency = cleaned_data.get('frequency')
        ordinal = cleaned_data.get('ordinal')
        weekday = cleaned_data.get('weekday')

        # If frequency is monthly_ordinal, validate that both fields are set
        if frequency == 'monthly_ordinal':
            if not ordinal:
                self.add_error('ordinal', _('This field is required for monthly ordinal events.'))
            if not weekday:
                self.add_error('weekday', _('This field is required for monthly ordinal events.'))

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Get values from both fields
        ordinal = self.cleaned_data.get('ordinal')
        weekday = self.cleaned_data.get('weekday')

        if ordinal and weekday:
            instance.monthly_ordinal = int(ordinal)
            instance.monthly_weekday = int(weekday)
        else:
            # Clear values if not set
            instance.monthly_ordinal = None
            instance.monthly_weekday = None

        if commit:
            instance.save()
        return instance
