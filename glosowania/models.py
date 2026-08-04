import re

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_comma_separated_integer_list
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from chat.models import ChatRoomModel

User = get_user_model()


def does_it_exist(value):
    x = re.split(r'\W+', value.strip(' ,'))
    for i in x:
        try:
            _existing = Decyzja.objects.get(pk=int(i))  # all existing for now
        except Exception as _e:
            raise ValidationError(_("Enter only existing bill numbers here"))  # noqa: B904
    return True


class Decyzja(ChatRoomModel, models.Model):
    class Status(models.IntegerChoices):
        PROPOSITION = 1, _('Proposition')
        DISCUSSION = 2, _('Discussion')
        REFERENDUM = 3, _('Referendum')
        REJECTED = 4, _('Rejected')
        APPROVED = 5, _('Approved')

    author = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    title = models.TextField(max_length=200, null=True, verbose_name=_('Title'), help_text=_('Enter short title describing new law.'))
    tresc = models.TextField(max_length=3000, null=True, verbose_name=_('Law text'), help_text=_('Enter the exact wording of the law as it is to be applied.'))
    kara = models.TextField(max_length=500, null=True, blank=True, verbose_name=_('Penalty for non-compliance (optional)'), help_text=_('Fill in only if the rule execution depends on human action and is not automatic. What is the penalty for non-compliance? This can be, for example: "Banishment for 3 months", "Banishment forever", etc.'))
    uzasadnienie = models.TextField(max_length=4000, null=True, verbose_name=_('Reasoning'), help_text=_('Why do we need this law? What events or thoughts inspired this bill? What are the expected results?'))
    args_for = models.TextField(
        # TODO: This field should be filled out by anyone - like comments or chat:
        max_length=1500,
        null=True,
        verbose_name=_('Positive Aspects of the Idea'),
        help_text=_('Enter the benefits for the group, environment, economy, etc. resulting from the introduction of the idea.')
    )
    args_against = models.TextField(
        # TODO: This field should be filled out by anyone - like comments or chat:
        max_length=1500,
        null=True,
        verbose_name=_('Negative Aspects of the Idea'),
        help_text=_('Enter the potential threat associated with the proposal.')
    )
    znosi = models.CharField(max_length=50, null=True, blank=True, verbose_name=_('Abolishes the rules'), help_text=_('If the proposed law supersedes other bills, enter their comma separated numbers here.'), validators=[validate_comma_separated_integer_list, does_it_exist])
    path = models.CharField(max_length=1000, null=True, verbose_name=_('The path this bill took.'))
    ile_osob_podpisalo = models.SmallIntegerField(editable=False, default=0)
    data_powstania = models.DateField(auto_now_add=True, editable=False, null=True)
    data_ostatniej_modyfikacji = models.DateTimeField(auto_now=True, editable=False, null=True)
    data_zebrania_podpisow = models.DateField(editable=False, null=True)
    data_referendum_start = models.DateField(editable=False, null=True)
    data_referendum_stop = models.DateField(editable=False, null=True)
    za = models.SmallIntegerField(default=0, editable=False)
    przeciw = models.SmallIntegerField(default=0, editable=False)
    status = models.SmallIntegerField(choices=Status.choices, default=Status.PROPOSITION, editable=False)
    referendum_restart_count = models.SmallIntegerField(
        default=0,
        editable=False,
        verbose_name=_('Referendum restart count'),
        help_text=_('How many times voting had to restart from scratch because the vote buffer was lost (e.g. Redis restart) before it closed.'),
    )
    proposed_parameters = models.JSONField(
        null=True,
        blank=True,
        editable=False,
        verbose_name=_('Proposed system parameters'),
        help_text=_('If set, this referendum changes system parameters. Applied when approved.'),
    )
    proposed_brand_mark = models.ImageField(
        upload_to='site_branding/proposed/',
        null=True,
        blank=True,
        editable=False,
        verbose_name=_('Proposed logo'),
        help_text=_('If set, this referendum changes the site logo. Applied when approved.'),
    )
    def __str__(self):
        return '%s: %s on %s' % (self.pk, self.tresc, self.status)

    objects = models.Manager()

    def get_chat_room_title(self):
        return f"{self.pk}. {self.title}"[:90]

    def get_chat_room(self):
        return self.chat_room

    def get_chat_room_url(self):
        room = self.get_chat_room()
        if room:
            return f"{reverse('chat:chat')}#room_id={room.id}"
        return None

    @property
    def chat_room_url(self):
        return self.get_chat_room_url()

    def get_chat_room_pulse_class(self, user):
        """Return CSS class for chat room pulse indicator if there are unseen messages"""
        chat_room = self.chat_room
        if (chat_room and chat_room.messages.exists() and not chat_room.seen_by.filter(id=user.id).exists()):
            return "chat-room-pulse"
        return ""

    @property
    def is_author_signed(self):
        if not self.author_id:
            return False
        return ZebranePodpisy.objects.filter(projekt=self, podpis_uzytkownika_id=self.author_id).exists()

    @property
    def display_title(self):
        if self.is_author_signed:
            return self.title
        return f"{self.title} [{_('draft')}]"

    @property
    def voting_has_ended(self):
        """True once the decision has been rejected or approved (arguments
        can no longer be added/edited/deleted)."""
        return self.status in (self.Status.REJECTED, self.Status.APPROVED)


