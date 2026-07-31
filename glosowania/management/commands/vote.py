import logging
import re
from datetime import datetime, timedelta

from django.db import transaction
from django.utils.translation import gettext_lazy as _

from chat.models import Room
from glosowania.models import Decyzja
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

            # OBECNIE:
            proposition = 1
            discussion = 2
            referendum = 3
            rejected = 4
            approved = 5

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

            with transaction.atomic():
                decyzje = Decyzja.objects.select_for_update().filter(
                    status__in=[proposition, discussion, referendum]
                )

                for i in decyzje:
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
                                    continue

                            i.status = discussion
                            i.path = str(i.path) + " -> " + _("Signed") + " -> " + _("Discussion")
                            i.data_zebrania_podpisow = dzisiaj
                            i.data_referendum_start = i.data_zebrania_podpisow + timedelta(days=sp.dyskusja)
                            i.data_referendum_stop = i.data_referendum_start + timedelta(days=sp.czas_trwania_referendum)
                            i.save()
                            details_url = f"http://{HOST}/glosowania/details/{i.id}"
                            pending_emails.append((f"{prop_number} {i.id} {approved_for}", f"{prop_number} {i.id} '{i.title}' {gathered} {i.data_referendum_start} {to} {i.data_referendum_stop}\n{click}: {details_url}"))
                            pending_notifications.append(build_notification(f"{prop_number} {i.id} {approved_for}", i.title, details_url, f"vote-{i.id}", vote_id=i.id))
                            log.info(f"Proposition {i.id} changed status from PROPOSITION to DISCUSSION.")
                            continue
                    # FROM PROPOSITION TO REJECTED
                    # NOTE: This block (indent 24) is a sibling of the if/elif above (also indent 24),
                    # inside the outer "if i.status == proposition" (indent 20).
                    # Reached when: (a) author has NOT signed (if not is_author_signed), OR
                    # (b) author signed but not enough signatures gathered (elif was False).
                    # When elif was True and proposal moved to discussion — continue skips this block.
                        if i.data_powstania + timedelta(days=sp.czas_na_zebranie_podpisow) <= dzisiaj:
                            i.status = rejected
                            i.path = str(i.path) + " -> " + _("Not enough signatures")
                            i.save()
                            details_url = f"http://{HOST}/glosowania/details/{i.id}"
                            pending_emails.append((f"{prop_number} {i.id} {not_gathered}", f"{prop_number} {i.id} '{i.title}' {not_gathered} {was_removed}. {feel_free}\n{click}: {details_url}"))
                            pending_notifications.append(build_notification(f"{prop_number} {i.id} {not_gathered}", i.title, details_url, f"vote-{i.id}", vote_id=i.id))
                            log.info(f"Proposition {i.id} changed status from PROPOSITION to NOT_INTRESTED.")
                            continue

                    if i.status == discussion and i.data_referendum_start <= dzisiaj:
                        i.status = referendum
                        i.path = i.path + " -> " + _("Referendum")
                        i.save()
                        details_url = f"http://{HOST}/glosowania/details/{i.id}"
                        pending_emails.append((f"{ref_num} {i.id} {starting_now}", f"{time_to_vote} {i.id} '{i.title}'\n{ends_at} {i.data_referendum_stop}\n{click}: {details_url}"))
                        pending_notifications.append(build_notification(f"{ref_num} {i.id} {starting_now}", i.title, details_url, f"vote-{i.id}", vote_id=i.id))
                        log.info(f"Proposition {i.id} changed status from DISCUSSION to REFERENDUM.")
                        continue

                    # LAST DAY OF REFERENDUM REMINDER
                    if i.status == referendum and i.data_referendum_stop == dzisiaj:
                        details_url = f"http://{HOST}/glosowania/details/{i.id}"
                        pending_emails.append((f"{last_day} {i.id}", f"{last_day_reminder}\n{ref_num} {i.id} '{i.title}' {ends_at} {i.data_referendum_stop}\n{click}: {details_url}"))
                        pending_notifications.append(build_notification(f"{last_day} {i.id}", i.title, details_url, f"vote-{i.id}", vote_id=i.id))
                        log.info(f"Last day reminder sent for referendum {i.id}.")
                        continue

                    # FROM REFERENDUM TO APPROVED OR REJECTED
                    if i.status == referendum and i.data_referendum_stop < dzisiaj:
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
                            continue
                        else:
                            i.status = rejected
                            i.path = i.path + " -> " + _("Rejected")
                            i.save()
                            details_url = f"http://{HOST}/glosowania/details/{i.id}"
                            pending_emails.append((f"{prop_number} {i.id} {was_rejected}", f"{prop_number} {i.id} '{i.title}' {rejected_in}\n{feel_free}\n{click}: {details_url}"))
                            pending_notifications.append(build_notification(f"{prop_number} {i.id} {was_rejected}", i.title, details_url, f"vote-{i.id}", vote_id=i.id))
                            log.info("Proposition {i.id} changed status from REFERENDUM to REJECTED.")
                            continue

            for subject, message in pending_emails:
                SendEmail(subject, message)

        def SendEmail(subject, message):
            # to: all active users, one email per recipient with delay between each
            # subject: Custom
            # message: Custom
            t = send_notification_email_to_active_users(
                subject,
                message,
                notification_type='glosowania',
                log_prefix='glosowania: ',
                raise_on_error=False,
                daemon=False,
            )
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
