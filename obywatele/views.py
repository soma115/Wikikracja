import json
import logging
from datetime import timedelta
from urllib.parse import urlencode

import django.contrib.messages as messages
from allauth.account.models import EmailAddress
from allauth.account.signals import email_confirmed, user_signed_up
from django.conf import settings as s
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.contrib.messages import error, success
from django.core.mail import send_mail
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.db import DatabaseError
from django.db.models import Case, Count, IntegerField, Q, Sum, Value, When
from django.dispatch import receiver
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import check_for_language
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from django_filters.views import FilterView
from django_tables2.views import SingleTableMixin

from chat.services import get_user_public_message_rows
from core.signals import citizen_proposed
from obywatele.filters import UzytkownikFilter
from obywatele.forms import AvatarForm, EmailChangeForm, OnboardingDetailsForm, ProfileForm, UserForm, UsernameChangeForm
from obywatele.models import DeletionRequest, Rate, Uzytkownik
from obywatele.services import get_citizen_activity, get_citizen_created_items
from obywatele.tables import UzytkownikTable
from site_settings.params import get_param
from tasks.activity import get_user_tasks

log = logging.getLogger(__name__)

signer = TimestampSigner()


def is_email_confirmed_for_candidate(user: User, profile: Uzytkownik) -> bool:
    if profile.polecajacy:
        return True
    return EmailAddress.objects.filter(user=user, verified=True).exists()


def get_onboarding_user_from_request(request: HttpRequest):
    """
    CRITICAL: Find user for onboarding form access.

    DESIGN NOTE: Three ways to access onboarding form:
    1. Session (immediate after signup) - primary method
    2. Email link with signed token (backup after email confirmation) - overrides session
    3. Fallback for already active users with incomplete onboarding

    Without this logic, users get "Could not find your onboarding account" error.
    """
    # METHOD 1: Session - set immediately after signup
    onboarding_user_id = request.session.get('onboarding_user_id')

    # METHOD 2: Email link with signed token - overrides session if present
    # Token contains uid: signer.sign(uid) -> '<uid>:<timestamp>:<signature>'
    token = request.GET.get('token')
    if token:
        try:
            signed_value = signer.unsign(token, max_age=get_param('delete_inactive_user_after') * 24 * 60 * 60)
            onboarding_user_id = int(signed_value)
            request.session['onboarding_user_id'] = onboarding_user_id
            request.session.modified = True
        except (BadSignature, SignatureExpired, ValueError):
            onboarding_user_id = None

    if not onboarding_user_id:
        return None

    # Standard path: inactive user (just signed up, not yet approved)
    user = User.objects.filter(pk=onboarding_user_id, is_active=False).first()
    if user:
        return user

    # METHOD 3: Fallback - active user with incomplete onboarding
    # This handles edge cases where user became active but didn't complete onboarding
    user = User.objects.filter(pk=onboarding_user_id).first()
    if user and hasattr(user, 'uzytkownik'):
        profile = user.uzytkownik
        if profile.onboarding_status in [Uzytkownik.OnboardingStatus.EMAIL_ENTERED, Uzytkownik.OnboardingStatus.EMAIL_CONFIRMED]:
            return user

    # METHOD 4: Fallback for already accepted users (is_active=True)
    # Allow access for users who have already been accepted and completed onboarding
    user = User.objects.filter(pk=onboarding_user_id, is_active=True).first()
    if user and hasattr(user, 'uzytkownik'):
        return user

    return None


def population():
    try:
        population = User.objects.filter(is_active=True).count()
        return population
    except DatabaseError:
        log.exception("Could not calculate population.")
        return 0


def required_reputation():
    '''
    Załóżmy, że próg akceptacji wynosi 3.
    W grupie pojawiają się po kolei 1, 2, 3 osoby.
    W takiej sytuacji nikt nie może osiągnąć progu akceptacji wynoszącego 3 bo w grupie są np. 2 osoby.
    Musi więc istnieć mechanizm, który chwilowo obniża próg akceptacji.

    Rozwiązanie:
    populacja - docelowy_próg_akceptacji = chwilowy_próg_akceptacji
    1 - 3 = -2
    2 - 3 = -1
    3 - 3 =  0
    4 - 3 = +1
    5 - 3 = +2
    6 - 3 = +3  # tutaj zaczyna być używany docelowy_próg_akceptacji
    7 - 3 = +3
    8 - 3 = +3

    To rozwiązanie rodzi następny problem:
    Ponieważ próg akceptacji rośnie,
    ale pierwszej osobie w grupie nikt nie dał Akceptuję,
    to po automatycznym podniesieniu progu - pierwsza osoba jest usuwana.

    Stąd bierze się mechanizm automatycznego nadawania istniejącym osobom punktów reputacji:
    grant_automatic_reputation()
    '''
    pop = population()
    acceptance = get_param('acceptance')
    if pop < acceptance * 2:
        return pop - acceptance
    return acceptance


