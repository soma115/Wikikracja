# Standard library imports
from unittest.mock import patch

# Third party imports
from django.test import TestCase

# Local folder imports
from chat.models import Room
from tasks.models import Task, TaskEvaluation, TaskVote
from tasks.tests.utils import make_task, make_user


# ---------------------------------------------------------------------------
# Task model
# ---------------------------------------------------------------------------
class TaskModelTest(TestCase):
    def setUp(self):
        self.user = make_user("creator")
        self.task = make_task(created_by=self.user)

    def test_str_returns_title(self):
        self.assertEqual(str(self.task), "Zadanie")

    def test_default_status_is_active(self):
        self.assertEqual(self.task.status, Task.Status.ACTIVE)

    def test_is_active_true_for_active_task(self):
        self.assertTrue(self.task.is_active)

    def test_is_active_false_for_completed_task(self):
        self.task.status = Task.Status.COMPLETED
        self.task.save()
        self.assertFalse(self.task.is_active)

    def test_get_chat_room_title_clips_to_90(self):
        task = make_task(title="A" * 100)
        self.assertEqual(len(task.get_chat_room_title()), 90)

    def test_get_chat_room_url_none_when_no_room(self):
        task = Task.objects.create(title="No room", description="x", status=Task.Status.ACTIVE, created_by=self.user)
        Task.objects.filter(pk=task.pk).update(chat_room=None)
        task.refresh_from_db()
        self.assertIsNone(task.get_chat_room_url())

    def test_task_creation_creates_chat_room(self):
        task = make_task(created_by=self.user)
        task.refresh_from_db()
        self.assertIsNotNone(task.chat_room)
        self.assertTrue(Room.objects.filter(title=task.get_chat_room_title()).exists())
        self.assertEqual(task.chat_room.title, task.get_chat_room_title())

    def test_team_mode_defaults_to_false(self):
        task = make_task(created_by=self.user)
        self.assertFalse(task.team_mode)

    def test_can_user_post_old_task(self):
        other = make_user("other")
        task = make_task(created_by=self.user, team_mode=False)
        self.assertTrue(task.can_user_post(other))

    def test_can_user_post_team_mode_coordinator(self):
        other = make_user("other")
        task = make_task(created_by=self.user, assigned_to=other, team_mode=True)
        self.assertTrue(task.can_user_post(other))

    def test_can_user_post_team_mode_approved_helper(self):
        helper = make_user("helper")
        task = make_task(created_by=self.user, team_mode=True)
        TaskVote.objects.create(task=task, user=helper, value=TaskVote.Value.UP)
        task.approve_helper(helper)
        self.assertTrue(task.can_user_post(helper))

    def test_can_user_post_team_mode_unapproved_helper_cannot_post(self):
        helper = make_user("helper")
        other = make_user("other")
        task = make_task(created_by=self.user, team_mode=True)
        TaskVote.objects.create(task=task, user=helper, value=TaskVote.Value.UP)
        self.assertFalse(task.can_user_post(helper))
        self.assertFalse(task.can_user_post(other))

    def test_approve_helper_requires_helper_vote(self):
        helper = make_user("helper")
        task = make_task(created_by=self.user, team_mode=True)
        with self.assertRaises(ValueError):
            task.approve_helper(helper)

    def test_remove_helper_keeps_vote(self):
        helper = make_user("helper")
        task = make_task(created_by=self.user, team_mode=True)
        TaskVote.objects.create(task=task, user=helper, value=TaskVote.Value.UP)
        task.approve_helper(helper)
        self.assertTrue(task.is_user_approved(helper))
        task.remove_helper(helper)
        self.assertFalse(task.is_user_approved(helper))
        self.assertTrue(task.is_user_helper(helper))

    def test_task_not_saved_when_chat_room_creation_fails(self):
        with patch("chat.signals.Room.objects.create", side_effect=RuntimeError("DB unavailable")):
            with self.assertRaises(RuntimeError):
                make_task(created_by=self.user)
        self.assertEqual(Task.objects.count(), 1)  # only setUp task

    def test_created_by_set_null_on_user_delete(self):
        temp = make_user("temp")
        task = make_task(created_by=temp)
        temp.delete()
        task.refresh_from_db()
        self.assertIsNone(task.created_by)

    def test_assigned_to_set_null_on_user_delete(self):
        temp = make_user("temp2")
        task = make_task(assigned_to=temp)
        temp.delete()
        task.refresh_from_db()
        self.assertIsNone(task.assigned_to)


