from datetime import datetime

from django.contrib.auth.models import User
from django.db import models, transaction
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


class Asset(models.Model):
    code = models.CharField(max_length=10, unique=True, verbose_name=_("Code"))
    name = models.CharField(max_length=100, verbose_name=_("Name"))
    symbol = models.CharField(max_length=10, verbose_name=_("Symbol"))
    decimal_places = models.PositiveSmallIntegerField(default=2, verbose_name=_("Decimal places"))
    is_currency = models.BooleanField(default=True, verbose_name=_("Is currency"))
    is_default = models.BooleanField(default=False, verbose_name=_("Default asset"), help_text=_("Main asset shown on the dashboard. Only one asset can be marked as default at a time — selecting a new one automatically unmarks the previous."))

    def __str__(self):
        return f"{self.code} ({self.symbol})"

    def save(self, *args, **kwargs):
        # Auto-unset: ustawienie is_default=True na tym instance odznacza poprzedniego defaulta.
        # Wykluczamy self.pk, żeby nie odznaczyć samego siebie przy ponownym zapisie.
        #
        # Atomic: unset poprzedniego defaulta + zapis tego instance muszą być jedną transakcją.
        # Bez tego, gdy super().save() rzuci PO update(), zostajemy z ZERO defaultów (poprzedni
        # odznaczony, nowy niezapisany) bez rollbacku.
        #
        # Ograniczenia tej ścieżki (świadome trade-offy):
        #  - QuerySet.update() / bulk_update() / bulk_create() omijają save() — można w ten sposób
        #    obejść auto-unset i wymusić wiele defaultów. Bezpiecznikiem jest UniqueConstraint
        #    w Meta poniżej (rzuci IntegrityError zamiast pozwolić na cichy bug).
        #  - Race condition (dwóch userów zapisuje default jednocześnie) jest teoretycznie możliwy,
        #    ale w praktyce nieosiągalny (admin assetów = jeden user, sporadyczne zmiany). Constraint
        #    również go łapie.
        with transaction.atomic():
            if self.is_default:
                Asset.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
            super().save(*args, **kwargs)

    def validate_constraints(self, exclude=None):
        # Pomijamy walidację constraintów dotyczących is_default na poziomie formularza.
        # Powód: save() poniżej i tak zaspokoi 'unique_default_asset' przez auto-unset
        # poprzedniego defaulta — ale validate_constraints() biegnie PRZED save(), więc bez
        # tego override formularz promujący istniejący asset do default zawsze padałby z
        # "Ograniczenie naruszone". Constraint nadal chroni przed bulk-bypass (QuerySet.update,
        # bulk_create) na poziomie bazy — IntegrityError tam dalej leci.
        # Uwaga: 'exclude' w Django to zbiór NAZW PÓL (nie nazw constrainów).
        #
        # TODO: to wyklucza is_default GLOBALNIE — każdy PRZYSZŁY constraint dotykający
        # is_default też zostanie po cichu pominięty w walidacji formularza i wyjdzie dopiero
        # jako IntegrityError na zapisie. Przy dodawaniu kolejnego constraintu na to pole
        # zawęź exclude do konkretnej nazwy constraintu zamiast całego pola.
        exclude = set(exclude or [])
        exclude.add('is_default')
        super().validate_constraints(exclude=exclude)

    @classmethod
    def get_default(cls):
        """
        Zwraca asset oznaczony jako domyślny (is_default=True).
        Konsumenci: pulpit (karta finansów + badge), /transaction/ (default first w pasku sald),
        /report/ (default first w pivot kolumn) — wszystko w trakcie wdrażania w ramach
        multi-asset fix (kroki 3-5).

        Fallback: pierwszy dodany (najmniejsze pk) — założenie, że user dodaje
        najważniejszą walutę jako pierwszą. Zwraca None tylko gdy baza assetów jest pusta.
        """
        return (
            cls.objects.filter(is_default=True).first()
            or cls.objects.order_by('pk').first()
        )

    class Meta:
        ordering = ['code']
        constraints = [
            # Defense-in-depth dla auto-unset z save(). Łapie bypass (QuerySet.update,
            # bulk_create) oraz teoretyczne race conditions. Partial unique index — tylko
            # wiersze z is_default=True muszą być unique, False mogą się powtarzać.
            models.UniqueConstraint(fields=['is_default'], condition=Q(is_default=True), name='unique_default_asset'),
        ]


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
    notes = models.TextField(null=True, blank=True, verbose_name=_("Notes"))

    def __str__(self):
        return self.name


class Transaction(models.Model):
    INCOMING = 'I'
    OUTGOING = 'O'
    TYPES = [
        (INCOMING, _('Incoming')),
        (OUTGOING, _('Outgoing')),
    ]
    type = models.CharField(max_length=1, choices=TYPES, default=INCOMING, verbose_name=_("Type"))

    created_date = models.DateField(auto_now_add=True, verbose_name=_("Created"))
    payment_received_date = models.DateField(null=True, blank=True, default=datetime.now, editable=True, verbose_name=_("Payment received date"))

    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, blank=False, verbose_name=_("Asset"))
    category = models.ForeignKey(Category, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_("Category"))
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, null=True, blank=False, verbose_name=_("Partner"))
    amount = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=False, verbose_name=_("Amount"))
    note = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("Note"))
    author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("Author"), related_name='transactions')

    def __str__(self):
        return f"{self.payment_received_date} - {self.partner} {self.type} {self.amount} {self.asset}"
