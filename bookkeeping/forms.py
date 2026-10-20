from datetime import datetime

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.utils.translation import gettext_lazy as _

from obywatele.map_data import normalize_country
from obywatele.models import Country, Uzytkownik
from resources.models import Entity

from .models import Category, Partner, Transaction


class PartnerForm(forms.ModelForm):
    country = forms.ChoiceField(choices=(), required=False, label=_('Country'))

    class Meta:
        model = Partner
        fields = ('name', 'email', 'phone', 'web_page', 'address', 'city', 'country', 'street', 'house_number', 'apartment_number', 'notes')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        countries = list(Country.objects.order_by('name'))
        self.countries_by_code = {country.code: country for country in countries}
        country_rows = [(country.code, country.name) for country in countries]
        self.fields['country'].choices = country_rows
        if not self.is_bound:
            self.initial['country'] = normalize_country(self.instance.country, country_rows) or 'PL'

    def clean_country(self):
        country_code = self.cleaned_data.get('country') or normalize_country(self.instance.country) or 'PL'
        return self.countries_by_code[country_code].name


class AssetForm(forms.ModelForm):
    """Form for managing financial Entity records through legacy Asset URLs."""

    class Meta:
        model = Entity
        fields = ['code', 'name', 'symbol', 'decimal_places', 'is_currency', 'is_default']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk and not self.is_bound:
            self.initial.setdefault('is_currency', True)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', _('Save')))


class ActiveMemberChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, profile):
        return profile.uid.get_full_name() or profile.uid.get_username()


class ResourceEntityForm(forms.Form):
    kind = forms.ChoiceField(choices=(('', _('Select type')), *Entity.ResourceKind.choices), label=_('Type'))
    name = forms.CharField(max_length=200, label=_('Name'))
    description = forms.CharField(max_length=1866, required=False, label=_('Description'), widget=forms.Textarea(attrs={'rows': 3}))
    country = forms.ModelChoiceField(queryset=Country.objects.all(), required=False, label=_('Country'))
    city = forms.CharField(max_length=100, required=False, label=_('City'))
    street = forms.CharField(max_length=150, required=False, label=_('Street'))
    house_number = forms.CharField(max_length=32, required=False, label=_('House number'))
    apartment_number = forms.CharField(max_length=32, required=False, label=_('Apartment number'))

    def __init__(self, *args, profile=None, entity=None, can_assign=True, **kwargs):
        self.profile = profile
        self.entity = entity
        self.can_assign = can_assign
        super().__init__(*args, **kwargs)

        if can_assign:
            self.fields['assignment_scope'] = forms.ChoiceField(
                choices=(('', _('Select assignment')), (Entity.AssignmentScope.MEMBER, Entity.AssignmentScope.MEMBER.label), (Entity.AssignmentScope.COMMUNITY, Entity.AssignmentScope.COMMUNITY.label)),
                label=_('Owner'),
            )
            member_queryset = Uzytkownik.objects.filter(uid__is_active=True).select_related('uid')
            self.fields['assigned_member'] = ActiveMemberChoiceField(
                queryset=member_queryset.order_by('uid__first_name', 'uid__last_name', 'uid__username'), required=False, label=_('Assigned member'), empty_label=_('Select a member')
            )

        if entity:
            self.initial.setdefault('kind', entity.resource_kind)
            self.initial.setdefault('name', entity.name)
            self.initial.setdefault('description', entity.description)
            self.initial.setdefault('country', entity.country_id)
            self.initial.setdefault('city', entity.city)
            self.initial.setdefault('street', entity.street)
            self.initial.setdefault('house_number', entity.house_number)
            self.initial.setdefault('apartment_number', entity.apartment_number)
            if can_assign:
                self.initial.setdefault('assignment_scope', entity.assignment_scope)
                self.initial.setdefault('assigned_member', entity.assigned_member_id)
        elif profile and can_assign:
            self.initial.setdefault('assignment_scope', Entity.AssignmentScope.MEMBER)
            self.initial.setdefault('assigned_member', profile.pk)

        self.show_address = any(self.data.get(field) if self.is_bound else self.initial.get(field) for field in ('country', 'city', 'street', 'house_number', 'apartment_number'))
        if not self.is_bound and not self.initial.get('country'):
            self.initial['country'] = Country.objects.get(code='PL').pk

    def clean_country(self):
        return self.cleaned_data['country'] or (self.entity.country if self.entity and self.entity.country_id else Country.objects.get(code='PL'))

    def clean_name(self):
        value = ' '.join((self.cleaned_data.get('name') or '').split())
        if not value:
            raise forms.ValidationError(_('Enter a name.'))
        return value

    def clean(self):
        cleaned_data = super().clean()
        kind = cleaned_data.get('kind')
        if not kind:
            self.add_error('kind', _('Select a type.'))
            return cleaned_data

        if self.can_assign:
            assignment_scope = cleaned_data.get('assignment_scope')
            assigned_member = cleaned_data.get('assigned_member')
            if assignment_scope == Entity.AssignmentScope.MEMBER and not assigned_member:
                self.add_error('assigned_member', _('Select a member for this assignment.'))
            elif assignment_scope == Entity.AssignmentScope.COMMUNITY and assigned_member:
                self.add_error('assigned_member', _('Community ownership cannot also be assigned to an individual.'))
            elif assignment_scope not in (Entity.AssignmentScope.MEMBER, Entity.AssignmentScope.COMMUNITY):
                self.add_error('assignment_scope', _('Select assignment.'))
        elif self.entity:
            assignment_scope = self.entity.assignment_scope
            assigned_member = self.entity.assigned_member
        else:
            assignment_scope = None
            assigned_member = None

        name = cleaned_data.get('name')
        if not name or self.errors:
            return cleaned_data

        duplicates = Entity.objects.filter(entity_type=Entity.Type.RESOURCE, name__iexact=name, resource_kind=kind)
        if self.entity:
            duplicates = duplicates.exclude(pk=self.entity.pk)
        if assignment_scope == Entity.AssignmentScope.COMMUNITY:
            duplicates = duplicates.filter(is_community_owned=True)
        elif assignment_scope == Entity.AssignmentScope.MEMBER and assigned_member:
            duplicates = duplicates.filter(is_community_owned=False, assigned_member=assigned_member)
        if duplicates.exists():
            self.add_error('name', _('This item is already assigned with this type.'))
        return cleaned_data


