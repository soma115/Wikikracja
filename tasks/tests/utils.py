# Standard library imports
import secrets

# Third party imports
from django.contrib.auth import get_user_model

# Local folder imports
from tasks.models import Task

User = get_user_model()


def make_user(username):
    password = secrets.token_urlsafe(16)
    user = User.objects.create_user(username=username, password=password)
    user._plain_password = password
    return user


def make_task(title="Zadanie", created_by=None, assigned_to=None, status=Task.Status.ACTIVE):
    return Task.objects.create(title=title, description="Opis zadania", status=status, created_by=created_by, assigned_to=assigned_to)
