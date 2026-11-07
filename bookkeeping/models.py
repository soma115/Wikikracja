from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name=_("Name"))
    description = models.TextField(blank=True, default="", verbose_name=_("Description"))
    is_protected = models.BooleanField(default=False, verbose_name=_("Protected"))
    order = models.PositiveIntegerField(default=0, verbose_name=_("Order"))

    class Meta:
        ordering = ("order", "name", "pk")

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


class PaymentPlan(models.Model):
    class Direction(models.TextChoices):
        INCOMING = 'I', _('Incoming')
        OUTGOING = 'O', _('Outgoing')

    class Recurrence(models.TextChoices):
        ONCE = 'once', _('One time')
        MONTHLY = 'monthly', _('Monthly')
        YEARLY = 'yearly', _('Yearly')

    name = models.CharField(max_length=200, verbose_name=_('Name'))
    description = models.TextField(blank=True, default='', verbose_name=_('Description'))
    direction = models.CharField(max_length=1, choices=Direction.choices, verbose_name=_('Direction'))
    amount = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal('0'), validators=[MinValueValidator(Decimal('0'))], verbose_name=_('Amount'))
    entity = models.ForeignKey('resources.Entity', on_delete=models.PROTECT, related_name='payment_plans', verbose_name=_('Financial asset'))
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='payment_plans', verbose_name=_('Category'))
    partner = models.ForeignKey(Partner, on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_plans', verbose_name=_('Recipient'))
    debtors = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='payment_plans_as_debtor', verbose_name=_('Members who pay'))
    debtor_partners = models.ManyToManyField(Partner, blank=True, related_name='payment_plans_as_debtor', verbose_name=_('Partners who pay'))
    recurrence = models.CharField(max_length=10, choices=Recurrence.choices, default=Recurrence.MONTHLY, verbose_name=_('Recurrence'))
    first_due_date = models.DateField(verbose_name=_('First due date'))
    next_due_date = models.DateField(null=True, blank=True, verbose_name=_('Next period to generate'))
    last_generated_date = models.DateField(null=True, blank=True, verbose_name=_('Last generated period'))
    treasurer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='treasurer_payment_plans', verbose_name=_('Treasurer'))
    is_active = models.BooleanField(default=True, verbose_name=_('Active'))
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_payment_plans', verbose_name=_('Author'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Last updated'))

    class Meta:
        ordering = ('first_due_date', 'name', 'pk')
        constraints = [
            models.CheckConstraint(condition=Q(direction__in=('I', 'O')), name='payment_plan_known_direction'),
            models.CheckConstraint(condition=Q(recurrence__in=('once', 'monthly', 'yearly')), name='payment_plan_known_recurrence'),
        ]

    def clean(self):
        super().clean()
        if self.entity_id:
            from resources.models import Entity

            if not Entity.objects.filter(pk=self.entity_id, entity_type=Entity.Type.FINANCIAL_ASSET).exists():
                raise ValidationError({'entity': _('Select a financial asset.')})

    def __str__(self):
        return self.name


