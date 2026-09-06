from __future__ import unicode_literals

from datetime import datetime

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.timezone import make_aware
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class Country(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name=_('Country name'))
    code = models.CharField(max_length=2, unique=True, verbose_name=_('ISO code'))

    class Meta:
        verbose_name = _('Country')
        verbose_name_plural = _('Countries')
        ordering = ('name',)

    def __str__(self):
        return self.name


class Region(models.Model):
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='regions', verbose_name=_('Country'))
    name = models.CharField(max_length=100, verbose_name=_('Region name'))

    class Meta:
        verbose_name = _('Region')
        verbose_name_plural = _('Regions')
        ordering = ('country', 'name')
        unique_together = ('country', 'name')

    def __str__(self):
        return f"{self.name} ({self.country.code})"


class Uzytkownik(models.Model):
    class OnboardingStatus(models.TextChoices):
        EMAIL_ENTERED = 'email_entered', _('Email entered')
        EMAIL_CONFIRMED = 'email_confirmed', _('Email confirmed')
        FORM_COMPLETED = 'form_completed', _('Form completed')

    class EmailFrequency(models.TextChoices):
        DAILY = 'daily', _('Daily')
        WEEKLY = 'weekly', _('Weekly')
        MONTHLY = 'monthly', _('Monthly')
        NEVER = 'never', _('Never')

    uid = models.OneToOneField(User, on_delete=models.CASCADE, editable=False, null=True, verbose_name=_('Username'))

    reputation = models.SmallIntegerField(null=True, default=0)
    onboarding_status = models.CharField(max_length=32, choices=OnboardingStatus.choices, default=OnboardingStatus.EMAIL_ENTERED)
    polecajacy = models.CharField(editable=False, null=True, max_length=64)
    data_przyjecia = models.DateField(null=True, editable=False)

    phone = models.CharField(null=True, blank=True, max_length=72, help_text=_('Preferred communicator or phone number'), verbose_name=_('Phone number'))
    city = models.CharField(null=True, blank=True, max_length=72, help_text=_('Where one spend most of their time'), verbose_name=_('City'))
    voivodeship = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, blank=True, related_name='citizens', verbose_name=_('Voivodeship'))
    responsibilities = models.CharField(null=True, blank=True, max_length=622, help_text=_('Activities performed in our group'), verbose_name=_('Responsibilities'))
    skills_knowledge_hobby = models.CharField(null=True, blank=True, max_length=1866, help_text=_('Skills, knowledge, and hobbies'), verbose_name=_('Skills / Knowledge / Hobby'))
    to_give_away = models.CharField(null=True, blank=True, max_length=622, help_text=_('Things you are willing to give away for free'), verbose_name=_('To give away'))
    to_borrow = models.CharField(null=True, blank=True, max_length=622, help_text=_('Stuff you can borrow to others'), verbose_name=_('To borrow'))
    for_sale = models.CharField(null=True, blank=True, max_length=622, help_text=_('Stuff you have for sale'), verbose_name=_('For sale'))
    i_need = models.CharField(null=True, blank=True, max_length=622, help_text=_('What do you need'), verbose_name=_('I need'))
    want_to_learn = models.CharField(null=True, blank=True, max_length=622, help_text=_('Things one would like to learn'), verbose_name=_('I want to learn'))
    business = models.CharField(null=True, blank=True, max_length=622, help_text=_('If running a business'), verbose_name=_('Business'))
    job = models.CharField(null=True, blank=True, max_length=622, help_text=_('Profession'), verbose_name=_('Job'))
    why = models.CharField(null=True, blank=True, max_length=662, help_text=_("In your own words please explain why do you want join our group"), verbose_name=_("Why do you want to join?"))

    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name=_('Avatar'))

    language = models.CharField(max_length=10, blank=True, default='', verbose_name=_('Language'))

    # Last broadcast time
    last_broadcast = models.DateTimeField(default=make_aware(datetime(1900, 1, 1)))

    # Email digest frequency
    email_frequency = models.CharField(max_length=10, choices=EmailFrequency.choices, default=EmailFrequency.DAILY, help_text=_('How often to receive email activity digests'), verbose_name=_('Email frequency'))
    last_email_digest_at = models.DateTimeField(default=timezone.now, verbose_name=_('Last email digest sent at'))

    # Email notification preferences (deprecated, replaced by email_frequency)
    email_notifications_obywatele = models.BooleanField(default=True, help_text=_('Receive notifications about new citizens and membership requests'), verbose_name=_('Citizenship notifications'))
    email_notifications_glosowania = models.BooleanField(default=True, help_text=_('Receive notifications about law proposals and voting'), verbose_name=_('Voting notifications'))
    email_notifications_chat = models.BooleanField(default=True, help_text=_('Receive notifications about new chat messages'), verbose_name=_('Chat notifications'))
    email_notifications_events = models.BooleanField(default=True, help_text=_('Receive notifications about events'), verbose_name=_('Event notifications'))

    # Push notification preferences
    push_notifications_obywatele = models.BooleanField(default=True, help_text=_('Receive push notifications about new citizens and membership requests'), verbose_name=_('Push citizenship notifications'))
    push_notifications_glosowania = models.BooleanField(default=True, help_text=_('Receive push notifications about law proposals and voting'), verbose_name=_('Push voting notifications'))
    push_notifications_chat = models.BooleanField(default=True, help_text=_('Receive push notifications about new chat messages'), verbose_name=_('Push chat notifications'))
    push_notifications_events = models.BooleanField(default=True, help_text=_('Receive push notifications about events'), verbose_name=_('Push event notifications'))
    push_notifications_post = models.BooleanField(default=True, help_text=_('Receive push notifications about new and updated documents'), verbose_name=_('Push document notifications'))
    push_notifications_task = models.BooleanField(default=True, help_text=_('Receive push notifications about new activities'), verbose_name=_('Push activity notifications'))
    push_notifications_survey = models.BooleanField(default=True, help_text=_('Receive push notifications about new surveys'), verbose_name=_('Push survey notifications'))

    # Per-device-type push toggles (phone = mobile/tablet, computer = desktop browsers/PWAs)
    push_phone_enabled = models.BooleanField(default=True, help_text=_('Receive push notifications on phones and tablets'), verbose_name=_('Push on phone'))
    push_computer_enabled = models.BooleanField(default=True, help_text=_('Receive push notifications on desktop computers and laptops'), verbose_name=_('Push on computer'))

    ONBOARDING_FORM_FIELDS = ('phone', 'responsibilities', 'city', 'voivodeship', 'skills_knowledge_hobby', 'to_give_away', 'to_borrow', 'for_sale', 'i_need', 'want_to_learn', 'business', 'job', 'why')

    @property
    def form_completion_percent(self) -> int:
        profile_fields = [bool(getattr(self, f)) for f in self.ONBOARDING_FORM_FIELDS]
        try:
            user_fields = [bool(self.uid.first_name), bool(self.uid.last_name)]
        except Exception:
            user_fields = [False, False]
        all_fields = profile_fields + user_fields
        filled = sum(all_fields)
        return round(filled / len(all_fields) * 100)

    class Meta:
        verbose_name = _("Citizen")
        verbose_name_plural = _("Citizens")

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse('obywatele:obywatele_szczegoly', args=[self.uid.pk])

    # https://simpleisbetterthancomplex.com/tutorial/2016/07/22/how-to-extend-django-user-model.html#onetoone
    @receiver(post_save, sender=User)
    def create_user_profile(sender, instance, created, **kwargs):
        if created:
            # no, there should be no 'self':
            Uzytkownik.objects.create(uid=instance)


