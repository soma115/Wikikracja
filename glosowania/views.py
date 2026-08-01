import difflib
import html
import logging
import random
import re
import time
from datetime import datetime

from django.conf import settings as s
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import OperationalError, transaction
from django.db.models import Count, Exists, F, OuterRef
from django.http import HttpRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _

from chat.views import get_translations as get_chat_translations
from glosowania.forms import ArgumentForm, DecyzjaForm, ParametersProposalForm
from glosowania.models import Argument, Decyzja, DecyzjaWersja, KtoJuzGlosowal, VoteCode, ZebranePodpisy
from glosowania.vote_buffer import push_pending_vote
from site_settings.models import SiteParameters
from site_settings.params import describe_changes, specs_by_category
from zzz.email import send_notification_email_to_active_users
from zzz.notifications import build_notification, send_notification_to_all_in_thread
from zzz.utils import build_site_url

log = logging.getLogger(__name__)


@login_required
def dodaj(request: HttpRequest):
    # Dodaj nową propozycję przepisu:
    # nowy = DecyzjaForm(request.POST or None)
    if request.method == 'POST':
        form = DecyzjaForm(request.POST)
        if form.is_valid():
            form = form.save(commit=False)
            form.author = request.user
            form.data_powstania = datetime.today()
            # form.ile_osob_podpisalo += 1
            form.status = Decyzja.Status.PROPOSITION
            form.path = _("Proposition")
            form.save()
            # signed = ZebranePodpisy.objects.create(projekt=form, podpis_uzytkownika = request.user)

            log.info(f"New proposal {form.id} added by {form.author}")
            message = _("New proposal has been saved.")
            messages.success(request, (message))

            log.info(f'EMAIL_DIAG trigger=new_law_proposal source=glosowania.views.dodaj actor_user_id={request.user.id} actor_username={request.user.username} decision_id={form.id} subject={_("New law proposal")}')
            SendEmail(_('New law proposal'), _('{user} added new law proposal: "{title}"\nYou can read it here: {url}').format(user=request.user.username.capitalize(), title=form.title, url=build_site_url(f'/glosowania/details/{form.id}')))

            notification = build_notification(
                _('New law proposal'),
                f'{request.user.username.capitalize()}: {form.title}',
                build_site_url(f'/glosowania/details/{form.id}'),
                f'vote-{form.id}',
                vote_id=form.id,
            )
            send_notification_to_all_in_thread(notification, ws_type='vote.notification', notification_type='glosowania')

            return redirect('glosowania:proposition')
        else:
            return render(request, 'glosowania/dodaj.html', {
                'form': form
            })
    else:
        form = DecyzjaForm()
    return render(request, 'glosowania/dodaj.html', {
        'form': form
    })


@login_required
def edit(request: HttpRequest, pk: int):
    try:
        decision = Decyzja.objects.get(pk=pk)
    except Decyzja.DoesNotExist:
        return redirect('glosowania:index')

    if decision.author != request.user:
        return redirect('glosowania:details', pk)

    if decision.status != Decyzja.Status.PROPOSITION:
        return redirect('glosowania:details', pk)

    # Parameter referenda use a dedicated form pre-filled with proposed values.
    if decision.proposed_parameters is not None or decision.proposed_brand_mark:
        return redirect('glosowania:parameters_edit', pk)

    if request.method == 'POST':
        form = DecyzjaForm(request.POST)
        if form.is_valid():
            next_version = decision.wersje.count() + 1
            DecyzjaWersja.objects.create(
                decyzja=decision,
                modified_by=request.user,
                version_number=next_version,
                title=decision.title,
                tresc=decision.tresc,
                kara=decision.kara,
                uzasadnienie=decision.uzasadnienie,
                znosi=decision.znosi,
            )
            decision.title = form.cleaned_data['title']
            decision.tresc = form.cleaned_data['tresc']
            decision.kara = form.cleaned_data['kara']
            decision.uzasadnienie = form.cleaned_data['uzasadnienie']
            decision.znosi = form.cleaned_data['znosi']
            decision.save()
            message = _("Saved.")
            messages.success(request, (message))

            SendEmail(_("Proposal no. {} has been modified").format(decision.id), _('{user} modified proposal: "{title}"\nYou can read new version here: {url}').format(user=request.user.username.capitalize(), title=decision.title, url=build_site_url(f'/glosowania/details/{decision.id}')))
            return redirect('glosowania:proposition')
    else:  # request.method != 'POST':
        form = DecyzjaForm(initial={
            'author': decision.author,
            'title': decision.title,
            'tresc': decision.tresc,
            'kara': decision.kara,
            'uzasadnienie': decision.uzasadnienie,
            'znosi': decision.znosi,
        })

    # log.info(f"Proposal {decision.id} modified by {request.user}") # Can't log that because it kicks in on form open (not on save)
    return render(request, 'glosowania/edit.html', {
        'form': form
    })


