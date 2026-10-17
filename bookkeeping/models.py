from datetime import datetime

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class Category(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name=_("Name"))

    def __str__(self):
        return self.name


class Partner(models.Model):
    name = models.CharField(max_length=200, unique=True, verbose_name=_("Name"))
    email = models.EmailField(null=True, blank=True, verbose_name=_("email"))
    phone = models.CharField(max_length=200, null=True, blank=True, verbose_name=_("Phone"))
    web_page = models.CharField(max_length=200, null=True, blank=True, verbose_name=_("Web page"))
    address = models.CharField(max_length=200, null=True, blank=True, verbose_name=_("Address"))
    city = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("City"))
    country = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("Country"))
    street = models.CharField(max_length=150, blank=True, default='', verbose_name=_("Street"))
    house_number = models.CharField(max_length=32, blank=True, default='', verbose_name=_("House number"))
    apartment_number = models.CharField(max_length=32, blank=True, default='', verbose_name=_("Apartment number"))
    notes = models.TextField(null=True, blank=True, verbose_name=_("Notes"))

    def __str__(self):
        return self.name


class Transaction(models.Model):
    INCOMING = 'I'
    OUTGOING = 'O'
    TYPES = [(INCOMING, _('Incoming')), (OUTGOING, _('Outgoing'))]
    type = models.CharField(max_length=1, choices=TYPES, default=INCOMING, verbose_name=_("Type"))

    created_date = models.DateField(auto_now_add=True, verbose_name=_("Created"))
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True, verbose_name=_("Last updated"))
    payment_received_date = models.DateField(null=True, blank=True, default=datetime.now, editable=True, verbose_name=_("Payment received date"))

    entity = models.ForeignKey('resources.Entity', on_delete=models.PROTECT, related_name='bookkeeping_transactions', verbose_name=_("Asset"))
    category = models.ForeignKey(Category, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("Category"))
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, null=True, blank=False, verbose_name=_("Partner"))
    amount = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=False, verbose_name=_("Amount"))
    note = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("Note"))
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Author"), related_name='transactions')

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields')
        if self.entity_id and (update_fields is None or {'entity', 'entity_id'}.intersection(update_fields)):
            from resources.models import Entity

            if not Entity.objects.filter(pk=self.entity_id, entity_type=Entity.Type.FINANCIAL_ASSET).exists():
                raise ValidationError({'entity': _('Select a financial asset.')})
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.payment_received_date} - {self.partner} {self.type} {self.amount} {self.entity}"