class CitizenActivity(models.Model):
    """Track activities related to citizens"""

    class ActivityType(models.TextChoices):
        NEW_CANDIDATE = 'new_candidate', _('New Candidate')
        USER_ACTIVATED = 'user_activated', _('User Activated')
        USER_BLOCKED = 'user_blocked', _('User Blocked')

    uzytkownik = models.ForeignKey(Uzytkownik, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=20, choices=ActivityType.choices)
    timestamp = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [models.Index(fields=['timestamp'], name='citizen_activity_timestamp_idx'), models.Index(fields=['activity_type'], name='citizen_activity_type_idx')]

    def __str__(self):
        return f"{self.uzytkownik.uid.username}: {self.get_activity_type_display()}"


class DeletionRequest(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='deletion_request', verbose_name=_('User'))
    requested_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Requested at'))
    scheduled_for = models.DateTimeField(verbose_name=_('Scheduled for'))
    reason = models.TextField(blank=True, null=True, verbose_name=_('Reason for deletion'))

    class Meta:
        verbose_name = _('Deletion request')
        verbose_name_plural = _('Deletion requests')
        indexes = [models.Index(fields=['scheduled_for'], name='deletion_request_scheduled_idx')]

    def __str__(self):
        return f"{self.user.username} (scheduled: {self.scheduled_for.date()})"


class Rate(models.Model):
    kandydat = models.ForeignKey(Uzytkownik, on_delete=models.CASCADE, related_name='kandydat')
    obywatel = models.ForeignKey(Uzytkownik, on_delete=models.CASCADE, related_name='obywatel')
    rate = models.SmallIntegerField(null=True, default=0)

    class Meta:
        unique_together = ('kandydat', 'obywatel')
