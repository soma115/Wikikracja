import logging
import threading
from collections import defaultdict
from time import sleep

from django.conf import settings as s
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.utils import timezone, translation
from django.utils.translation import gettext_lazy as _

from chat.models import Message, Room
from glosowania.models import Decyzja
from obywatele.models import Uzytkownik
from tasks.models import Task
from zzz.utils import build_site_url, get_site_domain

log = logging.getLogger(__name__)


class Command(BaseCommand):
    args = ''
    help = 'Send chat messages through email'

    def handle(self, *args, **options):
        translation.activate(s.LANGUAGE_CODE)

        HOST = get_site_domain()

        # Queue all emails to send in background thread sequentially
        email_queue = []

        def SendEmail(recipients: list[str], message: str) -> None:

            subject = _("{HOST} New messages on chat").format(HOST=HOST)
            header = _("New messages on {HOST}/chat").format(HOST=HOST)
            footer2 = _("Go to chat to do so {HOST}/chat").format(HOST=HOST)
            footer1 = _("You can disable those messages by unchecking bell icon next to chat room name.")
            footer3 = _("You can manage your email notifications here: {url}").format(url=build_site_url('/obywatele/settings/'))

            for recipient in recipients:
                email_queue.append({
                    'recipient': recipient,
                    'subject': subject,
                    'body': header + "\n\n" + message + "\n\n" + footer1 + "\n" + footer2 + "\n" + footer3,
                })

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

            # Group rooms by type
            rooms_by_type = {
                'tasks': [],
                'votings': [],
                'public': [],
                'private': []
            }

            for room in messages_by_room.keys():
                if Task.objects.filter(chat_room=room).exists():
                    rooms_by_type['tasks'].append(room)
                elif Decyzja.objects.filter(chat_room=room).exists():
                    rooms_by_type['votings'].append(room)
                elif room.public:
                    rooms_by_type['public'].append(room)
                else:
                    rooms_by_type['private'].append(room)

            b: list[str] = []

            # Process each category
            if rooms_by_type['votings']:
                b.append("## Głosowania")
                b.append("")
                for room in rooms_by_type['votings']:
                    room_link = f"{HOST}/chat#room_id={room.id}"
                    room_name = room.displayed_name(u.uid)
                    b.append(f"- {room_name}: {room_link}")
                b.append("")

            if rooms_by_type['tasks']:
                b.append("## Zadania")
                b.append("")
                for room in rooms_by_type['tasks']:
                    room_link = f"{HOST}/chat#room_id={room.id}"
                    room_name = room.displayed_name(u.uid)
                    b.append(f"- {room_name}: {room_link}")
                b.append("")

            if rooms_by_type['public']:
                b.append("## Pokoje publiczne")
                b.append("")
                for room in rooms_by_type['public']:
                    room_link = f"{HOST}/chat#room_id={room.id}"
                    room_name = room.displayed_name(u.uid)
                    b.append(f"- {room_name}: {room_link}")
                b.append("")

            if rooms_by_type['private']:
                b.append("## Pokoje prywatne")
                b.append("")
                for room in rooms_by_type['private']:
                    room_link = f"{HOST}/chat#room_id={room.id}"
                    room_name = room.displayed_name(u.uid)
                    b.append(f"- {room_name}: {room_link}")
                b.append("")

            body = "\n".join(b)
            if body:
                SendEmail([
                    u.uid.email,
                ], body)
            u.last_broadcast = timezone.now()
            u.save()

        # Send all queued emails in background thread sequentially
        def _send_queued_emails():
            for email_data in email_queue:
                email_message = EmailMessage(
                    subject=email_data['subject'],
                    body=email_data['body'],
                    from_email=str(s.DEFAULT_FROM_EMAIL),
                    to=[email_data['recipient']],
                )
                log.info(f'Sending email to {email_data["recipient"]}; subject: {email_message.subject}')
                try:
                    sleep(s.EMAIL_SEND_DELAY_SECONDS)
                    email_message.send(fail_silently=False)
                    log.info(f'Email sent successfully to {email_data["recipient"]}; subject: {email_message.subject}')
                except Exception as e:
                    log.error(f'Failed to send email to {email_data["recipient"]}; subject: {email_message.subject}; error: {e}', exc_info=True)

        if email_queue:
            send_thread = threading.Thread(target=_send_queued_emails)
            send_thread.start()

