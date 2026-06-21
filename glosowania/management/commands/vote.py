import logging
import os
import re
import smtplib
import time
from datetime import datetime, timedelta

from django.conf import settings as s
from django.db import transaction
from django.contrib.auth.models import User
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.utils import translation
from django.utils.translation import gettext_lazy as _

from chat.models import Room
from glosowania.models import Decyzja
from zzz.utils import build_site_url, get_site_domain

log = logging.getLogger(__name__)


class Command(BaseCommand):
    args = ''
    help = 'Send chat messages through email'

    def handle(self, *args, **options):
        translation.activate(s.LANGUAGE_CODE)

        HOST = get_site_domain()

        def zliczaj_wszystko():

            log.info('zliczaj_wszystko() run ok')

            # POPRZEDNIO:
            # propozycja = 1
            # brak_poparcia = 2
            # w_kolejce = 3
            # referendum = 4
            # odrzucone = 5
            # zatwierdzone = 6
            # obowiazuje = 7

            # OBECNIE:
            proposition = 1
            discussion = 2
            referendum = 3
            rejected = 4
            approved = 5

            dzisiaj = datetime.today().date()

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
                        elif i.ile_osob_podpisalo >= s.WYMAGANYCH_PODPISOW:
                            # Check if 2 days have passed since last modification
                            if i.data_ostatniej_modyfikacji:
                                days_since_modification = (dzisiaj - i.data_ostatniej_modyfikacji.date()).days
                                if days_since_modification < 2:
                                    log.info(f"Proposition {i.id} has enough signatures but waiting for 2-day freeze period (modified {days_since_modification} days ago).")
                                    continue

                            i.status = discussion
                            i.path = str(i.path) + " -> " + _("Signed") + " -> " + _("Discussion")
                            i.data_zebrania_podpisow = dzisiaj
                            i.data_referendum_start = i.data_zebrania_podpisow + timedelta(days=s.DYSKUSJA)
                            i.data_referendum_stop = i.data_referendum_start + timedelta(days=s.CZAS_TRWANIA_REFERENDUM)
                            i.save()
                            details_url = f"http://{HOST}/glosowania/details/{i.id}"
                            SendEmail(f"{prop_number} {i.id} {approved_for}", f"{prop_number} {i.id} '{i.title}' {gathered} {i.data_referendum_start} {to} {i.data_referendum_stop}\n{click}: {details_url}")
                            log.info(f"Proposition {i.id} changed status from PROPOSITION to DISCUSSION.")
                            continue
                    # FROM PROPOSITION TO REJECTED
                    # NOTE: This block (indent 24) is a sibling of the if/elif above (also indent 24),
                    # inside the outer "if i.status == proposition" (indent 20).
                    # Reached when: (a) author has NOT signed (if not is_author_signed), OR
                    # (b) author signed but not enough signatures gathered (elif was False).
                    # When elif was True and proposal moved to discussion — continue skips this block.
                        if i.data_powstania + timedelta(days=s.CZAS_NA_ZEBRANIE_PODPISOW) <= dzisiaj:
                            i.status = rejected
                            i.path = str(i.path) + " -> " + _("Not enough signatures")
                            i.save()
                            details_url = f"http://{HOST}/glosowania/details/{i.id}"
                            SendEmail(f"{prop_number} {i.id} {not_gathered}", f"{prop_number} {i.id} '{i.title}' {not_gathered} {was_removed}. {feel_free}\n{click}: {details_url}")
                            log.info(f"Proposition {i.id} changed status from PROPOSITION to NOT_INTRESTED.")
                            continue

                    # FROM DISCUSSION TO REFERENDUM
                    if i.status == discussion and i.data_referendum_start <= dzisiaj:
                        i.status = referendum
                        i.path = i.path + " -> " + _("Referendum")
                        i.save()
                        details_url = f"http://{HOST}/glosowania/details/{i.id}"
                        SendEmail(f"{ref_num} {i.id} {starting_now}", f"{time_to_vote} {i.id} '{i.title}'\n{ends_at} {i.data_referendum_stop}\n{click}: {details_url}")
                        log.info(f"Proposition {i.id} changed status from DISCUSSION to REFERENDUM.")
                        continue

                    # LAST DAY OF REFERENDUM REMINDER
                    if i.status == referendum and i.data_referendum_stop == dzisiaj:
                        details_url = f"http://{HOST}/glosowania/details/{i.id}"
                        SendEmail(f"{last_day} {i.id}", f"{last_day_reminder}\n{ref_num} {i.id} '{i.title}' {ends_at} {i.data_referendum_stop}\n{click}: {details_url}")
                        log.info(f"Last day reminder sent for referendum {i.id}.")
                        continue

                    # FROM REFERENDUM TO APPROVED OR REJECTED
                    if i.status == referendum and i.data_referendum_stop < dzisiaj:
                        if i.za > i.przeciw:
                            i.status = approved
                            i.path = i.path + " -> " + _("Approved")
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
                            SendEmail(f"{prop_number} {i.id} {in_effect}", f"{prop_number} {i.id} '{i.title}' {became}\n{click}: {details_url}")
                            log.info("Proposition {i.id} changed status from REFERENDUM to VALID.")
                            continue
                        else:
                            i.status = rejected
                            i.path = i.path + " -> " + _("Rejected")
                            i.save()
                            details_url = f"http://{HOST}/glosowania/details/{i.id}"
                            SendEmail(f"{prop_number} {i.id} {was_rejected}", f"{prop_number} {i.id} '{i.title}' {rejected_in}\n{feel_free}\n{click}: {details_url}")
                            log.info("Proposition {i.id} changed status from REFERENDUM to REJECTED.")
                            continue

        def SendEmail(subject, message):
            # bcc: all active users
            # subject: Custom
            # message: Custom
            translation.activate(s.LANGUAGE_CODE)

            email_footer = _("You can manage your email notifications here: {url}").format(url=build_site_url('/obywatele/settings/'))
            email_message = EmailMessage(
                from_email=str(s.DEFAULT_FROM_EMAIL),
                bcc=list(User.objects.filter(is_active=True, uzytkownik__email_notifications_glosowania=True).values_list('email', flat=True)),
                subject=f'[{HOST}] {subject}',
                body=message + "\n\n" + email_footer,
            )
            log.warning(f"subject: {subject} \n message: {message}")

            try:
                email_message.send()
            except smtplib.SMTPException as e:
                log.error(f"Failed to send email '{subject}': {e}")
            time.sleep(s.EMAIL_SEND_DELAY_SECONDS)

        zliczaj_wszystko()

        # Create all 1to1 rooms
        active_users = User.objects.filter(is_active=True)
        # i = request.user
        # i = kwargs['user']
        for i in active_users:
            for j in active_users:
                # User A will not talk to user A
                if i == j:
                    continue
                # Avoid A-B B-A because it is the same thing
                t = sorted([i.username, j.username])
                title = '-'.join(t)
                existing_room = Room.find_with_users(i, j)

                # check if room for user i and j exists, if so make sure room name is correct
                if existing_room is not None:
                    existing_room.title = title
                    existing_room.save()
                # if not - create new room (use get_or_create to handle race conditions)
                else:
                    r, created = Room.objects.get_or_create(title=title, defaults={
                        'public': False
                    })
                    if created or r.allowed.count() != 2:
                        r.allowed.set((
                            i,
                            j,
                        ))

        log.info('vote.py counted all votes')
