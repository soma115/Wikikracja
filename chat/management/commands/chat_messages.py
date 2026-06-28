import logging
import re
import threading
from collections import defaultdict
from time import sleep

from django.conf import settings as s
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.utils import timezone, translation
from django.utils.translation import gettext_lazy as _

from chat.models import Message, Room
from obywatele.models import Uzytkownik
from zzz.utils import build_site_url, get_site_domain

log = logging.getLogger(__name__)


class Command(BaseCommand):
    args = ''
    help = 'Send chat messages through email'

    def handle(self, *args, **options):
        translation.activate(s.LANGUAGE_CODE)

        HOST = get_site_domain()

        threads = []

        def SendEmail(recipients: list[str], message: str) -> None:

            subject = _("{HOST} New messages on chat").format(HOST=HOST)
            header = _("New messages on {HOST}/chat").format(HOST=HOST)
            footer1 = _("Go to chat to do so {HOST}/chat").format(HOST=HOST)
            footer2 = _("You can disable those messages by unchecking bell icon next to chat room name.")
            footer3 = _("You can manage your email notifications here: {url}").format(url=build_site_url('/obywatele/settings/'))

            # Send individual email to each recipient
            for recipient in recipients:
                email_message = EmailMessage(
                    subject=subject,
                    body=header + "\n\n" + message + "\n\n" + footer1 + "\n\n" + footer2 + "\n" + footer3,
                    from_email=str(s.DEFAULT_FROM_EMAIL),
                    to=[recipient],
                )
                log.info(f'Sending email to {recipient}; subject: {email_message.subject}')

                def _send_with_delay():
                    try:
                        sleep(s.EMAIL_SEND_DELAY_SECONDS)
                        email_message.send(fail_silently=False)
                        log.info(f'Email sent successfully to {recipient}; subject: {email_message.subject}')
                    except Exception as e:
                        log.error(f'Failed to send email to {recipient}; subject: {email_message.subject}; error: {e}', exc_info=True)

                t = threading.Thread(target=_send_with_delay)
                threads.append(t)
                t.start()

        user_list = Uzytkownik.objects.filter(uid__is_active=True, email_notifications_chat=True)
        log.info(f'chat_messages: found {user_list.count()} active users with chat notifications enabled')
        for u in user_list:
            room_allowed = Room.objects.filter(allowed=u.uid, archived=False).exclude(muted_by=u.uid)
            log.info(f'chat_messages: user={u.uid} last_broadcast={u.last_broadcast} rooms_allowed={room_allowed.count()}')
            message_list = Message.objects.filter(time__gte=u.last_broadcast, room__in=room_allowed).exclude(sender=u.uid)
            log.info(f'chat_messages: user={u.uid} new_messages={message_list.count()}')
            if not message_list:
                log.info(f'No new messages for user {u.uid}')
                continue

            # Group messages by room
            messages_by_room = defaultdict(list)
            for m in message_list.order_by('room', 'time'):
                messages_by_room[m.room].append(m)

            b: list[str] = []
            for room, messages in messages_by_room.items():
                # Add room header with name as link
                room_link = f"{HOST}/chat#room_id={room.id}"
                room_name = room.displayed_name(u.uid)
                b.append(f"## {room_name}: {room_link}")
                b.append("")

                # Add messages without date/time/room
                for m in messages:
                    log.info(f'Found messages for user {u.uid}: {m.text}')
                    if m.anonymous:
                        m.sender = None
                    plain = re.sub(r'<br\s*/?>', '\n', m.text)
                    plain = re.sub(r'<[^>]+>', '', plain)
                    b.append(f'{m.sender}: {plain}')

                b.append("")  # Empty line between rooms

            body = "\n".join(b)
            if body:
                SendEmail([
                    u.uid.email,
                ], body)
            u.last_broadcast = timezone.now()
            u.save()

        for t in threads:
            t.join()
