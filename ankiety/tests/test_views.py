from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from ankiety.forms import SurveyForm
from ankiety.models import Survey, SurveyOption, SurveyVote
from chat.models import Message, Room

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
        self.client.post(reverse("ankiety:create"), {"title": "New survey", "description": "", "end_date": future, "options_text": "Red\nBlue", "allow_custom_options": "on"})
        self.assertEqual(Survey.objects.count(), 1)
        survey = Survey.objects.first()
        self.assertEqual(survey.author, self.author)
        self.assertTrue(survey.allow_custom_options)
        self.assertEqual(survey.options.count(), 2)
        self.assertEqual(survey.chat_room.title, "Survey #1: New survey")
        self.assertEqual(survey.chat_room.source_app, "ankiety")

    def test_edit_survey_get_renders_prefilled_form(self):
        survey = self._create_survey(self.author)
        self.client.login(username="author", password="pass")

        response = self.client.get(reverse("ankiety:edit", args=[survey.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].instance, survey)
        self.assertContains(response, "tw-card")

    def test_edit_survey_updates_options(self):
        survey = self._create_survey(self.author)
        self.client.login(username="author", password="pass")
        future = (timezone.now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")

        response = self.client.post(
            reverse("ankiety:edit", args=[survey.pk]), {"title": "Updated survey", "description": "Updated", "end_date": future, "options_text": "Maybe\nNo", "allow_custom_options": "on"}
        )

        self.assertRedirects(response, reverse("ankiety:detail", args=[survey.pk]))
        survey.refresh_from_db()
        self.assertEqual(survey.title, "Updated survey")
        self.assertEqual(list(survey.options.values_list("text", flat=True)), ["Maybe", "No"])

    def test_edit_survey_invalid_post_rerenders_errors_without_saving(self):
        survey = self._create_survey(self.author)
        self.client.login(username="author", password="pass")

        response = self.client.post(reverse("ankiety:edit", args=[survey.pk]), {"title": "", "description": "Updated", "end_date": "", "options_text": "Only one"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        survey.refresh_from_db()
        self.assertEqual(survey.title, "Test survey")

    def test_survey_detail_embeds_chat_and_shows_unread_count(self):
        survey = self._create_survey(self.author)
        Message.objects.create(room=survey.chat_room, sender=self.other, text="Question")
        self.client.login(username="author", password="pass")

        response = self.client.get(reverse("ankiety:detail", args=[survey.pk]))

        self.assertContains(response, f'data-room-id="{survey.chat_room.pk}"')
        self.assertContains(response, "Chat")
        self.assertEqual(response.context["chat_unread_count"], 1)
        self.assertTrue(response.context["ec_translations"])
        self.assertEqual(response.context["MESSAGE_MAX_LENGTH"], 1500)

    def test_deleting_survey_deletes_chat_room(self):
        survey = self._create_survey(self.author)
        room_id = survey.chat_room_id
        self.client.login(username="author", password="pass")

        self.client.post(reverse("ankiety:delete", args=[survey.pk]))

        self.assertFalse(Room.objects.filter(pk=room_id).exists())

    def test_create_survey_shows_length_errors(self):
        self.client.login(username="author", password="pass")
        future = (timezone.now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
        response = self.client.post(reverse("ankiety:create"), {"title": "T" * 201, "description": "D" * 3001, "end_date": future, "options_text": "Red\nBlue"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("title", response.context["form"].errors)
        self.assertIn("description", response.context["form"].errors)
        self.assertContains(response, 'class="tw-text-danger tw-text-sm tw-mt-1" role="alert"', count=2)
        self.assertEqual(Survey.objects.count(), 0)

    def test_participant_can_vote_without_adding_custom_option_when_enabled(self):
        survey = Survey.objects.create(title="Test survey", description="Description", end_date=timezone.now() + timedelta(days=1), author=self.author, allow_custom_options=True)
        yes = SurveyOption.objects.create(survey=survey, text="Yes", order=0)
        SurveyOption.objects.create(survey=survey, text="No", order=1)

        self.client.login(username="other", password="pass")
        response = self.client.post(reverse("ankiety:detail", args=[survey.pk]), {"option": yes.pk})

        self.assertRedirects(response, reverse("ankiety:detail", args=[survey.pk]))
        self.assertTrue(SurveyVote.objects.filter(survey=survey, user=self.other, option=yes).exists())

    def test_participant_can_add_custom_option_when_enabled(self):
        survey = Survey.objects.create(title="Test survey", description="Description", end_date=timezone.now() + timedelta(days=1), author=self.author, allow_custom_options=True)
        SurveyOption.objects.bulk_create([SurveyOption(survey=survey, text="Yes", order=0), SurveyOption(survey=survey, text="No", order=1)])

        self.client.login(username="other", password="pass")
        response = self.client.post(reverse("ankiety:detail", args=[survey.pk]), {"custom_option": "1", "text": "Maybe"})

        self.assertRedirects(response, reverse("ankiety:detail", args=[survey.pk]))
        option = survey.options.get(text="Maybe")
        self.assertEqual(option.created_by, self.other)
        self.assertEqual(option.order, 2)

        response = self.client.get(reverse("ankiety:detail", args=[survey.pk]))
        self.assertContains(response, "fa-user-plus")

    def test_participant_can_add_custom_option_from_survey_list(self):
        survey = Survey.objects.create(title="Test survey", description="Description", end_date=timezone.now() + timedelta(days=1), author=self.author, allow_custom_options=True)
        SurveyOption.objects.bulk_create([SurveyOption(survey=survey, text="Yes", order=0), SurveyOption(survey=survey, text="No", order=1)])
        self.client.login(username="other", password="pass")

        response = self.client.post(reverse("ankiety:list"), {"tab": "active", "survey_id": survey.pk, "custom_option": "1", f"survey-{survey.pk}-custom-text": "Maybe"})

        self.assertRedirects(response, f"{reverse('ankiety:list')}?tab=active")
        self.assertEqual(survey.options.get(text="Maybe").created_by, self.other)

    def test_participant_cannot_add_custom_option_when_disabled(self):
        survey = self._create_survey(self.author)
        self.client.login(username="other", password="pass")

        self.client.post(reverse("ankiety:detail", args=[survey.pk]), {"custom_option": "1", "text": "Maybe"})

        self.assertFalse(survey.options.filter(text="Maybe").exists())

    def test_custom_option_must_be_unique(self):
        survey = Survey.objects.create(title="Test survey", description="Description", end_date=timezone.now() + timedelta(days=1), author=self.author, allow_custom_options=True)
        SurveyOption.objects.bulk_create([SurveyOption(survey=survey, text="Yes", order=0), SurveyOption(survey=survey, text="No", order=1)])
        self.client.login(username="other", password="pass")

        response = self.client.post(reverse("ankiety:detail", args=[survey.pk]), {"custom_option": "1", "text": " yes "})

        self.assertEqual(response.status_code, 200)
        self.assertIn("text", response.context["custom_option_form"].errors)
        self.assertEqual(survey.options.count(), 2)

    def test_any_logged_in_user_can_edit_active_survey(self):
        survey = self._create_survey(self.author)
        self.client.login(username="other", password="pass")
        response = self.client.get(reverse("ankiety:edit", args=[survey.pk]))
        self.assertEqual(response.status_code, 200)

        future = (timezone.now() + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M")
        response = self.client.post(reverse("ankiety:edit", args=[survey.pk]), {"title": "Updated by other", "description": "", "end_date": future, "options_text": "One\nTwo"})
        self.assertRedirects(response, reverse("ankiety:detail", args=[survey.pk]))
        survey.refresh_from_db()
        self.assertEqual(survey.title, "Updated by other")

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
        self.assertContains(response, "tw-stepper-nav")
        self.assertContains(response, 'href="?tab=active"')
        self.assertContains(response, 'href="?tab=finished"')
        self.assertContains(response, f'href="{reverse("ankiety:create")}"')
        self.assertNotContains(response, "tw-sort-btn")

        response = self.client.get(reverse("ankiety:list"), {"tab": "finished"})
        self.assertContains(response, finished.title)
        self.assertNotContains(response, active.title)

    def test_detail_stepper_returns_to_selected_survey_category(self):
        survey = self._create_survey(self.author)
        self.client.login(username="author", password="pass")

        response = self.client.get(reverse("ankiety:detail", args=[survey.pk]), {"tab": "active", "q": "Test"})

        self.assertEqual(response.context["stepper"]["steps"][0]["url"], f"{reverse('ankiety:list')}?tab=active&q=Test")
        self.assertEqual(response.context["stepper"]["steps"][1]["url"], f"{reverse('ankiety:list')}?tab=finished&q=Test")

    def test_detail_navigation_follows_active_tab_and_search(self):
        first = self._create_survey(self.author, end_delta=timedelta(days=1), title="Navigation first")
        middle = self._create_survey(self.author, end_delta=timedelta(days=2), title="Navigation middle")
        last = self._create_survey(self.author, end_delta=timedelta(days=3), title="Navigation last")
        self.client.login(username="author", password="pass")

        response = self.client.get(reverse("ankiety:detail", args=[middle.pk]), {"tab": "active", "q": "Navigation"})

        self.assertEqual(response.context["previous_url"], f"{reverse('ankiety:detail', args=[first.pk])}?tab=active&q=Navigation")
        self.assertEqual(response.context["next_url"], f"{reverse('ankiety:detail', args=[last.pk])}?tab=active&q=Navigation")
        self.assertContains(response, "fa-chevron-left")
        self.assertContains(response, "fa-chevron-right")

    def test_detail_navigation_disables_missing_directions(self):
        first = self._create_survey(self.author, title="Only navigation survey")
        self.client.login(username="author", password="pass")

        response = self.client.get(reverse("ankiety:detail", args=[first.pk]), {"tab": "active", "q": "Only navigation"})

        self.assertIsNone(response.context["previous_url"])
        self.assertIsNone(response.context["next_url"])
        self.assertContains(response, 'class="tw-detail-nav-btn tw-disabled"', count=2)

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

    def test_duplicate_option_ids_are_rejected(self):
        survey = Survey.objects.create(title="Multiple choice", description="Description", end_date=timezone.now() + timedelta(days=1), author=self.author, allow_multiple_choice=True)
        SurveyOption.objects.bulk_create([SurveyOption(survey=survey, text="Yes", order=0), SurveyOption(survey=survey, text="No", order=1)])
        self.client.login(username="other", password="pass")

        response = self.client.post(reverse("ankiety:detail", args=[survey.pk]), {"option": [survey.options.get(text="Yes").pk, survey.options.get(text="Yes").pk]})

        self.assertRedirects(response, reverse("ankiety:detail", args=[survey.pk]))
        self.assertFalse(SurveyVote.objects.filter(survey=survey, user=self.other).exists())

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

    def test_detail_without_options_uses_shared_empty_state(self):
        survey = Survey.objects.create(title="Empty survey", end_date=timezone.now() - timedelta(days=1), author=self.author)
        self.client.login(username="author", password="pass")

        response = self.client.get(reverse("ankiety:detail", args=[survey.pk]))

        self.assertContains(response, "tw-empty-state")
        self.assertContains(response, "tw-empty-state-title")

    def test_detail_custom_option_is_not_required_for_voting(self):
        survey = Survey.objects.create(title="Custom options", end_date=timezone.now() + timedelta(days=1), author=self.author, allow_custom_options=True)
        SurveyOption.objects.create(survey=survey, text="Yes", order=0)
        SurveyOption.objects.create(survey=survey, text="No", order=1)
        self.client.login(username="author", password="pass")

        response = self.client.get(reverse("ankiety:detail", args=[survey.pk]))

        self.assertNotContains(response, 'name="text" required')

    def test_detail_custom_option_uses_standard_field_markup(self):
        survey = Survey.objects.create(title="Custom options", end_date=timezone.now() + timedelta(days=1), author=self.author, allow_custom_options=True)
        self.client.login(username="author", password="pass")

        response = self.client.get(reverse("ankiety:detail", args=[survey.pk]))

        self.assertContains(response, "tw-form-label")
        self.assertContains(response, "tw-form-control")

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