@login_required
def parameters(request: HttpRequest):
    return render(request, 'obywatele/parameters.html', {'population': population(), 'acceptance': get_param('acceptance'), 'delete_inactive_user_after': get_param('delete_inactive_user_after')})


@login_required()
def change_email(request: HttpRequest):
    form = EmailChangeForm(request.user)
    if request.method == 'POST':
        form = EmailChangeForm(request.user, request.POST)
        if form.is_valid():
            form.save()
            message = _("Your new email has been saved.")
            success(request, (message))
            return redirect('obywatele:my_profile')
        else:
            message = form.non_field_errors().as_text() or next(iter(form.errors.values()))
            error(request, (message))
            return redirect('obywatele:my_profile')
    else:
        return render(request, 'obywatele/change_email.html', {'form': form})


@login_required()
def change_username(request: HttpRequest):
    if request.method == 'POST':
        form = UsernameChangeForm(request.user, request.POST)
        if form.is_valid():
            form.save()
            message = _("Your name has been saved.")
            success(request, (message))
            return redirect('obywatele:my_profile')
        else:
            message = form.errors
            error(request, (message))
            return redirect('obywatele:my_profile')
    else:
        form = UsernameChangeForm(request.user)
    return render(request, 'obywatele/change_username.html', {'form': form})


@login_required
def obywatele(request: HttpRequest):
    allowed_sort_fields = {
        'username': 'username',
        'email': 'email',
        'phone': 'uzytkownik__phone',
        'last_login': 'last_login',
        'city': 'uzytkownik__city',
        'first_name': 'first_name',
        'last_name': 'last_name',
        'joined': 'uzytkownik__data_przyjecia',
    }
    blank_sort_fields = {
        'username': 'username_is_blank',
        'email': 'email_is_blank',
        'phone': 'phone_is_blank',
        'last_login': 'last_login_is_blank',
        'city': 'city_is_blank',
        'first_name': 'first_name_is_blank',
        'last_name': 'last_name_is_blank',
        'joined': 'joined_is_blank',
    }
    default_sort = '-joined'

    five_min_ago = timezone.now() - timedelta(minutes=5)
    seven_days_ago = timezone.now() - timedelta(days=7)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    aktywnosc = request.GET.get('aktywnosc', '')
    _aktywnosc_filters = {
        'online': Q(last_login__gte=five_min_ago),
        '7d': Q(last_login__gte=seven_days_ago),
        '30d': Q(last_login__gte=thirty_days_ago),
        'nieaktywni': Q(last_login__lt=thirty_days_ago) | Q(last_login__isnull=True),
    }

    requested_sort = request.GET.get('sort', default_sort)
    requested_field = requested_sort.lstrip('-')

    if requested_field not in allowed_sort_fields:
        requested_sort = default_sort
        requested_field = default_sort.lstrip('-')

    sort_expression = allowed_sort_fields[requested_field]
    order_prefix = '-' if requested_sort.startswith('-') else ''

    order_by_fields = []
    blank_field = blank_sort_fields.get(requested_field)
    if blank_field:
        order_by_fields.append(blank_field)
    order_by_fields.append(f'{order_prefix}{sort_expression}')
    order_by_fields.append('id')

    uid = (
        User.objects.filter(is_active=True)
        .select_related('uzytkownik')
        .annotate(
            username_is_blank=Case(When(Q(username__isnull=True) | Q(username__exact=''), then=Value(1)), default=Value(0), output_field=IntegerField()),
            email_is_blank=Case(When(Q(email__isnull=True) | Q(email__exact=''), then=Value(1)), default=Value(0), output_field=IntegerField()),
            phone_is_blank=Case(When(Q(uzytkownik__phone__isnull=True) | Q(uzytkownik__phone__exact=''), then=Value(1)), default=Value(0), output_field=IntegerField()),
            last_login_is_blank=Case(When(last_login__isnull=True, then=Value(1)), default=Value(0), output_field=IntegerField()),
            city_is_blank=Case(When(Q(uzytkownik__city__isnull=True) | Q(uzytkownik__city__exact=''), then=Value(1)), default=Value(0), output_field=IntegerField()),
            first_name_is_blank=Case(When(Q(first_name__isnull=True) | Q(first_name__exact=''), then=Value(1)), default=Value(0), output_field=IntegerField()),
            last_name_is_blank=Case(When(Q(last_name__isnull=True) | Q(last_name__exact=''), then=Value(1)), default=Value(0), output_field=IntegerField()),
            joined_is_blank=Case(When(Q(uzytkownik__data_przyjecia__isnull=True), then=Value(1)), default=Value(0), output_field=IntegerField()),
        )
        .order_by(*order_by_fields)
    )
    if aktywnosc in _aktywnosc_filters:
        uid = uid.filter(_aktywnosc_filters[aktywnosc])

    req_rep = required_reputation()
    users_with_reputation = []
    for user in uid:
        if hasattr(user, 'uzytkownik'):
            reputation = Rate.objects.filter(kandydat_id=user.uzytkownik.id).aggregate(Sum('rate'))['rate__sum'] or 0
            user.near_threshold = reputation <= (req_rep + 1)
        else:
            user.near_threshold = False

        user.pending_deletion = hasattr(user, 'deletion_request')

        if user.last_login is None:
            user.activity_status = 'inactive'
        elif user.last_login >= five_min_ago:
            user.activity_status = 'online'
        elif user.last_login >= seven_days_ago:
            user.activity_status = 'active'
        elif user.last_login >= thirty_days_ago:
            user.activity_status = 'dormant'
        else:
            user.activity_status = 'inactive'

        users_with_reputation.append(user)

    default_directions = {'username': 'asc', 'email': 'asc', 'phone': 'asc', 'last_login': 'desc', 'city': 'asc', 'first_name': 'asc', 'last_name': 'asc', 'joined': 'desc'}

    sort_meta = {}
    for field in allowed_sort_fields:
        is_current = requested_field == field
        if is_current:
            current_direction = 'desc' if requested_sort.startswith('-') else 'asc'
            next_param = field if current_direction == 'desc' else f'-{field}'
        else:
            current_direction = None
            default_direction = default_directions.get(field, 'asc')
            next_param = f'-{field}' if default_direction == 'desc' else field

        sort_meta[field] = {'is_current': is_current, 'direction': current_direction, 'next_param': next_param}

    _aktywnosc_ctx = aktywnosc if aktywnosc in _aktywnosc_filters else ''
    sort_url_suffix = f'&aktywnosc={_aktywnosc_ctx}' if _aktywnosc_ctx else ''
    sort_param = f'sort={requested_sort}' if requested_sort != default_sort else ''

    return render(
        request,
        'obywatele/start.html',
        {
            'uid': users_with_reputation,  # Don't change to 'user' - it will break menu
            'sort_meta': sort_meta,
            'current_sort': requested_sort,
            'aktywnosc': _aktywnosc_ctx,
            'sort_url_suffix': sort_url_suffix,
            'sort_param': sort_param,
        },
    )


