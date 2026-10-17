from datetime import datetime

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.utils.translation import gettext_lazy as _

from obywatele.models import Country, Uzytkownik
from resources.models import Entity

from .models import Category, Partner, Transaction


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


class PhysicalAssetForm(forms.ModelForm):
    country = forms.ModelChoiceField(queryset=Country.objects.all(), to_field_name='code', label=_('Country'), empty_label=None)

    def __init__(self, *args, can_assign=True, assignment_entity=None, author=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.can_assign = can_assign
        if author and not self.instance.pk:
            self.instance.author = author

        if not can_assign:
            self.fields.pop('assignment_scope', None)
            self.fields.pop('assigned_member', None)
            return

        self.fields['assignment_scope'] = forms.ChoiceField(
            choices=(('', _('Select assignment')), (Entity.AssignmentScope.MEMBER, Entity.AssignmentScope.MEMBER.label), (Entity.AssignmentScope.COMMUNITY, Entity.AssignmentScope.COMMUNITY.label)),
            label=_('Current assignment'),
        )
        member_queryset = Uzytkownik.objects.filter(uid__is_active=True).select_related('uid')
        self.fields['assigned_member'] = ActiveMemberChoiceField(
            queryset=member_queryset.order_by('uid__first_name', 'uid__last_name', 'uid__username'), required=False, label=_('Assigned member'), empty_label=_('Select a member')
        )

        if assignment_entity:
            self.initial['assignment_scope'] = assignment_entity.assignment_scope
            self.initial['assigned_member'] = assignment_entity.assigned_member_id

    class Meta:
        model = Entity
        fields = ('name', 'country', 'city', 'street', 'house_number', 'apartment_number')

    def clean(self):
        cleaned_data = super().clean()
        if not self.can_assign:
            return cleaned_data

        assignment_scope = cleaned_data.get('assignment_scope')
        assigned_member = cleaned_data.get('assigned_member')
        if assignment_scope == Entity.AssignmentScope.MEMBER and not assigned_member:
            self.add_error('assigned_member', _('Select a member for this assignment.'))
        elif assignment_scope == Entity.AssignmentScope.COMMUNITY and assigned_member:
            self.add_error('assigned_member', _('Community ownership cannot also be assigned to an individual.'))
        elif assignment_scope == Entity.AssignmentScope.MEMBER:
            self.instance.is_community_owned = False
            self.instance.assigned_member = assigned_member
        elif assignment_scope == Entity.AssignmentScope.COMMUNITY:
            self.instance.is_community_owned = True
            self.instance.assigned_member = None
        return cleaned_data


class ActiveMemberChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, profile):
        return profile.uid.get_full_name() or profile.uid.get_username()


class ResourceEntityForm(forms.Form):
    kind = forms.ChoiceField(choices=(('', _('Select type')), *Entity.ResourceKind.choices), label=_('Type'))
    name = forms.CharField(max_length=200, label=_('Name'))
    description = forms.CharField(max_length=1866, required=False, label=_('Description'), widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, profile=None, entity=None, can_assign=True, **kwargs):
        self.profile = profile
        self.entity = entity
        self.can_assign = can_assign
        super().__init__(*args, **kwargs)

        if can_assign:
            self.fields['assignment_scope'] = forms.ChoiceField(
                choices=(('', _('Select assignment')), (Entity.AssignmentScope.MEMBER, Entity.AssignmentScope.MEMBER.label), (Entity.AssignmentScope.COMMUNITY, Entity.AssignmentScope.COMMUNITY.label)),
                label=_('Current assignment'),
            )
            member_queryset = Uzytkownik.objects.filter(uid__is_active=True).select_related('uid')
            self.fields['assigned_member'] = ActiveMemberChoiceField(
                queryset=member_queryset.order_by('uid__first_name', 'uid__last_name', 'uid__username'), required=False, label=_('Assigned member'), empty_label=_('Select a member')
            )

        if entity:
            self.initial.setdefault('kind', entity.resource_kind)
            self.initial.setdefault('name', entity.name)
            self.initial.setdefault('description', entity.description)
            if can_assign:
                self.initial.setdefault('assignment_scope', entity.assignment_scope)
                self.initial.setdefault('assigned_member', entity.assigned_member_id)
        elif profile and can_assign:
            self.initial.setdefault('assignment_scope', Entity.AssignmentScope.MEMBER)
            self.initial.setdefault('assigned_member', profile.pk)

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
