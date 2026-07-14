import logging
from urllib.parse import urlencode

from allauth.account.adapter import DefaultAccountAdapter
from django.core.signing import TimestampSigner
from django.urls import reverse

log = logging.getLogger(__name__)
signer = TimestampSigner()


class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Custom adapter to handle Wikikracja onboarding flow.

    KEY DESIGN NOTES:
    - Ensures onboarding_user_id is set in session after signup
    - Handles inactive user redirects to onboarding (not /accounts/inactive/)
    - Preserves session data across allauth redirects
    - Critical for onboarding form access after signup
    """
    def save_user(self, request, user, form, commit=True):
        """
        CRITICAL: Set onboarding_user_id in session immediately after user creation.

        DESIGN NOTE: allauth may clear/modify session during signup process.
        This ensures the onboarding_user_id survives allauth redirects.
        Without this, users get "Could not find your onboarding account" error.
        """
        # Call the parent method first
        user = super().save_user(request, user, form, commit)

        # CRITICAL: Set onboarding_user_id in session immediately
        # This allows access to onboarding form after signup redirect
        if hasattr(user, 'uzytkownik'):
            request.session['onboarding_user_id'] = user.id
            request.session.modified = True

        return user

    def is_auto_signup_allowed(self, request, sociallogin):  # noqa: ARG002 - allauth API requires this signature
        """
        Disable auto signup for social accounts to ensure onboarding flow
        """
        return False

    def is_open_for_signup(self, request):
        """
        Allow signup if configured
        """
        from site_settings.params import get_param
        return get_param('group_is_public')

    def get_login_redirect_url(self, request):
        """
        CRITICAL: Redirect inactive users to onboarding (not /accounts/inactive/).

        DESIGN NOTE: Default allauth behavior sends inactive users to /accounts/inactive/
        This breaks our onboarding flow. We redirect them to onboarding form instead.
        Combined with ACCOUNT_INACTIVE_REDIRECT_URL setting, this ensures smooth flow.
        """
        if request.user.is_authenticated and not request.user.is_active:
            # IMPORTANT: Redirect inactive users to onboarding, not /accounts/inactive/
            # This prevents "Your account is inactive" dead-end
            # Preserve the original URL with token if present (e.g., from email link)
            next_url = request.GET.get('next') or request.POST.get('next')
            if next_url and 'token=' in next_url:
                return next_url
            return '/obywatele/onboarding/'

        # Preserve the original URL with token for authenticated users too
        # This handles the case where users click email links and need to login
        next_url = request.GET.get('next') or request.POST.get('next')
        if next_url and 'token=' in next_url:
            return next_url

        return super().get_login_redirect_url(request)

    def get_email_verification_redirect_url(self, email_address):
        """
        CRITICAL: After email confirmation, redirect directly to onboarding form with token.

        DESIGN NOTE: Default allauth behavior redirects to ACCOUNT_EMAIL_CONFIRMATION_*_REDIRECT_URL
        which is /obywatele/onboarding/ — but without a token and with a fresh session,
        so get_onboarding_user_from_request returns None and user sees an error.
        We generate a signed token here and embed it in the redirect URL.
        """
        user = email_address.user
        token = signer.sign(str(user.id))
        query_params = urlencode({'token': token})
        url = reverse('obywatele:onboarding_details') + f'?{query_params}'
        return url

    def add_message(self, request, level, message_template, message_context=None, *args, **kwargs):
        """
        Override to prevent allauth from adding default email confirmation message.

        DESIGN NOTE: We add our own message in the email_confirmed signal handler.
        Allauth sends this message via 'account/messages/email_confirmed.txt' template.
        """
        if message_template == 'account/messages/email_confirmed.txt':
            return
        return super().add_message(request, level, message_template, message_context, *args, **kwargs)
