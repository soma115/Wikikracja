# Third party imports
from django.test import TestCase

# Local folder imports
from tasks.forms import TaskForm, TaskStatusForm
from tasks.models import Task
from tasks.tests.utils import make_user


class TaskFormTest(TestCase):
    def test_valid_form(self):
        form = TaskForm(data={"title": "Zadanie", "description": "Opis"})
        self.assertTrue(form.is_valid())

    def test_empty_title_invalid(self):
        form = TaskForm(data={"title": "", "description": "Opis"})
        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)

    def test_title_too_long_invalid(self):
        form = TaskForm(data={"title": "A" * 201, "description": "Opis"})
        self.assertFalse(form.is_valid())

    def test_empty_description_invalid(self):
        form = TaskForm(data={"title": "Zadanie", "description": ""})
        self.assertFalse(form.is_valid())
        self.assertIn("description", form.errors)


class TaskStatusFormTest(TestCase):
    def setUp(self):
        user = make_user("statususer")
        self.task = Task.objects.create(title="T", description="D", status=Task.Status.ACTIVE, created_by=user)

    def test_completed_status_valid(self):
        form = TaskStatusForm(data={"status": Task.Status.COMPLETED}, instance=self.task)
        self.assertTrue(form.is_valid())

    def test_cancelled_status_valid(self):
        form = TaskStatusForm(data={"status": Task.Status.CANCELLED}, instance=self.task)
        self.assertTrue(form.is_valid())

    def test_active_status_invalid(self):
        form = TaskStatusForm(data={"status": Task.Status.ACTIVE}, instance=self.task)
        self.assertFalse(form.is_valid())

    def test_rejected_status_invalid(self):
        form = TaskStatusForm(data={"status": Task.Status.REJECTED}, instance=self.task)
        self.assertFalse(form.is_valid())