@login_required
def poczekalnia(request: HttpRequest):
    # zliczaj_obywateli(request)
    uid = User.objects.filter(is_active=False).select_related('uzytkownik')
    verified_user_ids = set(EmailAddress.objects.filter(user__in=uid, verified=True).values_list('user_id', flat=True))

    # Get the current user's profile
    try:
        citizen_profile = request.user.uzytkownik
    except Uzytkownik.DoesNotExist:
        error(request, _('Your profile does not exist. Please contact administrator.'))
        return redirect('home:index')

    candidate_profiles = {user.id: user.uzytkownik for user in uid if hasattr(user, 'uzytkownik')}
    candidate_profile_ids = [profile.id for profile in candidate_profiles.values()]
    existing_rates = {rate.kandydat_id: rate for rate in Rate.objects.filter(obywatel=citizen_profile, kandydat_id__in=candidate_profile_ids)}

    # Count explicit ratings per candidate by type. A neutral rating (rate=0)
    # only exists when a citizen explicitly clicked "Indifferent"; we no longer
    # auto-create Rate rows just by viewing the list.
    ratings_positive_map = {row['kandydat_id']: row['total'] for row in Rate.objects.filter(kandydat_id__in=candidate_profile_ids, rate=1).values('kandydat_id').annotate(total=Count('id'))}
    ratings_neutral_map = {row['kandydat_id']: row['total'] for row in Rate.objects.filter(kandydat_id__in=candidate_profile_ids, rate=0).values('kandydat_id').annotate(total=Count('id'))}
    ratings_negative_map = {row['kandydat_id']: row['total'] for row in Rate.objects.filter(kandydat_id__in=candidate_profile_ids, rate=-1).values('kandydat_id').annotate(total=Count('id'))}

    # Process users and add rating directly to each user object for easy access in template
    users_with_ratings = []
    for user in uid:
        candidate_profile = candidate_profiles.get(user.id)
        if not candidate_profile:
            continue

        # Show current user's rating for this candidate, but do not create a
        # Rate record just by opening the waiting room.
        rate = existing_rates.get(candidate_profile.id)
        user.rating = rate.rate if rate else 0

        user.ratings_positive = ratings_positive_map.get(candidate_profile.id, 0)
        user.ratings_neutral = ratings_neutral_map.get(candidate_profile.id, 0)
        user.ratings_negative = ratings_negative_map.get(candidate_profile.id, 0)

        user.email_confirmed = (user.id in verified_user_ids) or bool(candidate_profile.polecajacy)
        user.form_completion_percent = candidate_profile.form_completion_percent
        users_with_ratings.append(user)

    return render(
        request,
        'obywatele/poczekalnia.html',
        {
            'uid': users_with_ratings,  # Users with ratings attached
            'population': population(),
            'acceptance': get_param('acceptance'),
            'delete_inactive_user_after': get_param('delete_inactive_user_after'),
            'required_reputation': required_reputation(),
        },
    )


