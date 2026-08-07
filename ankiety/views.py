from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Prefetch
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from .forms import SurveyForm
from .models import Survey, SurveyOption, SurveyVote


@login_required
def survey_list(request):
    tab = request.GET.get("tab", "active")
    if tab not in ("active", "finished"):
        tab = "active"

    now = timezone.now()
    base_qs = Survey.objects.select_related("author").prefetch_related(
        Prefetch(
            "options",
            queryset=SurveyOption.objects.annotate(
                vote_count=Count("votes")
            ).order_by("order", "id"),
        )
    )

    if tab == "active":
        surveys = base_qs.filter(end_date__gte=now).order_by("end_date")
    else:
        surveys = base_qs.filter(end_date__lt=now).order_by("-end_date")

    for survey in surveys:
        total_votes = sum(
            getattr(opt, "vote_count", 0) for opt in survey.options.all()
        )
        survey.total_votes = total_votes
        for opt in survey.options.all():
            opt.percentage = (
                round(opt.vote_count / total_votes * 100, 1) if total_votes else 0
            )

    return render(
        request,
        "ankiety/survey_list.html",
        {
            "surveys": surveys,
            "current_tab": tab,
        },
    )


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
    survey = get_object_or_404(
        Survey.objects.select_related("author").prefetch_related("options"),
        pk=pk,
    )

    options = list(
        survey.options.annotate(vote_count=Count("votes")).order_by("order", "id")
    )
    total_votes = sum(getattr(opt, "vote_count", 0) for opt in options)
    for opt in options:
        opt.percentage = (
            round(opt.vote_count / total_votes * 100, 1) if total_votes else 0
        )

    user_vote = (
        SurveyVote.objects.filter(survey=survey, user=request.user)
        .select_related("option")
        .first()
    )

    if request.method == "POST" and survey.is_active:
        option_id = request.POST.get("option")
        if not option_id:
            messages.error(request, _("Select one of the options."))
            return redirect("ankiety:detail", pk=survey.pk)

        option = get_object_or_404(SurveyOption, pk=option_id, survey=survey)
        with transaction.atomic():
            SurveyVote.objects.update_or_create(
                survey=survey,
                user=request.user,
                defaults={"option": option},
            )
        messages.success(request, _("Your vote has been saved."))
        return redirect("ankiety:detail", pk=survey.pk)

    return render(
        request,
        "ankiety/survey_detail.html",
        {
            "survey": survey,
            "options": options,
            "total_votes": total_votes,
            "user_vote": user_vote,
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
