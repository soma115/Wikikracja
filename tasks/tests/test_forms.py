# Third party imports
from django.test import TestCase

# Local folder imports
from tasks.forms import TaskForm, TaskStatusForm
from tasks.models import Task
from tasks.tests.utils import make_user, task_form_data


class TaskFormTest(TestCase):
    def test_valid_form(self):
        form = TaskForm(data=task_form_data())
        self.assertTrue(form.is_valid())

    def test_empty_title_invalid(self):
        form = TaskForm(data=task_form_data(title=""))
        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)

    def test_title_too_long_invalid(self):
        form = TaskForm(data=task_form_data(title="A" * 201))
        self.assertFalse(form.is_valid())

    def test_empty_description_invalid(self):
        form = TaskForm(data=task_form_data(description=""))
        self.assertFalse(form.is_valid())
        self.assertIn("description", form.errors)

    def test_positive_cost_requires_currency(self):
        form = TaskForm(data=task_form_data(estimated_cost="10", currency=""))
        self.assertFalse(form.is_valid())
        self.assertIn("currency", form.errors)

    def test_zero_cost_does_not_require_currency(self):
        form = TaskForm(data=task_form_data(estimated_cost="0", currency=""))
        self.assertTrue(form.is_valid())

    def test_people_required_must_be_positive(self):
        form = TaskForm(data=task_form_data(required_people="0"))
        self.assertFalse(form.is_valid())
        self.assertIn("required_people", form.errors)

    def test_people_required_must_fit_model_field(self):
        form = TaskForm(data=task_form_data(required_people="32768"))
        self.assertFalse(form.is_valid())
        self.assertIn("required_people", form.errors)

    def test_external_approval_requires_yes_or_no(self):
        data = task_form_data()
        data.pop("requires_external_approval")
        form = TaskForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("requires_external_approval", form.errors)

    def test_cost_is_limited_to_two_decimal_places(self):
        form = TaskForm(data=task_form_data(estimated_cost="1.234", currency="PLN"))
        self.assertFalse(form.is_valid())
        self.assertIn("estimated_cost", form.errors)

    def test_external_approval_choice_is_selected_when_editing(self):
        task = Task.objects.create(title="Zadanie", description="Opis", requires_external_approval=True)
        form = TaskForm(instance=task)
        self.assertEqual(form["requires_external_approval"].value(), "true")


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