def generate_code():
    return ''.join([random.SystemRandom().choice('abcdefghjkmnoprstuvwxyz23456789') for i in range(5)])


@login_required
def details(request: HttpRequest, pk: int):
    # Pokaż szczegóły przepisu

    # Handle POST requests first (sign, withdraw, vote)
    if request.POST.get('sign'):
        with transaction.atomic():
            try:
                nowy_projekt = Decyzja.objects.select_for_update().get(pk=pk)
            except Decyzja.DoesNotExist:
                return redirect('glosowania:index')
            osoba_podpisujaca = request.user
            __, created = ZebranePodpisy.objects.get_or_create(
                projekt=nowy_projekt,
                podpis_uzytkownika=osoba_podpisujaca,
            )
            if created:
                Decyzja.objects.filter(pk=pk).update(ile_osob_podpisalo=F('ile_osob_podpisalo') + 1)
        message = _('You signed this motion for a referendum.')
        messages.success(request, (message))
        return redirect('glosowania:details', pk)

    if request.POST.get('withdraw'):
        with transaction.atomic():
            try:
                nowy_projekt = Decyzja.objects.select_for_update().get(pk=pk)
            except Decyzja.DoesNotExist:
                return redirect('glosowania:index')
            osoba_podpisujaca = request.user
            deleted, __ = ZebranePodpisy.objects.filter(
                projekt=nowy_projekt,
                podpis_uzytkownika=osoba_podpisujaca,
            ).delete()
            if deleted:
                Decyzja.objects.filter(pk=pk).update(ile_osob_podpisalo=F('ile_osob_podpisalo') - 1)
        message = _('Not signed.')
        messages.success(request, (message))
        return redirect('glosowania:details', pk)

    if request.POST.get('tak'):
        with transaction.atomic():
            try:
                nowy_projekt = Decyzja.objects.select_for_update().get(pk=pk)
            except Decyzja.DoesNotExist:
                return redirect('glosowania:index')
            osoba_glosujaca = request.user
            already_voted = KtoJuzGlosowal.objects.filter(
                projekt=nowy_projekt,
                ktory_uzytkownik_juz_zaglosowal=osoba_glosujaca,
            ).exists()
            if already_voted:
                return redirect('glosowania:details', pk)
            glos = KtoJuzGlosowal(projekt=nowy_projekt, ktory_uzytkownik_juz_zaglosowal=osoba_glosujaca)
            glos.save()
            code = generate_code()
            # The vote's content is queued outside the SQL database (see
            # glosowania.vote_buffer) instead of being written to VoteCode
            # here, so it isn't created in the same instant/order as the
            # KtoJuzGlosowal row above. It is shuffled into VoteCode - and
            # counted into za/przeciw - only once the referendum closes
            # (glosowania.management.commands.vote).
            push_pending_vote(nowy_projekt.id, code, True)

        message1 = str(_('Your vote has been saved. You voted Yes.'))
        messages.success(request, (message1), extra_tags='persist')

        message2 = _('Your verification code is: %(code)s') % {
            'code': code
        }
        messages.error(request, (message2), extra_tags='persist')

        message3 = str(_('Write down your code or create screenshot to verify it when the referendum is over. This code will be presented just once and will be not related to you.'))
        messages.info(request, (message3), extra_tags='persist')

        return redirect('glosowania:details', pk)

    if request.POST.get('nie'):
        with transaction.atomic():
            try:
                nowy_projekt = Decyzja.objects.select_for_update().get(pk=pk)
            except Decyzja.DoesNotExist:
                return redirect('glosowania:index')
            osoba_glosujaca = request.user
            already_voted = KtoJuzGlosowal.objects.filter(
                projekt=nowy_projekt,
                ktory_uzytkownik_juz_zaglosowal=osoba_glosujaca,
            ).exists()
            if already_voted:
                return redirect('glosowania:details', pk)
            glos = KtoJuzGlosowal(projekt=nowy_projekt, ktory_uzytkownik_juz_zaglosowal=osoba_glosujaca)
            glos.save()
            code = generate_code()
            # See the 'tak' branch above for why this isn't a VoteCode.objects.create() here.
            push_pending_vote(nowy_projekt.id, code, False)

        message1 = str(_('Your vote has been saved. You voted No.'))
        messages.success(request, (message1), extra_tags='persist')

        message2 = _('Your verification code is: %(code)s') % {
            'code': code
        }
        messages.error(request, (message2), extra_tags='persist')

        message3 = str(_('Write down your code or create screenshot to verify it when the referendum is over. This code will be presented just once and will be not related to you.'))
        messages.info(request, (message3), extra_tags='persist')

        return redirect('glosowania:details', pk)

    # GET request - fetch details with retry logic for database lock errors
    max_retries = 3
    retry_delay = 0.5

    for attempt in range(max_retries):
        try:
            szczegoly = get_object_or_404(Decyzja.objects.select_related('chat_room'), pk=pk)
            break
        except OperationalError as e:
            if 'database is locked' in str(e) and attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            raise

    # check if already signed and voted in single query
    signed = ZebranePodpisy.objects.filter(projekt=pk, podpis_uzytkownika=request.user).exists()
    voted = KtoJuzGlosowal.objects.filter(projekt=pk, ktory_uzytkownik_juz_zaglosowal=request.user).exists()

    # Report
    report = VoteCode.objects.filter(project_id=pk).order_by('vote', 'code')

    # List of voters
    voters = KtoJuzGlosowal.objects.filter(projekt=pk).select_related('ktory_uzytkownik_juz_zaglosowal').order_by('ktory_uzytkownik_juz_zaglosowal__username')

    # Previous and Next - use szczegoly instead of another query
    prev = Decyzja.objects.filter(pk__lt=szczegoly.pk, status=szczegoly.status).order_by('-pk').first()
    next = Decyzja.objects.filter(pk__gt=szczegoly.pk, status=szczegoly.status).order_by('pk').first()

    # Find associated chat room using model method
    chat_room = szczegoly.get_chat_room()

    # Check if chat room has unseen messages
    chat_room_pulse_class = szczegoly.get_chat_room_pulse_class(request.user)

    # Query arguments for this decision
    arguments = Argument.objects.filter(decyzja=pk).select_related('author')

    # Custom sorting: prioritize concise arguments, then by author's argument count
    # First, get all arguments as a list to apply custom sorting
    all_arguments = list(arguments)

    # Count arguments per author for this decision
    from collections import Counter
    author_counts = Counter(arg.author_id for arg in all_arguments if arg.author_id)

    # Sort by: 1) content length (shorter first), 2) author's argument count (fewer first)
    def sort_key(arg):
        content_length = len(arg.content)
        author_arg_count = author_counts.get(arg.author_id, 0) if arg.author_id else 0
        return (content_length, author_arg_count)

    sorted_arguments = sorted(all_arguments, key=sort_key)

    # Separate into positive and negative
    positive_arguments = [arg for arg in sorted_arguments if arg.argument_type == 'FOR']
    negative_arguments = [arg for arg in sorted_arguments if arg.argument_type == 'AGAINST']

    # Create argument form for adding new arguments
    argument_form = ArgumentForm()

    return render(request, 'glosowania/szczegoly.html', {
        'id': szczegoly,
        'signed': signed,
        'voted': voted,
        'report': report,
        'voters': voters,
        'current_user': request.user,
        'state': szczegoly.get_status_display(),
        'data_referendum_stop': szczegoly.data_referendum_stop,
        'prev': prev,
        'next': next,
        'chat_room': chat_room,
        'chat_room_pulse_class': chat_room_pulse_class,
        'positive_arguments': positive_arguments,
        'negative_arguments': negative_arguments,
        'argument_form': argument_form,
        'MESSAGE_MAX_LENGTH': s.MESSAGE_MAX_LENGTH,
        'ec_translations': get_chat_translations(),
    })


