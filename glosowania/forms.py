from django import forms
from django.utils.translation import gettext_lazy as _

from site_settings.models import SiteParameters
from site_settings.params import PARAM_SPECS, coerce, specs_by_category
from site_settings.validators import validate_brand_mark_dimensions, validate_brand_mark_format, validate_branding_image_size
from zzz.widgets import CounterTextarea

from .models import Argument, Decyzja


class DecyzjaForm(forms.ModelForm):
    class Meta:
        model = Decyzja
        fields = ('title', 'tresc', 'uzasadnienie', 'kara', 'znosi')
        widgets = {
            'title': forms.TextInput(),
            'tresc': CounterTextarea(attrs={'rows': 8}, max_length=3000),
            'uzasadnienie': CounterTextarea(attrs={'rows': 8}, max_length=4000),
            'kara': CounterTextarea(attrs={'rows': 3}, max_length=500),
        }


class ArgumentForm(forms.ModelForm):
    class Meta:
        model = Argument
        fields = ('argument_type', 'content')
        widgets = {'content': CounterTextarea(attrs={'rows': 4}, max_length=1000)}


class ParametersProposalForm(forms.Form):
    """Dynamic form (built from PARAM_SPECS) to propose a change of system parameters.

    Pre-filled with current values. On submit it produces a dict of only the
    changed parameters, used to create a parameter referendum (Decyzja).
    """

    uzasadnienie = forms.CharField(label=_('Reasoning'), help_text=_('Why should these parameters change?'), widget=CounterTextarea(attrs={'rows': 8}, max_length=4000), max_length=4000)

    brand_mark = forms.ImageField(
        required=False,
        label=_('New logo (optional)'),
        help_text=_('PNG/JPEG/WebP/GIF, max 5 MB, any longest side 64-4096 px. Automatically resized to 1024×1024 px PNG and applied as the site logo if the referendum is approved.'),
        validators=[validate_branding_image_size, validate_brand_mark_dimensions, validate_brand_mark_format],
    )

    def __init__(self, *args, **kwargs):
        # Optional existing parameter referendum being edited. When provided,
        # fields are pre-filled with the previously proposed values (falling
        # back to current system values for unchanged parameters).
        self.decyzja = kwargs.pop('decyzja', None)
        super().__init__(*args, **kwargs)
        current = SiteParameters.get()
        proposed = (self.decyzja.proposed_parameters or {}) if self.decyzja else {}
        if self.decyzja and self.decyzja.uzasadnienie:
            self.fields['uzasadnienie'].initial = self.decyzja.uzasadnienie
        for spec in PARAM_SPECS:
            if spec.name in proposed:
                value = coerce(spec, proposed[spec.name])
            else:
                value = getattr(current, spec.name)
            help_text = spec.help_text
            if spec.kind == 'int':
                lo = spec.min_value if spec.min_value is not None else 0
                field = forms.IntegerField(min_value=lo, max_value=spec.max_value, initial=value)
                if spec.max_value is not None:
                    help_text = f'{help_text} ({_("allowed range")}: {lo}\u2013{spec.max_value})'
            elif spec.kind == 'bool':
                field = forms.BooleanField(required=False, initial=value)
            else:
                field = forms.CharField(required=False, initial=value, max_length=255)
            field.label = spec.label
            field.help_text = help_text
            field.spec = spec
            self.fields[spec.name] = field

    def grouped_fields(self):
        """Yield ``(category_label, [bound_field, ...])`` for template rendering."""
        for _key, label, specs in specs_by_category():
            yield label, [self[spec.name] for spec in specs]

    def changed_parameters(self):
        """Return ``{name: new_value}`` for parameters that differ from current values."""
        current = SiteParameters.get()
        changes = {}
        for spec in PARAM_SPECS:
            new_value = coerce(spec, self.cleaned_data[spec.name])
            old_value = coerce(spec, getattr(current, spec.name))
            if new_value != old_value:
                changes[spec.name] = new_value
        return changes

    def clean_brand_mark(self):
        file = self.cleaned_data.get('brand_mark')
        if not file:
            return file
        from site_settings.services import normalize_brand_mark

        return normalize_brand_mark(file)

    def clean(self):
        cleaned = super().clean()
        if not self.errors and not self.changed_parameters() and not cleaned.get('brand_mark'):
            raise forms.ValidationError(_('You did not change any parameter.'))
        return cleaned
