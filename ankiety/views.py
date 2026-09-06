from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Prefetch
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from core.signals import survey_created
from core.utils import build_site_url

from .forms import SurveyForm
from .models import Survey, SurveyOption, SurveyVote


def _compute_vote_results(options):
    """Set .percentage on each option (requires annotated .vote_count). Returns total votes."""
    total_votes = sum(getattr(opt, "vote_count", 0) for opt in options)
    for opt in options:
        opt.percentage = round(opt.vote_count / total_votes * 100, 1) if total_votes else 0
    return total_votes


def _cast_vote(request, survey):
    """Handle a voting POST for the given survey. Returns True on success."""
    if not survey.is_active:
        messages.error(request, _("The survey is closed and votes cannot be cast."))
        return False

    if survey.allow_multiple_choice:
        option_ids = [oid for oid in request.POST.getlist("option") if oid]
    else:
        option_id = request.POST.get("option")
        option_ids = [option_id] if option_id else []

    if not option_ids:
        with transaction.atomic():
            deleted = SurveyVote.objects.filter(survey=survey, user=request.user).delete()[0]
        if deleted:
            messages.success(request, _("Your vote has been withdrawn."))
        else:
            messages.info(request, _("You have not voted in this survey yet."))
        return True

    options = list(SurveyOption.objects.filter(pk__in=option_ids, survey=survey))
    if len(options) != len(set(option_ids)):
        messages.error(request, _("Invalid option selected."))
        return False

    with transaction.atomic():
        SurveyVote.objects.filter(survey=survey, user=request.user).delete()
        SurveyVote.objects.bulk_create(SurveyVote(survey=survey, user=request.user, option=opt) for opt in options)
    messages.success(request, _("Your vote has been saved."))
    return True


@login_required
def survey_list(request):
    tab = request.GET.get("tab", "active")
    if tab not in ("active", "finished"):
        tab = "active"

    if request.method == "POST":
        survey = get_object_or_404(Survey, pk=request.POST.get("survey_id"))
        _cast_vote(request, survey)
        return redirect(f"{reverse('ankiety:list')}?tab={tab}")

    now = timezone.now()
    base_qs = Survey.objects.select_related("author").prefetch_related(Prefetch("options", queryset=SurveyOption.objects.annotate(vote_count=Count("votes")).order_by("order", "id")))

    if tab == "active":
        surveys = base_qs.filter(end_date__gte=now).order_by("end_date")
    else:
        surveys = base_qs.filter(end_date__lt=now).order_by("-end_date")

    surveys = list(surveys)

    user_votes_by_survey = {}
    for vote in SurveyVote.objects.filter(survey_id__in=[s.pk for s in surveys], user=request.user).order_by("-created_at"):
        user_votes_by_survey.setdefault(vote.survey_id, []).append(vote)

    for survey in surveys:
        survey.total_votes = _compute_vote_results(survey.options.all())
        survey_votes = user_votes_by_survey.get(survey.pk, [])
        if survey.allow_multiple_choice:
            survey.user_vote_ids = {v.option_id for v in survey_votes}
        else:
            survey.user_vote_ids = {survey_votes[0].option_id} if survey_votes else set()
        survey.has_voted = bool(survey.user_vote_ids)
        survey.can_edit = request.user == survey.author and survey.is_active

    toolbar_sort_items = [{"url": "?tab=active", "label": _("Ongoing"), "active": tab == "active"}, {"url": "?tab=finished", "label": _("Finished"), "active": tab == "finished"}]
    return render(request, "ankiety/survey_list.html", {"surveys": surveys, "current_tab": tab, "toolbar_sort_items": toolbar_sort_items})


@login_required
def survey_create(request):
    if request.method == "POST":
        form = SurveyForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                survey = form.save(commit=False)
                survey.author = request.user
                survey.save()
                form.create_options(survey)
            survey_created.send(sender='ankiety.views.survey_create', survey=survey, url=build_site_url(survey.get_absolute_url()))
            messages.success(request, _("The survey has been created."))
            return redirect("ankiety:list")
    else:
        form = SurveyForm()

    return render(request, "ankiety/survey_form.html", {"form": form})


@login_required
def survey_edit(request, pk):
    survey = get_object_or_404(Survey, pk=pk)
    if survey.author != request.user:
        return HttpResponseForbidden(_("Only the author can edit this survey."))
    if not survey.is_active:
        return HttpResponseForbidden(_("The survey is closed and cannot be edited."))

    if request.method == "POST":
        form = SurveyForm(request.POST, instance=survey)
        if form.is_valid():
            with transaction.atomic():
                survey = form.save()
                form.create_options(survey)
            messages.success(request, _("The survey has been updated."))
            return redirect("ankiety:detail", pk=survey.pk)
    else:
        form = SurveyForm(instance=survey)

    return render(request, "ankiety/survey_form.html", {"form": form})


@login_required
def survey_detail(request, pk):
    survey = get_object_or_404(Survey.objects.select_related("author").prefetch_related("options"), pk=pk)

    options = list(survey.options.annotate(vote_count=Count("votes")).order_by("order", "id"))
    total_votes = _compute_vote_results(options)

    user_votes = list(SurveyVote.objects.filter(survey=survey, user=request.user).select_related("option").order_by("-created_at"))
    if survey.allow_multiple_choice:
        user_vote_ids = {v.option_id for v in user_votes}
    else:
        user_vote_ids = {user_votes[0].option_id} if user_votes else set()

    all_votes = list(SurveyVote.objects.filter(survey=survey).select_related("user", "option"))
    voter_choices = {}
    for v in all_votes:
        voter_choices.setdefault(v.user, []).append(v.option.text)
    voter_choices = dict(sorted(voter_choices.items(), key=lambda item: item[0].username.lower()))

    if request.method == "POST":
        _cast_vote(request, survey)
        return redirect("ankiety:detail", pk=survey.pk)

    return render(
        request,
        "ankiety/survey_detail.html",
        {
            "survey": survey,
            "options": options,
            "total_votes": total_votes,
            "user_votes": user_votes,
            "user_vote_ids": user_vote_ids,
            "voter_choices": voter_choices,
            "has_voted": bool(user_votes),
            "can_edit": request.user == survey.author and survey.is_active,
            "is_active": survey.is_active,
        },
    )


@login_required
@require_POST
def survey_delete(request, pk):
    survey = get_object_or_404(Survey, pk=pk)
    if survey.author != request.user:
        return HttpResponseForbidden(_("Only the author can delete this survey."))

    survey.delete()
    messages.success(request, _("The survey has been deleted."))
    return redirect("ankiety:list")