@login_required
def add_argument(request: HttpRequest, pk: int):
    """Add a new argument to decision pk"""
    decyzja = get_object_or_404(Decyzja, pk=pk)

    # Block adding arguments after voting has ended
    if decyzja.voting_has_ended:
        messages.error(request, _("Arguments cannot be added after voting has ended."))
        return redirect('glosowania:details', pk)

    if request.method == 'POST':
        form = ArgumentForm(request.POST)
        if form.is_valid():
            argument = form.save(commit=False)
            argument.decyzja = decyzja
            argument.author = request.user
            argument.save()

            arg_type = argument.get_argument_type_display()
            message = _("Your {type} argument has been added.").format(type=arg_type.lower())
            messages.success(request, message)

            log.info(f"User {request.user} added {argument.argument_type} argument to decision #{pk}")
        else:
            messages.error(request, _("There was an error with your argument. Please try again."))

    return redirect('glosowania:details', pk)


@login_required
def edit_argument(request: HttpRequest, argument_id: int):
    """Edit an existing argument (only by its author)"""
    argument = get_object_or_404(Argument, pk=argument_id)

    # Check if user is the author
    if argument.author != request.user:
        messages.error(request, _("You can only edit your own arguments."))
        return redirect('glosowania:details', argument.decyzja.pk)

    # Block editing after voting has ended
    if argument.decyzja.voting_has_ended:
        messages.error(request, _("Arguments cannot be edited after voting has ended."))
        return redirect('glosowania:details', argument.decyzja.pk)

    if request.method == 'POST':
        form = ArgumentForm(request.POST, instance=argument)
        if form.is_valid():
            form.save()
            messages.success(request, _("Your argument has been updated."))
            log.info(f"User {request.user} edited argument #{argument_id}")
            return redirect('glosowania:details', argument.decyzja.pk)
    else:
        form = ArgumentForm(instance=argument)

    return render(request, 'glosowania/edit_argument.html', {
        'form': form,
        'argument': argument,
        'decyzja': argument.decyzja,
    })


