import logging
import random
import re
from datetime import datetime, timedelta

from django.db import transaction
from django.utils.translation import gettext_lazy as _

from chat.models import Room
from glosowania.models import Decyzja, KtoJuzGlosowal, VoteCode
from glosowania.vote_buffer import pop_all_pending_votes
from site_settings.models import SiteParameters
from site_settings.params import apply_brand_mark, apply_parameters
from zzz.email import send_notification_email_to_active_users
from zzz.management.base_command import TranslatedCommand
from zzz.notifications import build_notification, send_notification_to_all_sync

log = logging.getLogger(__name__)


class Command(TranslatedCommand):
    help = 'Send chat messages through email'

    def run(self, *args, **options):
        HOST = self.host

        threads = []
        pending_emails = []
        pending_notifications = []

        def zliczaj_wszystko():

            log.info('zliczaj_wszystko() run ok')

            proposition = Decyzja.Status.PROPOSITION
            discussion = Decyzja.Status.DISCUSSION
            referendum = Decyzja.Status.REFERENDUM
            rejected = Decyzja.Status.REJECTED
            approved = Decyzja.Status.APPROVED

            dzisiaj = datetime.today().date()
            sp = SiteParameters.get()

            approved_for = _("is approved for referendum")
            became = _('became abiding law today')
            click = _('Click here to read it')
            ends_at = _('Referendum ends at')
            feel_free = _('Feel free to improve it and send it again')
            gathered = _("gathered required amount of signatures and will be voted from")
            in_effect = _('is in efect from today')
            last_day = _('Last day to vote on proposal no.')
            last_day_reminder = _('This is the last day to vote!')
            not_gathered = _('did not gathered required amount of signatures')
            prop_number = _('Proposal no.')
            ref_num = _('Referendum on proposal no.')
            was_rejected = _('was rejected')
            rejected_in = _('was rejected in referendum.')
            starting_now = _('is starting now')
            time_to_vote = _('It is time to vote on proposal no.')
            to = _('to')
            _was = _('was approved')
            was_removed = _('and was removed from queue')
            buffer_lost_subject = _('technical failure - restarting')
            buffer_lost_reason = _('votes cast so far were lost due to a technical problem with vote storage')
            buffer_lost_no_leak = _('no results were ever shown and no one could see how anyone voted')
            buffer_lost_codes_void = _('all verification codes issued so far are void')
            buffer_lost_restart = _('voting restarts today for a full new period')
            buffer_lost_please_vote = _('please vote again')

            def process(i):
                # FROM PROPOSITION TO DISCUSSION
                if i.status == proposition:
                    if not i.is_author_signed:
                        log.info(f"Proposition {i.id} is still a draft because the author has not signed it yet.")
                    elif i.ile_osob_podpisalo >= sp.wymaganych_podpisow:
                        # Check if 2 days have passed since last modification
                        if i.data_ostatniej_modyfikacji:
                            days_since_modification = (dzisiaj - i.data_ostatniej_modyfikacji.date()).days
                            if days_since_modification < 2:
                                log.info(f"Proposition {i.id} has enough signatures but waiting for 2-day freeze period (modified {days_since_modification} days ago).")
                                return

                        i.status = discussion
                        i.path = str(i.path) + " -> " + _("Signed") + " -> " + _("Discussion")
                        i.data_zebrania_podpisow = dzisiaj
                        i.data_referendum_start = i.data_zebrania_podpisow + timedelta(days=sp.dyskusja)
                        i.data_referendum_stop = i.data_referendum_start + timedelta(days=sp.czas_trwania_referendum)
                        i.save()
                        details_url = f"http://{HOST}/glosowania/details/{i.id}"
                        pending_emails.append(
                            (f"{prop_number} {i.id} {approved_for}", f"{prop_number} {i.id} '{i.title}' {gathered} {i.data_referendum_start} {to} {i.data_referendum_stop}\n{click}: {details_url}")
                        )
                        pending_notifications.append(build_notification(f"{prop_number} {i.id} {approved_for}", i.title, details_url, f"vote-{i.id}", vote_id=i.id))
                        log.info(f"Proposition {i.id} changed status from PROPOSITION to DISCUSSION.")
                        return
                    # FROM PROPOSITION TO REJECTED
                    # NOTE: This block is a sibling of the if/elif above (both nested
                    # inside "if i.status == proposition").
                    # Reached when: (a) author has NOT signed (if not is_author_signed), OR
                    # (b) author signed but not enough signatures gathered (elif was False).
                    # When elif was True and proposal moved to discussion - the return above skips this block.
                    if i.data_powstania + timedelta(days=sp.czas_na_zebranie_podpisow) <= dzisiaj:
                        i.status = rejected
                        i.path = str(i.path) + " -> " + _("Not enough signatures")
                        i.save()
                        details_url = f"http://{HOST}/glosowania/details/{i.id}"
                        pending_emails.append((f"{prop_number} {i.id} {not_gathered}", f"{prop_number} {i.id} '{i.title}' {not_gathered} {was_removed}. {feel_free}\n{click}: {details_url}"))
                        pending_notifications.append(build_notification(f"{prop_number} {i.id} {not_gathered}", i.title, details_url, f"vote-{i.id}", vote_id=i.id))
                        log.info(f"Proposition {i.id} changed status from PROPOSITION to NOT_INTRESTED.")
                    return

                if i.status == discussion and i.data_referendum_start <= dzisiaj:
                    i.status = referendum
                    i.path = i.path + " -> " + _("Referendum")
                    i.save()
                    details_url = f"http://{HOST}/glosowania/details/{i.id}"
                    pending_emails.append((f"{ref_num} {i.id} {starting_now}", f"{time_to_vote} {i.id} '{i.title}'\n{ends_at} {i.data_referendum_stop}\n{click}: {details_url}"))
                    pending_notifications.append(build_notification(f"{ref_num} {i.id} {starting_now}", i.title, details_url, f"vote-{i.id}", vote_id=i.id))
                    log.info(f"Proposition {i.id} changed status from DISCUSSION to REFERENDUM.")
                    return

                # LAST DAY OF REFERENDUM REMINDER
                if i.status == referendum and i.data_referendum_stop == dzisiaj:
                    details_url = f"http://{HOST}/glosowania/details/{i.id}"
                    pending_emails.append((f"{last_day} {i.id}", f"{last_day_reminder}\n{ref_num} {i.id} '{i.title}' {ends_at} {i.data_referendum_stop}\n{click}: {details_url}"))
                    pending_notifications.append(build_notification(f"{last_day} {i.id}", i.title, details_url, f"vote-{i.id}", vote_id=i.id))
                    log.info(f"Last day reminder sent for referendum {i.id}.")
                    return

                # FROM REFERENDUM TO APPROVED OR REJECTED
                if i.status == referendum and i.data_referendum_stop < dzisiaj:
                    # Reveal the votes now: pop everything buffered outside the
                    # database for this referendum, shuffle it so on-disk order
                    # says nothing about voting order, and only now write the
                    # verification codes and tally them. Until this point za/przeciw
                    # stay at 0, i.e. no one (not even someone with DB access) could
                    # see a running tally while the referendum was open.
                    pending_votes = pop_all_pending_votes(i.id)
                    expected_voters = KtoJuzGlosowal.objects.filter(projekt=i).count()

                    if expected_voters != len(pending_votes):
                        # Votes were lost from the buffer (e.g. the vote storage
                        # service restarted) before the referendum closed. Do NOT
                        # tally a partial/wrong result - wipe the who-voted list
                        # and restart the voting window from scratch instead.
                        log.error(
                            f"Referendum {i.id}: vote buffer had {len(pending_votes)} entries "
                            f"but {expected_voters} users are recorded as having voted. "
                            "Votes were lost (e.g. vote storage restart) - restarting the referendum from scratch."
                        )
                        KtoJuzGlosowal.objects.filter(projekt=i).delete()
                        i.data_referendum_start = dzisiaj
                        i.data_referendum_stop = dzisiaj + timedelta(days=sp.czas_trwania_referendum)
                        i.referendum_restart_count += 1
                        i.save()
                        details_url = f"http://{HOST}/glosowania/details/{i.id}"
                        pending_emails.append(
                            (
                                f"{ref_num} {i.id}: {buffer_lost_subject}",
                                f"{ref_num} {i.id} '{i.title}': {buffer_lost_subject}.\n"
                                f"{buffer_lost_reason}. {buffer_lost_no_leak}. {buffer_lost_codes_void}. "
                                f"{buffer_lost_restart}. {buffer_lost_please_vote}.\n"
                                f"{ends_at} {i.data_referendum_stop}\n{click}: {details_url}",
                            )
                        )
                        pending_notifications.append(build_notification(f"{ref_num} {i.id}: {buffer_lost_subject}", i.title, details_url, f"vote-{i.id}", vote_id=i.id))
                        return

                    random.SystemRandom().shuffle(pending_votes)
                    VoteCode.objects.bulk_create([VoteCode(project=i, code=v['code'], vote=v['vote']) for v in pending_votes])
                    i.za = sum(1 for v in pending_votes if v['vote'])
                    i.przeciw = sum(1 for v in pending_votes if not v['vote'])

                    if i.za > i.przeciw:
                        i.status = approved
                        i.path = i.path + " -> " + _("Approved")
                        # Apply system parameter changes if this is a parameter referendum
                        if i.proposed_parameters:
                            try:
                                apply_parameters(i.proposed_parameters)
                                log.info(f"Applied system parameters from referendum {i.id}: {i.proposed_parameters}")
                            except Exception as e:
                                log.error(f"Failed to apply parameters from referendum {i.id}: {e}")
                        # Apply logo change if this referendum proposed a new logo
                        if i.proposed_brand_mark:
                            try:
                                apply_brand_mark(i.proposed_brand_mark)
                                log.info(f"Applied logo from referendum {i.id}")
                            except Exception as e:
                                log.error(f"Failed to apply logo from referendum {i.id}: {e}")
                        # Reject bills
                        if i.znosi:
                            separated = re.split(r'\W+', i.znosi)
                            for z in separated:
                                abolish = Decyzja.objects.select_for_update().get(pk=str(z))
                                abolish.status = rejected
                                abolish.save()
                                log.info(f"Proposition {z} was rejected in {i.id}")
                        i.save()
                        details_url = f"http://{HOST}/glosowania/details/{i.id}"
                        pending_emails.append((f"{prop_number} {i.id} {in_effect}", f"{prop_number} {i.id} '{i.title}' {became}\n{click}: {details_url}"))
                        pending_notifications.append(build_notification(f"{prop_number} {i.id} {in_effect}", i.title, details_url, f"vote-{i.id}", vote_id=i.id))
                        log.info("Proposition {i.id} changed status from REFERENDUM to VALID.")
                    else:
                        i.status = rejected
                        i.path = i.path + " -> " + _("Rejected")
                        i.save()
                        details_url = f"http://{HOST}/glosowania/details/{i.id}"
                        pending_emails.append((f"{prop_number} {i.id} {was_rejected}", f"{prop_number} {i.id} '{i.title}' {rejected_in}\n{feel_free}\n{click}: {details_url}"))
                        pending_notifications.append(build_notification(f"{prop_number} {i.id} {was_rejected}", i.title, details_url, f"vote-{i.id}", vote_id=i.id))
                        log.info("Proposition {i.id} changed status from REFERENDUM to REJECTED.")

            # Each decision is processed in its own transaction so that a
            # failure handling one of them (e.g. the vote storage being
            # unreachable) cannot roll back unrelated status changes made to
            # other decisions earlier in the same run.
            decyzja_ids = list(Decyzja.objects.filter(status__in=[proposition, discussion, referendum]).values_list('id', flat=True))

            for decyzja_id in decyzja_ids:
                try:
                    with transaction.atomic():
                        i = Decyzja.objects.select_for_update().get(pk=decyzja_id)
                        process(i)
                except Exception:
                    log.error(f"Failed to process decyzja {decyzja_id} this run; it will be retried next time.", exc_info=True)

            for subject, message in pending_emails:
                SendEmail(subject, message)

        def SendEmail(subject, message):
            # to: all active users, one email per recipient with delay between each
            # subject: Custom
            # message: Custom
            t = send_notification_email_to_active_users(subject, message, notification_type='glosowania', log_prefix='glosowania: ', raise_on_error=False, daemon=False)
            log.warning(f"subject: {subject} \n message: {message}")
            threads.append(t)

        zliczaj_wszystko()

        for notif in pending_notifications:
            send_notification_to_all_sync(notif, ws_type='vote.notification', notification_type='glosowania')

        # Create all 1to1 rooms
        Room.create_all_one2one_rooms()

        for t in threads:
            t.join()

        log.info('vote.py counted all votes')