def onboarding_details(request: HttpRequest):
    user = get_onboarding_user_from_request(request)
    if not user:
        error(request, _('Could not find your onboarding account.'))
        return redirect('account_signup')

    profile = user.uzytkownik

    if request.method == 'POST':
        form = OnboardingDetailsForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            user.first_name = form.cleaned_data.get('first_name', '')
            user.last_name = form.cleaned_data.get('last_name', '')
            user.save()

            profile.onboarding_status = Uzytkownik.OnboardingStatus.FORM_COMPLETED
            profile.save()

            success(request, _('Your onboarding form has been saved.'))
            return redirect('obywatele:onboarding_waiting')
    else:
        form = OnboardingDetailsForm(instance=profile, initial={'first_name': user.first_name, 'last_name': user.last_name})

    return render(request, 'obywatele/onboarding_details.html', {'form': form, 'email_confirmed': EmailAddress.objects.filter(user=user, verified=True).exists()})


def onboarding_waiting(request: HttpRequest):
    user = get_onboarding_user_from_request(request)
    if not user:
        error(request, _('Could not find your onboarding account.'))
        return redirect('account_signup')

    return render(request, 'obywatele/onboarding_waiting.html', {'email_confirmed': EmailAddress.objects.filter(user=user, verified=True).exists()})


@login_required
def dodaj(request: HttpRequest):
    if request.method == 'POST':
        user_form = UserForm(request.POST)
        profile_form = ProfileForm(request.POST, request.FILES)

        if user_form.is_valid() and profile_form.is_valid():
            mail = user_form.cleaned_data['email']
            if User.objects.filter(email__iexact=mail).exists():
                # is_valid doesn't check if email exist
                message = _('Email already exist')
                error(request, (message))
                return redirect('obywatele:zaproponuj_osobe')

            else:
                # If everything is ok
                candidate = user_form.save()
                candidate.is_active = False
                candidate.save()

                # CANDIDATE — profil powstał już przez sygnał post_save;
                # pola profilu kopiujemy po autorytatywnej liście z modelu.
                candidate_profile = candidate.uzytkownik
                candidate_profile.polecajacy = request.user.username
                for field in Uzytkownik.ONBOARDING_FORM_FIELDS:
                    setattr(candidate_profile, field, profile_form.cleaned_data[field])
                candidate_profile.save()

                # Since you proposed new person,
                # you probably also want to accept him/her
                citizen = request.user.uzytkownik
                rate = Rate()
                rate.obywatel = citizen
                rate.kandydat = candidate_profile
                rate.rate = 1
                rate.save()

                # Create EmailAddress with verified=True for manually invited users
                EmailAddress.objects.get_or_create(user=candidate, email=candidate.email, defaults={'verified': True, 'primary': True})

                message = _('The new user has been saved')
                success(request, (message))

                log.info(
                    f'EMAIL_DIAG trigger=new_citizen_proposed source=obywatele.views.dodaj actor_user_id={request.user.id} actor_username={request.user.username} candidate_user_id={candidate.id} candidate_username={candidate.username} subject={_("New citizen has been proposed")}'
                )
                citizen_proposed.send(sender='obywatele.views.dodaj', candidate=candidate, proposed_by=request.user)

                return redirect('obywatele:poczekalnia')
        else:
            error_messages = []

            for form in (user_form, profile_form):
                errors = form.errors.get_json_data()
                for field_errors in errors.values():
                    for err in field_errors:
                        error_messages.append(err.get('message'))

            message = error_messages[0] if error_messages else _('Please correct the highlighted errors.')
            error(request, (message))
    else:
        user_form = UserForm()
        profile_form = ProfileForm()

    return render(request, 'obywatele/dodaj.html', {'user_form': user_form, 'profile_form': profile_form})


