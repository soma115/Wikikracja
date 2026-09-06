from datetime import datetime

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Asset, Category, Partner, Transaction


class AssetForm(forms.ModelForm):
    """Form for creating and updating Asset records."""

    class Meta:
        model = Asset
        fields = ['code', 'name', 'symbol', 'decimal_places', 'is_currency', 'is_default']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', _('Save'), css_class='btn-primary'))


class TransactionForm(forms.ModelForm):
    """Form for creating and updating Transaction records."""

    TYPE_CHOICES = [('I', _('Incoming')), ('O', _('Outgoing'))]

    type = forms.ChoiceField(choices=TYPE_CHOICES, label=_('Type'), widget=forms.RadioSelect(attrs={'class': 'form-check-inline'}))

    asset = forms.ModelChoiceField(queryset=Asset.objects.all().order_by('code'), label=_('Asset'), empty_label=None)

    partner = forms.ModelChoiceField(queryset=Partner.objects.all().order_by('name'), label=_('Partner'), empty_label=_('Select partner'))

    category = forms.ModelChoiceField(queryset=Category.objects.all().order_by('name'), required=True, label=_('Category'))

    amount = forms.DecimalField(label=_('Amount'), min_value=0, decimal_places=8, widget=forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'id': 'id_amount'}))

    payment_received_date = forms.DateField(initial=datetime.now, label=_('Payment received date'), widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}), input_formats=['%Y-%m-%d'])

    note = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}), label=_('Note'))

    class Meta:
        model = Transaction
        fields = ['type', 'asset', 'partner', 'category', 'amount', 'payment_received_date', 'note']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', _('Save'), css_class='btn-primary'))

        # Format today's date as YYYY-MM-DD for new instances
        if not self.instance or not self.instance.pk:
            self.initial['payment_received_date'] = datetime.now().strftime('%Y-%m-%d')

        # Format the existing date for editing instances
        elif self.instance.payment_received_date:
            self.initial['payment_received_date'] = self.instance.payment_received_date.strftime('%Y-%m-%d')
