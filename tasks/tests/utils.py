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


def make_task(title="Zadanie", created_by=None, assigned_to=None, status=Task.Status.ACTIVE, team_mode=False, phase=Task.Phase.PROPOSAL, required_people=None):
    return Task.objects.create(title=title, description="Opis zadania", status=status, created_by=created_by, assigned_to=assigned_to, team_mode=team_mode, phase=phase, required_people=required_people)


def task_form_data(**overrides):
    data = {
        "title": "Zadanie",
        "description": "Opis zadania",
        "cost_estimate": "0",
        "required_people": "1",
        "requires_external_approval": "false",
        "success_criteria": "Osiągnięto cel.",
        "due_date": "",
        "category": "",
    }
    data.update(overrides)
    return data