@login_required
def my_profile(request: HttpRequest):
    user = request.user
    profile = request.user.uzytkownik

    push_notifications = [
        {'type': 'push_task', 'title': _('Activities'), 'description': _('New activities'), 'enabled': profile.push_notifications_task},
        {'type': 'push_obywatele', 'title': _('Citizenship'), 'description': _('New citizens, membership requests'), 'enabled': profile.push_notifications_obywatele},
        {'type': 'push_post', 'title': _('Documents'), 'description': _('New and updated documents'), 'enabled': profile.push_notifications_post},
        {'type': 'push_events', 'title': _('Calendar'), 'description': _('Upcoming events, reminders'), 'enabled': profile.push_notifications_events},
        {'type': 'push_glosowania', 'title': _('Voting'), 'description': _('Law proposals, voting reminders, results'), 'enabled': profile.push_notifications_glosowania},
        {'type': 'push_survey', 'title': _('Surveys'), 'description': _('New surveys'), 'enabled': profile.push_notifications_survey},
        {'type': 'push_chat', 'title': _('Chat'), 'description': _('New messages from rooms you haven\'t muted'), 'enabled': profile.push_notifications_chat},
    ]

    push_devices = [
        {'type': 'push_phone', 'title': _('Phone'), 'description': _('Mobile phones and tablets'), 'enabled': profile.push_phone_enabled},
        {'type': 'push_computer', 'title': _('Computer'), 'description': _('Desktop browsers and PWAs'), 'enabled': profile.push_computer_enabled},
    ]

    deletion_request = getattr(user, 'deletion_request', None)

    return render(
        request,
        'obywatele/my_profile.html',
        {
            'profile': profile,
            'user': user,
            'population': population(),
            'required_reputation': required_reputation(),
            'email_frequency': profile.email_frequency,
            'email_frequency_choices': Uzytkownik.EmailFrequency.choices,
            'push_notifications': push_notifications,
            'push_devices': push_devices,
            'avatar_form': AvatarForm(),
            'deletion_request': deletion_request,
        },
    )


@login_required
def upload_avatar(request: HttpRequest):
    profile = request.user.uzytkownik
    if request.method == 'POST':
        form = AvatarForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
    return redirect('obywatele:my_profile')


@login_required
@require_POST
def toggle_notification(request: HttpRequest):

    PUSH_FIELDS = {
        'push_obywatele': 'push_notifications_obywatele',
        'push_glosowania': 'push_notifications_glosowania',
        'push_events': 'push_notifications_events',
        'push_chat': 'push_notifications_chat',
        'push_post': 'push_notifications_post',
        'push_task': 'push_notifications_task',
        'push_survey': 'push_notifications_survey',
        'push_phone': 'push_phone_enabled',
        'push_computer': 'push_computer_enabled',
    }

    try:
        data = json.loads(request.body)
        notification_type = request.GET.get('type')

        profile = request.user.uzytkownik

        if notification_type == 'email_frequency':
            value = data.get('value')
            if value not in [choice[0] for choice in Uzytkownik.EmailFrequency.choices]:
                return JsonResponse({'success': False, 'error': 'Invalid frequency'})
            profile.email_frequency = value
            profile.save()
            return JsonResponse({'success': True})

        field_name = PUSH_FIELDS.get(notification_type)
        if not field_name:
            return JsonResponse({'success': False, 'error': 'Invalid notification type'})

        enabled = data.get('enabled', False)
        setattr(profile, field_name, enabled)
        profile.save()

        return JsonResponse({'success': True})

    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
def my_assets(request: HttpRequest):
    user = request.user
    profile = request.user.uzytkownik

    if request.method == 'POST':
        # first_name/last_name należą do User, nie do Uzytkownik — zapisujemy je osobno.
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            user.first_name = form.cleaned_data['first_name']
            user.last_name = form.cleaned_data['last_name']
            user.save()
            form.save()

            success(request, _('Changes was saved'))
            return redirect('obywatele:my_profile')
        else:  # form.is_NOT_valid():
            error(request, form.errors)
            return redirect('obywatele:my_profile')
    else:  # request.method != 'POST':
        form = ProfileForm(instance=profile, initial={'first_name': user.first_name, 'last_name': user.last_name})
        return render(request, 'obywatele/my_assets.html', {'user': user, 'profile': profile, 'form': form})