class PaymentDue(models.Model):
    plan = models.ForeignKey(PaymentPlan, on_delete=models.PROTECT, related_name='dues', verbose_name=_('Payment plan'))
    name = models.CharField(max_length=200, verbose_name=_('Name'))
    direction = models.CharField(max_length=1, choices=PaymentPlan.Direction.choices, verbose_name=_('Direction'))
    amount = models.DecimalField(max_digits=20, decimal_places=8, validators=[MinValueValidator(Decimal('0'))], verbose_name=_('Amount'))
    entity = models.ForeignKey('resources.Entity', on_delete=models.PROTECT, related_name='payment_dues', verbose_name=_('Financial asset'))
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='payment_dues', verbose_name=_('Category'))
    partner = models.ForeignKey(Partner, on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_dues', verbose_name=_('Recipient'))
    due_date = models.DateField(verbose_name=pgettext_lazy('payment due', 'Due date'))
    debtor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_dues', verbose_name=_('Member'))
    debtor_partner = models.ForeignKey(Partner, on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_dues_as_debtor', verbose_name=_('Partner who pays'))
    treasurer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='treasurer_payment_dues', verbose_name=_('Treasurer'))
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Cancelled at'))
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='cancelled_payment_dues', verbose_name=_('Cancelled by'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Last updated'))

    class Meta:
        ordering = ('due_date', 'name', 'pk')
        constraints = [
            models.CheckConstraint(condition=Q(direction__in=('I', 'O')), name='payment_due_known_direction'),
            models.UniqueConstraint(fields=('plan', 'due_date', 'debtor'), condition=Q(debtor__isnull=False), name='payment_due_member_period_unique'),
            models.UniqueConstraint(fields=('plan', 'due_date', 'debtor_partner'), condition=Q(debtor_partner__isnull=False), name='payment_due_partner_period_unique'),
            models.UniqueConstraint(fields=('plan', 'due_date'), condition=Q(debtor__isnull=True, debtor_partner__isnull=True), name='payment_due_shared_period_unique'),
        ]

    @property
    def is_paid(self):
        transaction = self.transaction
        return transaction is not None and transaction.status == Transaction.Status.POSTED

    @property
    def status(self):
        if self.is_paid:
            return 'paid'
        if self.cancelled_at:
            return 'cancelled'
        return 'pending'

    @property
    def paid_at(self):
        transaction = self.transaction
        return transaction.payment_received_date if transaction else None

    @property
    def paid_by(self):
        transaction = self.transaction
        return transaction.author if transaction else None

    @property
    def transaction(self):
        try:
            return self.payment_transaction
        except Transaction.DoesNotExist:
            return None

    @property
    def transaction_id(self):
        transaction = self.transaction
        return transaction.pk if transaction else None

    @property
    def is_overdue(self):
        return not self.is_paid and not self.cancelled_at and self.due_date < timezone.localdate()

    def __str__(self):
        return f'{self.name} — {self.due_date}'


class PaymentReminderDelivery(models.Model):
    class Channel(models.TextChoices):
        EMAIL = 'email', _('E-mail')
        PUSH = 'push', _('Push')

    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        SENDING = 'sending', _('Sending')
        SENT = 'sent', _('Sent')
        SKIPPED = 'skipped', _('Skipped')

    due = models.ForeignKey(PaymentDue, on_delete=models.CASCADE, related_name='reminder_deliveries')
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payment_reminder_deliveries')
    channel = models.CharField(max_length=5, choices=Channel.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    claimed_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=500, blank=True, default='')

    class Meta:
        constraints = [models.UniqueConstraint(fields=('due', 'recipient', 'channel'), name='payment_reminder_recipient_channel_unique')]
        ordering = ('due_id', 'recipient_id', 'channel')


class Transaction(models.Model):
    class Status(models.TextChoices):
        PLANNED = 'planned', _('Planned')
        POSTED = 'posted', _('Posted')

    INCOMING = 'I'
    OUTGOING = 'O'
    TYPES = [(INCOMING, _('Incoming')), (OUTGOING, _('Outgoing'))]
    type = models.CharField(max_length=1, choices=TYPES, default=INCOMING, verbose_name=_("Type"))
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.POSTED, verbose_name=_('Status'))

    created_date = models.DateField(auto_now_add=True, verbose_name=_("Created"))
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True, verbose_name=_("Last updated"))
    payment_received_date = models.DateField(null=True, blank=True, default=datetime.now, editable=True, verbose_name=_("Payment received date"))

    entity = models.ForeignKey('resources.Entity', on_delete=models.PROTECT, related_name='bookkeeping_transactions', verbose_name=_("Asset"))
    category = models.ForeignKey(Category, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("Category"))
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("Partner"))
    amount = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=False, verbose_name=_("Amount"))
    note = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("Note"))
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Author"), related_name='transactions')
    payment_due = models.OneToOneField(PaymentDue, on_delete=models.PROTECT, null=True, blank=True, related_name='payment_transaction', verbose_name=_('Payment due'))

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(status__in=('planned', 'posted')), name='transaction_known_status'),
            models.CheckConstraint(condition=(~Q(status='planned') | Q(payment_due__isnull=False)), name='transaction_planned_has_due'),
        ]

    def clean(self):
        super().clean()
        if self.status == self.Status.PLANNED and not self.payment_due_id:
            raise ValidationError({'payment_due': _('A planned transaction must have a payment due.')})
        if self.payment_due_id:
            due = PaymentDue.objects.get(pk=self.payment_due_id)
            if due.cancelled_at or self.type != due.direction:
                raise ValidationError({'type': _('Transaction direction must match the payment due.')})
            if self.status == self.Status.PLANNED and self.payment_received_date != due.due_date:
                raise ValidationError({'payment_received_date': _('A planned transaction date must match its payment due date.')})

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields')
        if self.entity_id and (update_fields is None or {'entity', 'entity_id'}.intersection(update_fields)):
            from resources.models import Entity

            if not Entity.objects.filter(pk=self.entity_id, entity_type=Entity.Type.FINANCIAL_ASSET).exists():
                raise ValidationError({'entity': _('Select a financial asset.')})
        if self.payment_due_id and (update_fields is None or {'type', 'status', 'payment_due', 'payment_due_id', 'payment_received_date'}.intersection(update_fields)):
            due = PaymentDue.objects.get(pk=self.payment_due_id)
            if due and (due.cancelled_at or self.type != due.direction):
                raise ValidationError({'type': _('Transaction direction must match the payment due.')})
            if self.status == self.Status.PLANNED and self.payment_received_date != due.due_date:
                raise ValidationError({'payment_received_date': _('A planned transaction date must match its payment due date.')})
        return super().save(*args, **kwargs)

    def __str__(self):
        partner = self.partner or (self.payment_due.name if self.payment_due_id else _('Transaction'))
        return f"{self.payment_received_date} - {partner} {self.type} {self.amount} {self.entity}"
