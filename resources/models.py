from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

LEGACY_PHYSICAL_ASSET_SOURCE = 'bookkeeping.PhysicalAsset'
LEGACY_RESOURCE_LISTING_SOURCE = 'bookkeeping.ResourceListing'
LEGACY_FINANCIAL_ASSET_SOURCE = 'bookkeeping.Asset'


class Entity(models.Model):
    class Type(models.TextChoices):
        FINANCIAL_ASSET = 'financial_asset', _('Asset')
        PHYSICAL_ASSET = 'physical_asset', _('Physical asset')
        RESOURCE = 'resource', _('Resource')

    class ResourceKind(models.TextChoices):
        GIVE = 'give', _('Give away')
        BORROW = 'borrow', _('Lend')
        SALE = 'sale', _('For sale')
        NEED = 'need', _('I need')

    class AssignmentScope(models.TextChoices):
        UNASSIGNED = 'unassigned', _('Unassigned')
        MEMBER = 'member', _('Assigned to a member')
        COMMUNITY = 'community', _('Shared community ownership')

    entity_type = models.CharField(max_length=20, choices=Type.choices, verbose_name=_('Type'))
    name = models.CharField(max_length=200, verbose_name=_('Name'))
    description = models.TextField(max_length=1866, blank=True, default='', verbose_name=_('Description'))
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='authored_entities', verbose_name=_('Author'))
    is_community_owned = models.BooleanField(default=False, verbose_name=_('Owned by the community'))
    assigned_member = models.ForeignKey('obywatele.Uzytkownik', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_entities', verbose_name=_('Assigned member'))

    resource_kind = models.CharField(max_length=10, choices=ResourceKind.choices, blank=True, default='', verbose_name=_('Resource type'))
    is_closed = models.BooleanField(default=False, verbose_name=_('Archive'))

    code = models.CharField(max_length=10, blank=True, default='', verbose_name=_('Code'))
    symbol = models.CharField(max_length=10, blank=True, default='', verbose_name=_('Symbol'))
    decimal_places = models.PositiveSmallIntegerField(default=2, verbose_name=_('Decimal places'))
    is_currency = models.BooleanField(default=False, verbose_name=_('Is currency'))
    is_default = models.BooleanField(default=False, verbose_name=_('Default asset'))

    country = models.ForeignKey('obywatele.Country', on_delete=models.PROTECT, null=True, blank=True, related_name='resource_entities', verbose_name=_('Country'))
    city = models.CharField(max_length=100, blank=True, default='', verbose_name=_('City'))
    street = models.CharField(max_length=150, blank=True, default='', verbose_name=_('Street'))
    house_number = models.CharField(max_length=32, blank=True, default='', verbose_name=_('House number'))
    apartment_number = models.CharField(max_length=32, blank=True, default='', verbose_name=_('Apartment number'))

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Updated at'))

    class Meta:
        ordering = ('entity_type', 'name', 'pk')
        constraints = [
            models.CheckConstraint(condition=Q(entity_type__in=('financial_asset', 'physical_asset', 'resource')), name='entity_known_type'),
            models.CheckConstraint(condition=(Q(assigned_member__isnull=True) | Q(is_community_owned=False)), name='entity_one_assignee'),
            models.CheckConstraint(condition=(~Q(entity_type='financial_asset') | (Q(assigned_member__isnull=True) & Q(is_community_owned=False))), name='entity_financial_unassigned'),
            models.CheckConstraint(condition=(~Q(entity_type='financial_asset') | (~Q(code='') & ~Q(symbol=''))), name='entity_financial_fields'),
            models.CheckConstraint(condition=(~Q(entity_type='physical_asset') | (Q(country__isnull=False) & ~Q(city=''))), name='entity_physical_location'),
            models.CheckConstraint(condition=(~Q(entity_type='resource') | Q(resource_kind__in=('give', 'borrow', 'sale', 'need'))), name='entity_resource_kind'),
            models.CheckConstraint(condition=(Q(entity_type='resource') | Q(resource_kind='')), name='entity_nonresource_kind_empty'),
            models.CheckConstraint(condition=(Q(entity_type='resource') | Q(is_closed=False)), name='entity_nonresource_open'),
            models.CheckConstraint(condition=(Q(entity_type='financial_asset') | Q(is_default=False)), name='entity_only_financial_default'),
            models.CheckConstraint(condition=(Q(entity_type='financial_asset') | (Q(code='') & Q(symbol='') & Q(is_currency=False))), name='entity_nonfinancial_fields'),
            models.CheckConstraint(
                condition=(~Q(entity_type='financial_asset') | (Q(country__isnull=True) & Q(city='') & Q(street='') & Q(house_number='') & Q(apartment_number=''))), name='entity_financial_no_location'
            ),
            models.UniqueConstraint(fields=('code',), condition=Q(entity_type='financial_asset', code__gt=''), name='entity_financial_code_unique'),
            models.UniqueConstraint(fields=('is_default',), condition=Q(entity_type='financial_asset', is_default=True), name='entity_default_unique'),
            models.UniqueConstraint(
                Lower('name'), 'assigned_member', 'resource_kind', condition=Q(entity_type='resource', is_community_owned=False, assigned_member__isnull=False), name='entity_res_member_kind_uq'
            ),
            models.UniqueConstraint(Lower('name'), 'resource_kind', condition=Q(entity_type='resource', is_community_owned=True), name='entity_res_community_kind_uq'),
        ]

    def clean(self):
        super().clean()
        errors = {}

        if self.assigned_member_id and self.is_community_owned:
            errors['assigned_member'] = _('An entity cannot be assigned to a member and the community at the same time.')
        elif self.assigned_member_id:
            assigned_user = self.assigned_member.uid
            if assigned_user is None or not assigned_user.is_active:
                errors['assigned_member'] = _('Select an active member.')

        if self.entity_type == self.Type.FINANCIAL_ASSET:
            if not self.code:
                errors['code'] = _('Enter a code for the financial asset.')
            if not self.symbol:
                errors['symbol'] = _('Enter a symbol for the financial asset.')
            if self.assigned_member_id or self.is_community_owned:
                errors['assignment_scope'] = _('Financial assets cannot be assigned to a member or the community.')
            if self.country_id or self.city or self.street or self.house_number or self.apartment_number:
                errors['country'] = _('Financial assets cannot have a physical location.')
        elif self.entity_type == self.Type.PHYSICAL_ASSET:
            if not self.country_id:
                errors['country'] = _('Select a country for the physical asset.')
            if not self.city.strip():
                errors['city'] = _('Enter a city for the physical asset.')
        elif self.entity_type == self.Type.RESOURCE and self.resource_kind not in self.ResourceKind.values:
            errors['resource_kind'] = _('Select a resource type.')

        if self.is_default and self.entity_type != self.Type.FINANCIAL_ASSET:
            errors['is_default'] = _('Only financial assets can be the default asset.')

        if self.entity_type != self.Type.FINANCIAL_ASSET:
            if not self.author_id:
                errors['author'] = _('Select the author of this entity.')
            if not (self.assigned_member_id or self.is_community_owned):
                errors['assignment_scope'] = _('Assign this entity to a member or the community.')

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.entity_type == self.Type.FINANCIAL_ASSET and self.is_default:
            with transaction.atomic():
                Entity.objects.filter(entity_type=self.Type.FINANCIAL_ASSET, is_default=True).exclude(pk=self.pk).update(is_default=False)
                return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)

    def validate_constraints(self, exclude=None):
        # A save promoting a financial unit first clears the previous default.
        exclude = set(exclude or [])
        if self.entity_type == self.Type.FINANCIAL_ASSET and self.is_default:
            exclude.add('is_default')
        super().validate_constraints(exclude=exclude)

    @classmethod
    def get_default_financial_asset(cls):
        financial_assets = cls.objects.filter(entity_type=cls.Type.FINANCIAL_ASSET)
        return financial_assets.filter(is_default=True).first() or financial_assets.order_by('pk').first()

    @property
    def assignment_scope(self):
        if self.assigned_member_id:
            return self.AssignmentScope.MEMBER
        if self.is_community_owned:
            return self.AssignmentScope.COMMUNITY
        return self.AssignmentScope.UNASSIGNED

    def __str__(self):
        if self.entity_type == self.Type.FINANCIAL_ASSET:
            return f'{self.code} ({self.symbol})'
        return self.name


class LegacyEntityReference(models.Model):
    entity = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name='legacy_references')
    source_model = models.CharField(max_length=100)
    source_pk = models.PositiveBigIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=('source_model', 'source_pk'), name='entity_legacy_source_unique')]

    def __str__(self):
        return f'{self.source_model}#{self.source_pk} -> {self.entity_id}'