class Argument(models.Model):
    ARGUMENT_TYPE_CHOICES = [
        ('FOR', _('Positive')),
        ('AGAINST', _('Negative')),
    ]

    decyzja = models.ForeignKey(Decyzja, on_delete=models.CASCADE, related_name='arguments', verbose_name=_('Decision'))
    author = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_('Author'))
    argument_type = models.CharField(max_length=10, choices=ARGUMENT_TYPE_CHOICES, verbose_name=_('Argument Type'), help_text=_('Is this a positive or negative argument?'))
    content = models.TextField(max_length=1000, verbose_name=_('Argument Content'), help_text=_('Enter your argument. You can include links.'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created At'))
    modified_at = models.DateTimeField(auto_now=True, verbose_name=_('Last Modified'))

    class Meta:
        ordering = ['created_at']
        verbose_name = _('Argument')
        verbose_name_plural = _('Arguments')

    def __str__(self):
        return f"{self.get_argument_type_display()}: {self.content[:50]}..."


class DecyzjaWersja(models.Model):
    decyzja = models.ForeignKey(Decyzja, on_delete=models.CASCADE, related_name='wersje', verbose_name=_('Decision'))
    modified_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_('Modified by'))
    modified_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Modified at'))
    version_number = models.PositiveSmallIntegerField(verbose_name=_('Version'))
    title = models.TextField(max_length=200, null=True)
    tresc = models.TextField(max_length=3000, null=True)
    kara = models.TextField(max_length=500, null=True, blank=True)
    uzasadnienie = models.TextField(max_length=4000, null=True)
    znosi = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        ordering = ['version_number']
        verbose_name = _('Decision version')
        verbose_name_plural = _('Decision versions')

    def __str__(self):
        return f"v{self.version_number} – {self.decyzja_id}"


class ZebranePodpisy(models.Model):
    '''Lista podpisów pod wnioskiem o referendum'''
    projekt = models.ForeignKey(Decyzja, on_delete=models.SET_NULL, null=True)

    # Lets note who signed proposal:
    podpis_uzytkownika = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        unique_together = ('projekt', 'podpis_uzytkownika')


class KtoJuzGlosowal(models.Model):
    projekt = models.ForeignKey(Decyzja, on_delete=models.CASCADE)
    ktory_uzytkownik_juz_zaglosowal = models.ForeignKey(User, on_delete=models.CASCADE)

    # odnotowujemy tylko fakt głosowania

    class Meta:
        unique_together = ('projekt', 'ktory_uzytkownik_juz_zaglosowal')


class VoteCode(models.Model):
    '''
    - Jednorazowy kod
    - Tak/Nie
    '''
    project = models.ForeignKey(Decyzja, on_delete=models.CASCADE)
    code = models.CharField(editable=False, null=True, max_length=20)
    vote = models.BooleanField(editable=False, null=True)
