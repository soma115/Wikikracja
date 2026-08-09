import secrets

from django.contrib.auth.models import User


def make_user(username, email=None):
    """Helper to create an active user with a random password for testing."""
    password = secrets.token_urlsafe(16)
    user = User.objects.create_user(username=username, email=email or f"{username}@example.com", password=password, is_active=True)
    user._plain_password = password
    return user