class AssetListView(LoginRequiredMixin, SingleTableMixin, FilterView):
    table_class = UzytkownikTable
    model = Uzytkownik
    template_name = 'obywatele/assets.html'
    filterset_class = UzytkownikFilter
    table_pagination = False

    def get_queryset(self):
        return Uzytkownik.objects.filter(uid__is_active=True).select_related('uid', 'voivodeship')


@login_required
def obywatele_szczegoly(request: HttpRequest, pk: int):
    '''
    -[x] There has to be a table relating user and new person. This table is needed because vote for person may be withdrawn at some point. So there are 3 states:
      1. Candidate is positive
      2. Candidate is neutral (not clicked, default)
      3. Candidate is negative
    3 states are needed because:
      - this is a fact, those 3 states really exist
      - but most importantly: it should be possible to take reputation away - even if somebody did not give reputation to that person before.
    -[x] Reputation should be calculated from Rate table relating citizen and candidate.
    -[x] Counter should NOT be zeroed out if person drop below required reputation.
    -[x] New person increase population so also increase reputation requirements for existing citizens. Therefore every time new person is accepted - every other old member should have his reputation increased autmatically. And vice versa - if somebody is banned - everyone else should loose one point of reputation from banned person.
    '''
    # zliczaj_obywateli(request)  # run reputation counting because a lot can change in the meanwhile

    candidate_profile = get_object_or_404(Uzytkownik, uid_id=pk)
    candidate_user = User.objects.get(pk=pk)
    email_confirmed = is_email_confirmed_for_candidate(candidate_user, candidate_profile)
    form_completion_percent = candidate_profile.form_completion_percent
    citizen_profile = request.user.uzytkownik
    polecajacy = citizen_profile.polecajacy

    # Do not auto-create a Rate record on GET; only create one when the citizen
    # explicitly casts a vote. This keeps the neutral rating counter accurate.
    rate = Rate.objects.filter(kandydat=candidate_profile, obywatel=citizen_profile).first()

    if request.method == 'POST' and candidate_profile != citizen_profile:
        action = request.POST.get('action')
        if action == 'accept':
            if rate is None:
                rate = Rate.objects.create(kandydat=candidate_profile, obywatel=citizen_profile, rate=1)
            else:
                rate.rate = 1
                rate.save(update_fields=['rate'])
        elif action == 'reject':
            if rate is None:
                rate = Rate.objects.create(kandydat=candidate_profile, obywatel=citizen_profile, rate=-1)
            else:
                rate.rate = -1
                rate.save(update_fields=['rate'])
        elif action == 'reset':
            if rate is None:
                rate = Rate.objects.create(kandydat=candidate_profile, obywatel=citizen_profile, rate=0)
            else:
                rate.rate = 0
                rate.save(update_fields=['rate'])
        return redirect(request.path)

    if rate is None or rate.rate == 0:
        r1 = 'neutral'
    elif rate.rate == 1:
        r1 = 'positive'
    else:
        r1 = 'negative'

    ratings_positive = Rate.objects.filter(kandydat=candidate_profile, rate=1).count()
    ratings_neutral = Rate.objects.filter(kandydat=candidate_profile, rate=0).count()
    ratings_negative = Rate.objects.filter(kandydat=candidate_profile, rate=-1).count()

    # Previous and Next
    obj = get_object_or_404(User, pk=pk)
    # Przewijaj w tej samej kolejności co lista obywateli, honorując parametr
    # 'sort' (przekazywany z listy), zachowując filtr po is_active.
    allowed_sort_fields = {
        'username': 'username',
        'email': 'email',
        'phone': 'uzytkownik__phone',
        'last_login': 'last_login',
        'city': 'uzytkownik__city',
        'first_name': 'first_name',
        'last_name': 'last_name',
        'joined': 'uzytkownik__data_przyjecia',
    }
    blank_annotations = {
        'username': Q(username__isnull=True) | Q(username__exact=''),
        'email': Q(email__isnull=True) | Q(email__exact=''),
        'phone': Q(uzytkownik__phone__isnull=True) | Q(uzytkownik__phone__exact=''),
        'last_login': Q(last_login__isnull=True),
        'city': Q(uzytkownik__city__isnull=True) | Q(uzytkownik__city__exact=''),
        'first_name': Q(first_name__isnull=True) | Q(first_name__exact=''),
        'last_name': Q(last_name__isnull=True) | Q(last_name__exact=''),
        'joined': Q(uzytkownik__data_przyjecia__isnull=True),
    }
    default_sort = '-joined'
    requested_sort = request.GET.get('sort', default_sort)
    requested_field = requested_sort.lstrip('-')
    if requested_field not in allowed_sort_fields:
        requested_sort = default_sort
        requested_field = default_sort.lstrip('-')

    order_prefix = '-' if requested_sort.startswith('-') else ''
    ordered_qs = (
        User.objects.filter(is_active=obj.is_active)
        .annotate(sort_is_blank=Case(When(blank_annotations[requested_field], then=Value(1)), default=Value(0), output_field=IntegerField()))
        .order_by('sort_is_blank', f'{order_prefix}{allowed_sort_fields[requested_field]}', 'id')
    )
    ordered_pks = list(ordered_qs.values_list('pk', flat=True))
    try:
        idx = ordered_pks.index(obj.pk)
    except ValueError:
        idx = -1

    # 'next' => przycisk "← Previous" (w górę listy, do poprzedniego)
    # 'prev' => przycisk "Next →" (w dół listy, do następnego)
    # Pierwsza osoba na liście (idx == 0) => brak "Previous", dostępny "Next".
    next = User.objects.filter(pk=ordered_pks[idx - 1]).first() if idx > 0 else None
    prev = User.objects.filter(pk=ordered_pks[idx + 1]).first() if 0 <= idx < len(ordered_pks) - 1 else None
    sort_param = f'sort={requested_sort}' if requested_sort != default_sort else ''

    candidate_deletion_request = getattr(candidate_user, 'deletion_request', None)

    return render(
        request,
        'obywatele/szczegoly.html',
        {
            'b': candidate_profile,
            'd': citizen_profile,
            'wr': required_reputation(),
            'rate': r1,
            'p': polecajacy,
            'prev': prev,
            'next': next,
            'active': obj.is_active,
            'email_confirmed': email_confirmed,
            'form_completion_percent': form_completion_percent,
            'ratings_positive': ratings_positive,
            'ratings_neutral': ratings_neutral,
            'ratings_negative': ratings_negative,
            'candidate_deletion_request': candidate_deletion_request,
            'sort_param': sort_param,
        },
    )


