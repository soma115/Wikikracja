from captcha.fields import CaptchaField
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import Room


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        # fields = ('title', 'allowed',)
        fields = ('title',)

    def clean_title(self):
        title = self.cleaned_data.get('title')
        if self.instance and self.instance.pk and getattr(self.instance, 'is_inbox', False):
            raise ValidationError(_("The Inbox room cannot be renamed."), code='inbox_rename_forbidden')
        if title:
            title_cf = title.casefold()
            qs = Room.objects.values_list('title', 'pk')
            existing = next((pk for t, pk in qs if t.casefold() == title_cf and (not self.instance or not self.instance.pk or pk != self.instance.pk)), None)
            if existing is not None:
                raise ValidationError("Pokój o tej nazwie już istnieje.", code='duplicate_title')
        return title


class GuestMessageForm(forms.Form):
    guest_email = forms.EmailField(label=_('Email'), required=True, max_length=254)
    guest_name = forms.CharField(label=_('Name and surname'), required=True, max_length=255)
    message = forms.CharField(label=_('Message'), required=True, widget=forms.Textarea, max_length=settings.MESSAGE_MAX_LENGTH)
    captcha = CaptchaField(label='')