class TransactionForm(forms.ModelForm):
    """Form for creating and updating Transaction records."""

    TYPE_CHOICES = [('I', _('Incoming')), ('O', _('Outgoing'))]

    type = forms.ChoiceField(choices=TYPE_CHOICES, label=_('Type'), widget=forms.RadioSelect(attrs={'class': 'tw-form-check-inline'}))

    entity = forms.ModelChoiceField(queryset=Entity.objects.filter(entity_type=Entity.Type.FINANCIAL_ASSET).order_by('code'), label=_('Asset'), empty_label=None)

    partner = forms.ModelChoiceField(queryset=Partner.objects.all().order_by('name'), label=_('Partner'), empty_label=_('Select partner'))

    category = forms.ModelChoiceField(queryset=Category.objects.all().order_by('name'), required=True, label=_('Category'))

    amount = forms.DecimalField(label=_('Amount'), min_value=0, decimal_places=8, widget=forms.NumberInput(attrs={'class': 'tw-form-control', 'step': 'any', 'id': 'id_amount'}))

    payment_received_date = forms.DateField(initial=datetime.now, label=_('Payment received date'), widget=forms.DateInput(attrs={'type': 'date', 'class': 'tw-form-control'}), input_formats=['%Y-%m-%d'])

    note = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3, 'class': 'tw-form-control'}), label=_('Note'))

    class Meta:
        model = Transaction
        fields = ['type', 'entity', 'partner', 'category', 'amount', 'payment_received_date', 'note']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', _('Save')))

        # Format today's date as YYYY-MM-DD for new instances
        if not self.instance or not self.instance.pk:
            self.initial['payment_received_date'] = datetime.now().strftime('%Y-%m-%d')

        # Format the existing date for editing instances
        elif self.instance.payment_received_date:
            self.initial['payment_received_date'] = self.instance.payment_received_date.strftime('%Y-%m-%d')
