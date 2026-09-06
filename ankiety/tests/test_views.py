from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from ankiety.forms import SurveyForm
from ankiety.models import Survey, SurveyOption, SurveyVote

User = get_user_model()


class SurveyViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.author = User.objects.create_user(username="author", email="author@example.com", password="pass")
        self.other = User.objects.create_user(username="other", email="other@example.com", password="pass")

    def _create_survey(self, user, end_delta=timedelta(days=1), title="Test survey"):
        survey = Survey.objects.create(title=title, description="Description", end_date=timezone.now() + end_delta, author=user)
        SurveyOption.objects.bulk_create([SurveyOption(survey=survey, text="Yes", order=0), SurveyOption(survey=survey, text="No", order=1)])
        return survey

    def test_create_survey_requires_login(self):
        response = self.client.get(reverse("ankiety:create"))
        self.assertEqual(response.status_code, 302)

    def test_create_survey(self):
        self.client.login(username="author", password="pass")
        future = (timezone.now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
        self.client.post(reverse("ankiety:create"), {"title": "New survey", "description": "", "end_date": future, "options_text": "Red\nBlue"})
        self.assertEqual(Survey.objects.count(), 1)
        survey = Survey.objects.first()
        self.assertEqual(survey.author, self.author)
        self.assertEqual(survey.options.count(), 2)

    def test_edit_only_by_author(self):
        survey = self._create_survey(self.author)
        self.client.login(username="other", password="pass")
        response = self.client.get(reverse("ankiety:edit", args=[survey.pk]))
        self.assertEqual(response.status_code, 403)

    def test_author_can_edit(self):
        survey = self._create_survey(self.author)
        self.client.login(username="author", password="pass")
        future = (timezone.now() + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M")
        response = self.client.post(reverse("ankiety:edit", args=[survey.pk]), {"title": "Updated title", "description": "", "end_date": future, "options_text": "One\nTwo"})
        self.assertRedirects(response, reverse("ankiety:detail", args=[survey.pk]))
        survey.refresh_from_db()
        self.assertEqual(survey.title, "Updated title")

    def test_options_can_change_while_active(self):
        survey = self._create_survey(self.author)
        yes_option = survey.options.get(text="Yes")
        SurveyVote.objects.create(survey=survey, user=self.other, option=yes_option)

        self.client.login(username="author", password="pass")
        future = (timezone.now() + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M")

        # Add a new option while keeping existing ones – votes should be preserved.
        self.client.post(reverse("ankiety:edit", args=[survey.pk]), {"title": "Updated title", "description": "", "end_date": future, "options_text": "Yes\nNo\nMaybe"})
        survey.refresh_from_db()
        self.assertEqual(survey.options.count(), 3)
        self.assertTrue(survey.options.filter(text="Yes").exists())
        self.assertEqual(SurveyVote.objects.filter(survey=survey).count(), 1)

        # Remove "Yes" (which has a vote) – the vote should be deleted.
        self.client.post(reverse("ankiety:edit", args=[survey.pk]), {"title": "Updated title", "description": "", "end_date": future, "options_text": "No\nMaybe"})
        survey.refresh_from_db()
        self.assertEqual(survey.options.count(), 2)
        self.assertFalse(survey.options.filter(text="Yes").exists())
        self.assertEqual(SurveyVote.objects.filter(survey=survey).count(), 0)

    def test_options_order_preserved_after_edit(self):
        survey = self._create_survey(self.author)

        self.client.login(username="author", password="pass")
        future = (timezone.now() + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M")

        # Rename the first option and add a new one in the middle.
        self.client.post(reverse("ankiety:edit", args=[survey.pk]), {"title": "Updated title", "description": "", "end_date": future, "options_text": "Maybe\nNew\nNo"})
        survey.refresh_from_db()
        texts = list(survey.options.order_by("order", "id").values_list("text", flat=True))
        self.assertEqual(texts, ["Maybe", "New", "No"])

    def test_active_and_finished_lists(self):
        active = self._create_survey(self.author, end_delta=timedelta(days=1), title="Active survey")
        finished = self._create_survey(self.author, end_delta=timedelta(days=-1), title="Finished survey")

        self.client.login(username="author", password="pass")

        response = self.client.get(reverse("ankiety:list"), {"tab": "active"})
        self.assertContains(response, active.title)
        self.assertNotContains(response, finished.title)

        response = self.client.get(reverse("ankiety:list"), {"tab": "finished"})
        self.assertContains(response, finished.title)
        self.assertNotContains(response, active.title)

    def test_voting(self):
        survey = self._create_survey(self.author)
        first_option = survey.options.first()
        second_option = survey.options.last()
        self.client.login(username="other", password="pass")

        response = self.client.post(reverse("ankiety:detail", args=[survey.pk]), {"option": first_option.pk})
        self.assertRedirects(response, reverse("ankiety:detail", args=[survey.pk]))
        self.assertEqual(SurveyVote.objects.filter(survey=survey).count(), 1)

        # User can change the vote while the survey is active.
        response = self.client.post(reverse("ankiety:detail", args=[survey.pk]), {"option": second_option.pk})
        self.assertRedirects(response, reverse("ankiety:detail", args=[survey.pk]))
        self.assertEqual(SurveyVote.objects.filter(survey=survey).count(), 1)
        vote = SurveyVote.objects.get(survey=survey, user=self.other)
        self.assertEqual(vote.option, second_option)

    def test_cannot_vote_after_end(self):
        survey = self._create_survey(self.author, end_delta=timedelta(days=-1))
        option = survey.options.first()
        self.client.login(username="other", password="pass")

        self.client.post(reverse("ankiety:detail", args=[survey.pk]), {"option": option.pk})
        self.assertEqual(SurveyVote.objects.count(), 0)

    def test_withdraw_single_choice_vote(self):
        survey = self._create_survey(self.author)
        option = survey.options.first()
        self.client.login(username="other", password="pass")

        self.client.post(reverse("ankiety:detail", args=[survey.pk]), {"option": option.pk})
        self.assertEqual(SurveyVote.objects.filter(survey=survey, user=self.other).count(), 1)

        response = self.client.post(reverse("ankiety:detail", args=[survey.pk]), {"option": ""})
        self.assertRedirects(response, reverse("ankiety:detail", args=[survey.pk]))
        self.assertEqual(SurveyVote.objects.filter(survey=survey, user=self.other).count(), 0)

    def test_detail_results_show_vote_percentages(self):
        survey = self._create_survey(self.author, end_delta=timedelta(days=-1))
        yes = survey.options.get(text="Yes")
        no = survey.options.get(text="No")
        third = User.objects.create_user(username="third", email="third@example.com", password="pass")
        SurveyVote.objects.create(survey=survey, user=self.author, option=yes)
        SurveyVote.objects.create(survey=survey, user=self.other, option=yes)
        SurveyVote.objects.create(survey=survey, user=third, option=no)

        self.client.login(username="author", password="pass")
        response = self.client.get(reverse("ankiety:detail", args=[survey.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_votes"], 3)
        percentages = {opt.text: opt.percentage for opt in response.context["options"]}
        self.assertEqual(percentages, {"Yes": 66.7, "No": 33.3})
        self.assertContains(response, 'data-progress="66.7"')

    def test_detail_results_zero_votes(self):
        survey = self._create_survey(self.author, end_delta=timedelta(days=-1))

        self.client.login(username="author", password="pass")
        response = self.client.get(reverse("ankiety:detail", args=[survey.pk]))
        self.assertEqual(response.context["total_votes"], 0)
        self.assertTrue(all(opt.percentage == 0 for opt in response.context["options"]))

    def test_list_results_show_percentages_for_finished_survey(self):
        survey = self._create_survey(self.author, end_delta=timedelta(days=-1))
        yes = survey.options.get(text="Yes")
        SurveyVote.objects.create(survey=survey, user=self.other, option=yes)

        self.client.login(username="author", password="pass")
        response = self.client.get(reverse("ankiety:list"), {"tab": "finished"})
        self.assertEqual(response.status_code, 200)
        listed = {s.pk: s for s in response.context["surveys"]}
        self.assertEqual(listed[survey.pk].total_votes, 1)
        percentages = {opt.text: opt.percentage for opt in listed[survey.pk].options.all()}
        self.assertEqual(percentages, {"Yes": 100.0, "No": 0})
        self.assertContains(response, 'data-progress="100.0"')

    def test_delete_only_by_author(self):
        survey = self._create_survey(self.author)
        self.client.login(username="other", password="pass")
        response = self.client.post(reverse("ankiety:delete", args=[survey.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Survey.objects.count(), 1)

    def test_author_can_delete(self):
        survey = self._create_survey(self.author)
        self.client.login(username="author", password="pass")
        self.client.post(reverse("ankiety:delete", args=[survey.pk]))
        self.assertEqual(Survey.objects.count(), 0)

    def test_author_cannot_edit_closed_survey(self):
        survey = self._create_survey(self.author, end_delta=timedelta(days=-1))
        original_title = survey.title

        self.client.login(username="author", password="pass")
        past = (timezone.now() + timedelta(days=-3)).strftime("%Y-%m-%dT%H:%M")
        response = self.client.post(reverse("ankiety:edit", args=[survey.pk]), {"title": "Updated title", "description": "", "end_date": past, "options_text": "Changed\nOptions"})
        self.assertEqual(response.status_code, 403)
        survey.refresh_from_db()
        self.assertEqual(survey.title, original_title)


class SurveyFormTests(TestCase):
    def test_options_text_parsing(self):
        data = {"title": "Test", "description": "", "end_date": (timezone.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"), "options_text": " A \n B \n A \n"}
        form = SurveyForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn("options_text", form.errors)

    def test_end_date_naive_is_made_aware(self):
        data = {"title": "Test", "description": "", "end_date": (timezone.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"), "options_text": "A\nB"}
        form = SurveyForm(data)
        self.assertTrue(form.is_valid())
        self.assertIsNotNone(form.cleaned_data["end_date"].tzinfo)
