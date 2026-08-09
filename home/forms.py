from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _


class RememberLoginForm(AuthenticationForm):
    remember_me = forms.BooleanField(required=False, label=_("Keep me signed in"), widget=forms.CheckboxInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # We authenticate with email, make the label explicit for clarity in templates.
        self.fields["username"].label = _("Email")