# ---------------------------------------------------------------------------
# TaskQuerySet.with_metrics()
# ---------------------------------------------------------------------------
class TaskQuerySetMetricsTest(TestCase):
    def setUp(self):
        self.user = make_user("voter")
        self.other = make_user("other")
        self.task = make_task(created_by=self.user)

    def test_with_metrics_votes_up(self):
        TaskVote.objects.create(task=self.task, user=self.user, value=TaskVote.Value.UP)
        task = Task.objects.with_metrics().get(pk=self.task.pk)
        self.assertEqual(task.votes_up, 1)
        self.assertEqual(task.votes_down, 0)

    def test_with_metrics_votes_down(self):
        TaskVote.objects.create(task=self.task, user=self.user, value=TaskVote.Value.DOWN)
        task = Task.objects.with_metrics().get(pk=self.task.pk)
        self.assertEqual(task.votes_down, 1)
        self.assertEqual(task.votes_up, 0)

    def test_with_metrics_votes_score_sum(self):
        TaskVote.objects.create(task=self.task, user=self.user, value=TaskVote.Value.UP)
        TaskVote.objects.create(task=self.task, user=self.other, value=TaskVote.Value.DOWN)
        task = Task.objects.with_metrics().get(pk=self.task.pk)
        self.assertEqual(task.votes_score, 0)

    def test_with_metrics_no_votes_score_is_zero(self):
        task = Task.objects.with_metrics().get(pk=self.task.pk)
        self.assertEqual(task.votes_score, 0)

    def test_with_metrics_eval_success(self):
        TaskEvaluation.objects.create(task=self.task, user=self.user, value=TaskEvaluation.Value.SUCCESS)
        task = Task.objects.with_metrics().get(pk=self.task.pk)
        self.assertEqual(task.eval_success, 1)
        self.assertEqual(task.eval_failure, 0)

    def test_with_metrics_eval_failure(self):
        TaskEvaluation.objects.create(task=self.task, user=self.user, value=TaskEvaluation.Value.FAILURE)
        task = Task.objects.with_metrics().get(pk=self.task.pk)
        self.assertEqual(task.eval_failure, 1)
        self.assertEqual(task.eval_success, 0)


# ---------------------------------------------------------------------------
# TaskVote model
# ---------------------------------------------------------------------------
class TaskVoteModelTest(TestCase):
    def setUp(self):
        self.user = make_user("voter")
        self.task = make_task()

    def test_str_contains_user_and_task(self):
        vote = TaskVote.objects.create(task=self.task, user=self.user, value=TaskVote.Value.UP)
        self.assertIn(self.user.username, str(vote))
        self.assertIn(self.task.title, str(vote))

    def test_unique_constraint_one_vote_per_user_per_task(self):
        from django.db import IntegrityError

        TaskVote.objects.create(task=self.task, user=self.user, value=TaskVote.Value.UP)
        with self.assertRaises(IntegrityError):
            TaskVote.objects.create(task=self.task, user=self.user, value=TaskVote.Value.DOWN)

    def test_vote_deleted_with_task(self):
        vote = TaskVote.objects.create(task=self.task, user=self.user, value=TaskVote.Value.UP)
        vote_id = vote.id
        self.task.delete()
        self.assertFalse(TaskVote.objects.filter(id=vote_id).exists())


# ---------------------------------------------------------------------------
# TaskEvaluation model
# ---------------------------------------------------------------------------
class TaskEvaluationModelTest(TestCase):
    def setUp(self):
        self.user = make_user("evaluator")
        self.task = make_task(status=Task.Status.COMPLETED)

    def test_str_contains_user_and_task(self):
        ev = TaskEvaluation.objects.create(task=self.task, user=self.user, value=TaskEvaluation.Value.SUCCESS)
        self.assertIn(self.user.username, str(ev))
        self.assertIn(self.task.title, str(ev))

    def test_unique_constraint_one_evaluation_per_user_per_task(self):
        from django.db import IntegrityError

        TaskEvaluation.objects.create(task=self.task, user=self.user, value=TaskEvaluation.Value.SUCCESS)
        with self.assertRaises(IntegrityError):
            TaskEvaluation.objects.create(task=self.task, user=self.user, value=TaskEvaluation.Value.FAILURE)

    def test_evaluation_deleted_with_task(self):
        ev = TaskEvaluation.objects.create(task=self.task, user=self.user, value=TaskEvaluation.Value.SUCCESS)
        ev_id = ev.id
        self.task.delete()
        self.assertFalse(TaskEvaluation.objects.filter(id=ev_id).exists())
