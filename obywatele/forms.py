import logging
import secrets
import string

from allauth.account.forms import SignupForm
from captcha.fields import CaptchaField, CaptchaTextInput
from django import forms
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from obywatele.models import Region, Uzytkownik
from zzz.signals import citizen_proposed

log = logging.getLogger(__name__)


class UserForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, label=_('First name'), required=True)
    last_name = forms.CharField(max_length=150, label=_('Last name'), required=True)
    email = forms.EmailField(label=_('Email'), required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')

    def __init__(self, *args, **kwargs):
        super(UserForm, self).__init__(*args, **kwargs)
        self.fields['first_name'].error_messages['required'] = _('First name is required.')
        self.fields['last_name'].error_messages['required'] = _('Last name is required.')
        self.fields['email'].error_messages['required'] = _('Email is required.')


class UsernameChangeForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('username',)

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super(UsernameChangeForm, self).__init__(*args, **kwargs)

    def save(self, commit=True):
        username = self.cleaned_data["username"]
        self.user.username = username
        if commit:
            self.user.save()
        return self.user


class EmailChangeForm(forms.Form):
    """
    A form that lets a user change set their email while checking for a change in the
    e-mail.
    """

    error_messages = {
        'email_mismatch': _("The two email addresses fields didn't match."),
        'not_changed': _("The email address is the same as the one already defined."),
        'already_exists': _("An account with this email address already exists."),
    }

    new_email1 = forms.EmailField(label=_("New email address"), widget=forms.EmailInput)

    new_email2 = forms.EmailField(label=_("New email address confirmation"), widget=forms.EmailInput)

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super(EmailChangeForm, self).__init__(*args, **kwargs)

    def clean_new_email1(self):
        old_email = self.user.email
        new_email1 = self.cleaned_data.get('new_email1')
        if new_email1 and old_email:
            if new_email1 == old_email:
                raise forms.ValidationError(self.error_messages['not_changed'], code='not_changed')
        if new_email1 and User.objects.filter(email__iexact=new_email1).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError(self.error_messages['already_exists'], code='already_exists')
        return new_email1

    def clean_new_email2(self):
        new_email1 = self.cleaned_data.get('new_email1')
        new_email2 = self.cleaned_data.get('new_email2')
        if new_email1 and new_email2:
            if new_email1 != new_email2:
                raise forms.ValidationError(self.error_messages['email_mismatch'], code='email_mismatch')
        return new_email2

    def save(self, commit=True):
        email = self.cleaned_data["new_email1"]
        self.user.email = email
        if commit:
            self.user.save()
        return self.user


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, label=_('First name'), required=True)
    last_name = forms.CharField(max_length=150, label=_('Last name'), required=True)

    class Meta:
        model = Uzytkownik
        fields = ('phone', 'responsibilities', 'city', 'voivodeship', 'skills_knowledge_hobby', 'to_give_away', 'to_borrow', 'for_sale', 'i_need', 'want_to_learn', 'business', 'job', 'why')

    def __init__(self, *args, **kwargs):
        super(ProfileForm, self).__init__(*args, **kwargs)
        self.fields['phone'].label = _('Communicator or Phone')
        self.fields['phone'].required = True
        self.fields['city'].required = True
        self.fields['job'].required = True

        # Filter voivodeship to show regions from Poland (can be extended for other countries)
        self.fields['voivodeship'].queryset = Region.objects.filter(country__code='PL').order_by('name')
        self.fields['voivodeship'].label = _('Voivodeship')
        self.fields['voivodeship'].required = False

        self.fields['first_name'].error_messages['required'] = _('First name is required.')
        self.fields['last_name'].error_messages['required'] = _('Last name is required.')
        self.fields['phone'].error_messages['required'] = _('Phone number is required.')
        self.fields['city'].error_messages['required'] = _('City / Commune is required.')
        self.fields['job'].error_messages['required'] = _('Job is required.')


class AvatarForm(forms.ModelForm):
    class Meta:
        model = Uzytkownik
        fields = ('avatar',)

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Delete old avatar file if being replaced
        if commit:
            try:
                old = Uzytkownik.objects.get(pk=instance.pk)
                if old.avatar and old.avatar != instance.avatar:
                    old.avatar.delete(save=False)
            except Uzytkownik.DoesNotExist:
                pass
            instance.save()
        return instance


class OnboardingDetailsForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, label=_('First name'), required=True)
    last_name = forms.CharField(max_length=150, label=_('Last name'), required=True)

    class Meta:
        model = Uzytkownik
        fields = ('why', 'phone', 'city', 'voivodeship', 'job', 'skills_knowledge_hobby', 'business')

    def __init__(self, *args, **kwargs):
        super(OnboardingDetailsForm, self).__init__(*args, **kwargs)
        self.fields['phone'].label = _('Communicator or Phone')
        self.fields['phone'].required = True
        self.fields['city'].required = True
        self.fields['job'].required = True

        # Filter voivodeship to show regions from Poland (can be extended for other countries)
        self.fields['voivodeship'].queryset = Region.objects.filter(country__code='PL').order_by('name')
        self.fields['voivodeship'].label = _('Voivodeship')
        self.fields['voivodeship'].required = False

        self.fields['first_name'].error_messages['required'] = _('First name is required.')
        self.fields['last_name'].error_messages['required'] = _('Last name is required.')
        self.fields['phone'].error_messages['required'] = _('Phone number is required.')
        self.fields['city'].error_messages['required'] = _('City / Commune is required.')
        self.fields['job'].error_messages['required'] = _('Job is required.')


class CustomSignupForm(SignupForm):
    """
    Custom signup form for Wikikracja onboarding process.

    KEY DESIGN NOTES:
    - Only email and captcha are shown to user (simplified signup)
    - Password is auto-generated (12 chars, alphanumeric)
    - User never sees password - login via email only
    - Email confirmation is manually triggered (allauth auto-send disabled)
    - After signup: user redirected to onboarding form
    - After email confirmation: second email with onboarding link sent
    """

    email = forms.CharField(max_length=100, label='Email', required=True)
    captcha = CaptchaField(widget=CaptchaTextInput(attrs={'class': 'form-control'}))

    def __init__(self, *args, **kwargs):
        super(CustomSignupForm, self).__init__(*args, **kwargs)
        # CRITICAL: allauth requires password1 field, but we hide it and auto-generate
        # This prevents "field required" validation errors while keeping UI simple
        self.fields['password1'].widget = forms.HiddenInput()
        self.fields['password1'].required = False

        password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
        self.fields['password1'].initial = password

    def clean_email(self):
        email = self.cleaned_data['email']
        existing_user = User.objects.filter(email__iexact=email).first()

        if existing_user:
            if not existing_user.is_active:
                raise forms.ValidationError(_('Your candidacy is still in the queue. Please wait for verification.'))
            else:
                raise forms.ValidationError(_('An account with this email address already exists.'))

        return email

    def clean_password1(self):
        """
        Auto-generate password for hidden password1 field.

        DESIGN NOTE: allauth requires password validation but we want email-only signup.
        This method satisfies allauth's requirements while keeping UI simple.
        Password is secure (12 chars, alphanumeric) but user never sees it.
        """
        password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
        return password

    def clean(self):
        return super().clean()

    def save(self, request: HttpRequest):
        user = super(CustomSignupForm, self).save(request)
        user.email = self.cleaned_data['email']
        # Pozwolmy allauth zarzadac haslem - nie ustawiamy set_unusable_password()

        try:
            user.save()
        except IntegrityError:
            # Handle unique constraint violation
            # Delete this user if a duplicate with the same email already exists
            existing = User.objects.filter(email__iexact=user.email).exclude(id=user.id).first()
            if existing:
                user.delete()
                user = existing
            else:
                raise

        profile = user.uzytkownik
        profile.onboarding_status = Uzytkownik.OnboardingStatus.EMAIL_ENTERED
        profile.save()

        # CRITICAL: Manual email confirmation sending
        # DESIGN NOTE: allauth auto-send is disabled due to custom form structure
        # We must manually trigger email confirmation with proper HMAC signing
        try:
            from allauth.account.adapter import get_adapter
            from allauth.account.models import EmailAddress, EmailConfirmationHMAC

            # Ensure EmailAddress exists (allauth requirement for email confirmation)
            email_address, created = EmailAddress.objects.get_or_create(user=user, email=user.email, defaults={'verified': False, 'primary': True})

            if created or not email_address.verified:
                # IMPORTANT: Use EmailConfirmationHMAC (not EmailConfirmation)
                # HMAC provides secure signed links that don't expire quickly
                # Old EmailConfirmation.create() was causing "link expired" errors
                confirmation = EmailConfirmationHMAC.create(email_address)
                adapter = get_adapter()
                adapter.send_confirmation_mail(request, confirmation, signup=True)

        except Exception as e:
            log.error(f'Failed to send confirmation email: {e}', exc_info=True)

        citizen_proposed.send(sender='obywatele.forms.CustomSignupForm', candidate=user, proposed_by=None)
        return user
