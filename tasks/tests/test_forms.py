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

    def test_free_text_cost_estimate_is_accepted(self):
        value = "Approximately 120 PLN; materials donated"
        form = TaskForm(data=task_form_data(cost_estimate=value))
        self.assertTrue(form.is_valid())
        self.assertEqual(form.save().cost_estimate, value)

    def test_cost_estimate_is_required(self):
        form = TaskForm(data=task_form_data(cost_estimate=""))
        self.assertFalse(form.is_valid())
        self.assertIn("cost_estimate", form.errors)

    def test_people_required_must_be_positive(self):
        form = TaskForm(data=task_form_data(required_people="0"))
        self.assertFalse(form.is_valid())
        self.assertIn("required_people", form.errors)

    def test_people_required_must_fit_model_field(self):
        form = TaskForm(data=task_form_data(required_people="32768"))
        self.assertFalse(form.is_valid())
        self.assertIn("required_people", form.errors)

    def test_people_required_is_mandatory(self):
        form = TaskForm(data=task_form_data(required_people=""))
        self.assertFalse(form.is_valid())
        self.assertIn("required_people", form.errors)

    def test_new_task_defaults_required_people_to_one(self):
        form = TaskForm()
        self.assertEqual(form["required_people"].value(), 1)

    def test_legacy_empty_people_count_stays_empty_but_is_required_on_edit(self):
        task = Task.objects.create(title="Legacy task", description="Old task", required_people=None)
        form = TaskForm(instance=task)
        self.assertIsNone(form["required_people"].value())

        form = TaskForm(data=task_form_data(required_people=""), instance=task)
        self.assertFalse(form.is_valid())
        self.assertIn("required_people", form.errors)

    def test_external_approval_requires_yes_or_no(self):
        data = task_form_data()
        data.pop("requires_external_approval")
        form = TaskForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("requires_external_approval", form.errors)

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