@login_required
def candidate_edit(request: HttpRequest, pk: int):
    candidate_user = get_object_or_404(User, pk=pk, is_active=False)
    candidate_profile = get_object_or_404(Uzytkownik, uid=candidate_user)

    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=candidate_profile)
        if form.is_valid():
            candidate_user.first_name = form.cleaned_data.get('first_name') or candidate_user.first_name
            candidate_user.last_name = form.cleaned_data.get('last_name') or candidate_user.last_name
            candidate_user.save(update_fields=['first_name', 'last_name'])
            form.save()
            success(request, _('Candidate profile has been updated.'))
            return redirect('obywatele:poczekalnia_szczegoly', pk=pk)
        else:
            error(request, _('Please correct the highlighted errors.'))
    else:
        form = ProfileForm(instance=candidate_profile, initial={'first_name': candidate_user.first_name, 'last_name': candidate_user.last_name})

    return render(request, 'obywatele/candidate_edit.html', {'form': form, 'candidate_user': candidate_user, 'candidate_profile': candidate_profile})


@receiver(user_signed_up)
def DeactivateNewUser(sender, **kwargs):
    user = kwargs.get('user')
    if not user:
        log.error('Missing user in DeactivateNewUser signal')
        return

    if user.is_active:
        user.is_active = False
        user.save(update_fields=['is_active'])


@receiver(email_confirmed)
def set_onboarding_email_confirmed(sender, request, email_address, **kwargs):
    user = email_address.user
    profile = user.uzytkownik

    if profile.onboarding_status == Uzytkownik.OnboardingStatus.EMAIL_ENTERED:
        profile.onboarding_status = Uzytkownik.OnboardingStatus.EMAIL_CONFIRMED
        profile.save()

        messages.success(request, _('You have confirmed %(email)s.') % {'email': email_address.email})

        # Send onboarding email with link to form
        onboarding_token = signer.sign(str(user.id))
        query_params = urlencode({'token': onboarding_token})
        onboarding_url = request.build_absolute_uri(reverse('obywatele:onboarding_details') + f'?{query_params}')

        subject = _('Fill out your onboarding form')
        body = _('Your email has been confirmed.\n\nPlease fill out your onboarding form here: %(link)s') % {'link': onboarding_url}
        send_mail(subject, body, s.DEFAULT_FROM_EMAIL, [email_address.email], fail_silently=False)