@login_required
def delete_argument(request: HttpRequest, argument_id: int):
    """Delete an argument (only by its author)"""
    argument = get_object_or_404(Argument, pk=argument_id)
    decyzja_pk = argument.decyzja.pk

    # Check if user is the author
    if argument.author != request.user:
        messages.error(request, _("You can only delete your own arguments."))
        return redirect('glosowania:details', decyzja_pk)

    # Block deletion after voting has ended
    if argument.decyzja.voting_has_ended:
        messages.error(request, _("Arguments cannot be deleted after voting has ended."))
        return redirect('glosowania:details', decyzja_pk)

    if request.method == 'POST':
        log.info(f"User {request.user} deleted argument #{argument_id} from decision #{decyzja_pk}")
        argument.delete()
        messages.success(request, _("Your argument has been deleted."))
        return redirect('glosowania:details', decyzja_pk)

    return render(request, 'glosowania/delete_argument.html', {
        'argument': argument,
        'decyzja': argument.decyzja,
    })


def _strip_html(text):
    """Usuwa tagi HTML przed diffem, zachowując nowe linie z tagów blokowych"""
    if not text:
        return ''
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</?(p|div|li|h[1-6]|blockquote|tr)[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _make_diff_html(old_text, new_text):
    """Zwraca HTML z zaznaczonymi różnicami (unified diff styl inline)."""
    old_lines = _strip_html(old_text or '').splitlines(keepends=True)
    new_lines = _strip_html(new_text or '').splitlines(keepends=True)
    diff = list(difflib.ndiff(old_lines, new_lines))
    result = []
    for line in diff:
        if line.startswith('+ '):
            result.append(f'<span class="diff-add">{html.escape(line[2:].rstrip())}</span>')
        elif line.startswith('- '):
            result.append(f'<span class="diff-remove">{html.escape(line[2:].rstrip())}</span>')
        elif line.startswith('  '):
            result.append(f'<span class="diff-context">{html.escape(line[2:].rstrip())}</span>')
    return '\n'.join(result) or '—'


@login_required
def historia(request: HttpRequest, pk: int):
    decision = get_object_or_404(Decyzja, pk=pk)
    versions = list(decision.wersje.select_related('modified_by').order_by('version_number'))

    FIELDS = [
        ('title', _('Title')),
        ('tresc', _('Law text')),
        ('uzasadnienie', _('Reasoning')),
        ('kara', _('Penalty')),
        ('znosi', _('Abolishes')),
    ]

    entries = []
    for i, ver in enumerate(versions):
        if i == 0:
            prev = None
        else:
            prev = versions[i - 1]

        diffs = []
        for field, label in FIELDS:
            old_val = getattr(prev, field) if prev else ''
            new_val = getattr(ver, field) or ''
            if old_val != new_val:
                diffs.append({
                    'label': label,
                    'html': _make_diff_html(old_val, new_val),
                })

        entries.append({
            'version': ver,
            'diffs': diffs,
        })

    # Ostatnia wersja (aktualna) vs. ostatni snapshot
    if versions:
        last = versions[-1]
        current_diffs = []
        for field, label in FIELDS:
            old_val = getattr(last, field) or ''
            new_val = getattr(decision, field) or ''
            if old_val != new_val:
                current_diffs.append({
                    'label': label,
                    'html': _make_diff_html(old_val, new_val),
                })
    else:
        current_diffs = []

    return render(request, 'glosowania/historia.html', {
        'decision': decision,
        'entries': entries,
        'current_diffs': current_diffs,
    })


def SendEmail(subject: str, message: str):
    # to: all active users with voting notifications enabled (individual emails)
    # subject: Custom
    # message: Custom
    send_notification_email_to_active_users(
        subject,
        message,
        notification_type='glosowania',
        log_prefix='glosowania: ',
    )


# proposition = 1
# discussion = 2
# referendum = 3
# rejected = 4
# approved = 5


@login_required
def parameters(request: HttpRequest):
    sp = SiteParameters.get()

    # Grouped current values for display (category label -> [(spec, value), ...]).
    groups = []
    for _key, label, specs in specs_by_category():
        groups.append((label, [(spec, getattr(sp, spec.name)) for spec in specs]))

    return render(request, 'glosowania/parameters.html', {
        'signatures': sp.wymaganych_podpisow,
        'signatures_span': sp.czas_na_zebranie_podpisow,
        'queue_span': sp.dyskusja,
        'referendum_span': sp.czas_trwania_referendum,
        'parameter_groups': groups,
    })


@login_required
def parameters_propose(request: HttpRequest, pk: int = None):
    """Show a pre-filled form of all system parameters and create (or edit) a
    referendum (Decyzja) from the changed values.

    When ``pk`` is given, an existing parameter referendum is edited in place
    (a DecyzjaWersja snapshot is stored), instead of creating a new one.
    """
    decyzja = None
    if pk is not None:
        decyzja = get_object_or_404(Decyzja, pk=pk)
        # Only the author may edit, and only while it is still a proposition.
        if decyzja.author != request.user or decyzja.status != Decyzja.Status.PROPOSITION:
            return redirect('glosowania:details', pk)

    if request.method == 'POST':
        form = ParametersProposalForm(request.POST, request.FILES, decyzja=decyzja)
        if form.is_valid():
            changes = form.changed_parameters()
            new_logo = form.cleaned_data.get('brand_mark')

            # Build a human readable change list used as the referendum body.
            # NOTE: the |richtext filter only keeps b/i/u/br/a tags, so we use <br>/<b>.
            rows = describe_changes(changes)
            lines = [f'{html.escape(str(label))}: <b>{html.escape(str(old))}</b> → <b>{html.escape(str(new))}</b>'
                     for label, old, new in rows]
            keeps_logo = bool(decyzja and decyzja.proposed_brand_mark)
            if new_logo or keeps_logo:
                lines.append(f'{html.escape(str(_("Logo")))}: <b>{html.escape(str(_("new logo")))}</b>')
            tresc = str(_('Proposed change of system parameters:')) + '<br>' + '<br>'.join(lines)

            if decyzja is None:
                decyzja = Decyzja(
                    author=request.user,
                    title=str(_('System parameters change')),
                    data_powstania=datetime.today(),
                    status=Decyzja.Status.PROPOSITION,
                    path=str(_('Proposition')),
                )
            else:
                # Snapshot the current version before overwriting.
                DecyzjaWersja.objects.create(
                    decyzja=decyzja,
                    modified_by=request.user,
                    version_number=decyzja.wersje.count() + 1,
                    title=decyzja.title,
                    tresc=decyzja.tresc,
                    kara=decyzja.kara,
                    uzasadnienie=decyzja.uzasadnienie,
                    znosi=decyzja.znosi,
                )

            decyzja.tresc = tresc
            decyzja.uzasadnienie = form.cleaned_data['uzasadnienie']
            decyzja.proposed_parameters = changes
            if new_logo:
                decyzja.proposed_brand_mark = new_logo
            decyzja.save()

            if pk is None:
                log.info(f'New parameters referendum {decyzja.id} added by {request.user} changes={changes}')
                messages.success(request, _('New proposal has been saved.'))
                SendEmail(str(_('New law proposal')), str(_('{user} added new law proposal: "{title}"\nYou can read it here: {url}')).format(
                    user=request.user.username.capitalize(), title=decyzja.title, url=build_site_url(f'/glosowania/details/{decyzja.id}')))

                notification = build_notification(
                    str(_('New law proposal')),
                    f'{request.user.username.capitalize()}: {decyzja.title}',
                    build_site_url(f'/glosowania/details/{decyzja.id}'),
                    f'vote-{decyzja.id}',
                    vote_id=decyzja.id,
                )
                send_notification_to_all_in_thread(notification, ws_type='vote.notification', notification_type='glosowania')
            else:
                log.info(f'Parameters referendum {decyzja.id} edited by {request.user} changes={changes}')
                messages.success(request, _('Saved.'))
            return redirect('glosowania:proposition')
    else:
        form = ParametersProposalForm(decyzja=decyzja)

    return render(request, 'glosowania/parameters_propose.html', {
        'form': form,
        'decyzja': decyzja,
    })


def _apply_sort(queryset, sort, order='desc'):
    """Zastosuj sortowanie do querysetu Decyzja."""
    p = '' if order == 'asc' else '-'
    if sort == 'signatures':
        return queryset.order_by(f'{p}ile_osob_podpisalo', '-pk')
    elif sort == 'buzz':
        return queryset.annotate(chat_msg_count=Count('chat_room__messages', distinct=True)).order_by(f'{p}chat_msg_count', '-pk')
    else:  # 'date' — domyślne
        return queryset.order_by(f'{p}pk')


def _sort_context(request):
    sort = request.GET.get('sort', 'date')
    order = request.GET.get('order', 'desc')
    if order not in ('asc', 'desc'):
        order = 'desc'
    return sort, order


@login_required
def rejected(request: HttpRequest):
    sort, order = _sort_context(request)
    votings = _apply_sort(Decyzja.objects.filter(status=Decyzja.Status.REJECTED), sort, order)
    return render(request, 'glosowania/rejected.html', {
        'votings': votings,
        'current_sort': sort,
        'current_order': order,
    })


@login_required
def proposition(request: HttpRequest):
    sort, order = _sort_context(request)
    votings = _apply_sort(Decyzja.objects.filter(status=Decyzja.Status.PROPOSITION), sort, order)
    for voting in votings:
        voting.chat_room_pulse_class = voting.get_chat_room_pulse_class(request.user)
    return render(request, 'glosowania/proposition.html', {
        'votings': votings,
        'current_sort': sort,
        'current_order': order,
    })


@login_required
def discussion(request: HttpRequest):
    sort, order = _sort_context(request)
    author_signed = Exists(
        ZebranePodpisy.objects.filter(
            projekt=OuterRef("pk"),
            podpis_uzytkownika_id=OuterRef("author_id"),
        )
    )
    qs = _apply_sort(Decyzja.objects.filter(status=Decyzja.Status.DISCUSSION).annotate(_signed=author_signed).filter(_signed=True), sort, order)
    votings = list(qs)
    for voting in votings:
        voting.chat_room_pulse_class = voting.get_chat_room_pulse_class(request.user)
    return render(request, 'glosowania/discussion.html', {
        'votings': votings,
        'current_sort': sort,
        'current_order': order,
    })


@login_required
def referendum(request: HttpRequest):
    sort, order = _sort_context(request)
    author_signed = Exists(
        ZebranePodpisy.objects.filter(
            projekt=OuterRef("pk"),
            podpis_uzytkownika_id=OuterRef("author_id"),
        )
    )
    qs = _apply_sort(Decyzja.objects.filter(status=Decyzja.Status.REFERENDUM).annotate(_signed=author_signed).filter(_signed=True), sort, order)
    votings = list(qs)
    for voting in votings:
        voting.chat_room_pulse_class = voting.get_chat_room_pulse_class(request.user)
    return render(request, 'glosowania/referendum.html', {
        'votings': votings,
        'current_sort': sort,
        'current_order': order,
    })


@login_required
def approved(request: HttpRequest):
    sort, order = _sort_context(request)
    votings = _apply_sort(Decyzja.objects.filter(status=Decyzja.Status.APPROVED), sort, order)
    return render(request, 'glosowania/approved.html', {
        'votings': votings,
        'current_sort': sort,
        'current_order': order,
    })