@require_POST
def set_user_language(request: HttpRequest):
    """Set the interface language.

    Open to anonymous users so the language can be chosen on the landing page and
    kept through the whole signup/onboarding flow (which runs unauthenticated).
    Persistence relies on the django_language cookie, read by LocaleMiddleware on
    every request. For authenticated users we additionally store the choice in
    their profile so it survives a cookie reset.
    """
    lang = request.POST.get('language', '').strip()
    next_url = request.POST.get('next', '/')
    # Endpoint is reachable by anonymous users, so guard against open redirects.
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        next_url = '/'

    # Only authenticated users have a profile to persist the choice to.
    profile = request.user.uzytkownik if request.user.is_authenticated else None

    if lang and check_for_language(lang):
        if profile:
            profile.language = lang
            profile.save(update_fields=['language'])
        translation.activate(lang)
        response = redirect(next_url)
        response.set_cookie(
            s.LANGUAGE_COOKIE_NAME,
            lang,
            max_age=s.LANGUAGE_COOKIE_AGE,
            path=s.LANGUAGE_COOKIE_PATH,
            domain=s.LANGUAGE_COOKIE_DOMAIN,
            secure=s.LANGUAGE_COOKIE_SECURE,
            httponly=s.LANGUAGE_COOKIE_HTTPONLY,
            samesite=s.LANGUAGE_COOKIE_SAMESITE,
        )
    elif lang == '':
        # Reset to auto-detect
        if profile:
            profile.language = ''
            profile.save(update_fields=['language'])
        response = redirect(next_url)
        response.delete_cookie(s.LANGUAGE_COOKIE_NAME, path=s.LANGUAGE_COOKIE_PATH)
    else:
        response = redirect(next_url)

    return response


@login_required
def citizen_czaty(request: HttpRequest, pk: int):
    target_user = get_object_or_404(User, pk=pk)
    rows = get_user_public_message_rows(target_user, request.user)
    template = 'obywatele/_citizen_czaty_partial.html' if request.headers.get('X-Requested-With') == 'XMLHttpRequest' else 'obywatele/citizen_czaty.html'
    return render(request, template, {'target_user': target_user, 'rows': rows, 'is_own': request.user.pk == pk})


@login_required
def citizen_zadania(request: HttpRequest, pk: int):
    target_user = get_object_or_404(User, pk=pk)
    tasks = get_user_tasks(target_user)
    template = 'obywatele/_citizen_zadania_partial.html' if request.headers.get('X-Requested-With') == 'XMLHttpRequest' else 'obywatele/citizen_zadania.html'
    return render(request, template, {'target_user': target_user, 'tasks': tasks, 'is_own': request.user.pk == pk})


@login_required
def citizen_aktywnosc(request: HttpRequest, pk: int):
    target_user = get_object_or_404(User, pk=pk)
    target_profile = get_object_or_404(Uzytkownik, uid=target_user)
    items = get_citizen_activity(target_user, target_profile)
    template = 'obywatele/_citizen_aktywnosc_partial.html' if request.headers.get('X-Requested-With') == 'XMLHttpRequest' else 'obywatele/citizen_aktywnosc.html'
    return render(request, template, {'target_user': target_user, 'items': items, 'is_own': request.user.pk == pk})


@login_required
def citizen_zalozono(request: HttpRequest, pk: int):
    target_user = get_object_or_404(User, pk=pk)
    items = get_citizen_created_items(target_user)
    template = 'obywatele/_citizen_zalozono_partial.html' if request.headers.get('X-Requested-With') == 'XMLHttpRequest' else 'obywatele/citizen_zalozono.html'
    return render(request, template, {'target_user': target_user, 'items': items, 'is_own': request.user.pk == pk})


@login_required
@require_POST
def request_deletion(request: HttpRequest):
    user = request.user
    if hasattr(user, 'deletion_request'):
        error(request, _('A deletion request already exists for your account.'))
        return redirect('obywatele:my_profile')

    reason = request.POST.get('reason', '').strip()
    scheduled = timezone.now() + timedelta(days=30)
    DeletionRequest.objects.create(user=user, scheduled_for=scheduled, reason=reason)
    log.info(f'User {user.username} (id={user.id}) requested account deletion, scheduled for {scheduled.date()}, reason: {reason[:100] if reason else "not provided"}')
    success(request, _('Your account deletion has been scheduled. Your data will be permanently removed in 30 days. You can cancel this request at any time before then.'))
    return redirect('obywatele:my_profile')


@login_required
@require_POST
def cancel_deletion(request: HttpRequest):
    user = request.user
    try:
        dr = user.deletion_request
        dr.delete()
        log.info(f'User {user.username} (id={user.id}) cancelled their account deletion request')
        success(request, _('Your account deletion request has been cancelled.'))
    except DeletionRequest.DoesNotExist:
        error(request, _('No active deletion request found.'))
    return redirect('obywatele:my_profile')
