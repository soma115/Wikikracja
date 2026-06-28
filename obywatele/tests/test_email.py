"""
Tests for email sending:
  1. New person sign-up → SendEmailToAll sends one email per active user.
  2. chat_messages command → each user receives exactly one email per run.

EMAIL_SEND_DELAY_SECONDS is overridden to 0 so threads finish quickly.
EMAIL_BACKEND is overridden to locmem so no real SMTP is used.
"""
# Standard library imports
import secrets
import threading
from datetime import datetime

from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils.timezone import make_aware, now

from chat.models import Message, Room
from obywatele.forms import SendEmailToAll
from obywatele.models import Uzytkownik

FAST_EMAIL_SETTINGS = {
    'EMAIL_BACKEND': 'django.core.mail.backends.locmem.EmailBackend',
    'EMAIL_SEND_DELAY_SECONDS': 0,
}


def _drain_threads():
    main = threading.main_thread()
    for t in threading.enumerate():
        if t is main or not t.daemon:
            continue
        t.join(timeout=5)


def make_active_user(username, email):
    password = secrets.token_urlsafe(16)
    user = User.objects.create_user(username=username, email=email, password=password)
    user.is_active = True
    user.save()
    return user


@override_settings(**FAST_EMAIL_SETTINGS)
class NewPersonEmailTest(TransactionTestCase):
    # TransactionTestCase (zamiast TestCase) — SendEmailToAll spawnuje wątek tła
    # który czyta DB; transakcja TestCase byłaby niewidoczna dla tego wątku
    # (table lock). TransactionTestCase commit'uje dane → wątek je widzi.
    def _call_send_email_to_all(self, subject, message):
        SendEmailToAll(subject, message)
        _drain_threads()

    def test_send_email_to_all_sends_exactly_one_email(self):
        make_active_user('citizen1', 'citizen1@example.com')
        make_active_user('citizen2', 'citizen2@example.com')
        self._call_send_email_to_all('Test subject', 'Test message')
        self.assertEqual(len(mail.outbox), 2,
            f"Expected 2 emails (one per user), got {len(mail.outbox)}. Double-sending would produce 4 or more.")

    def test_send_email_to_all_sends_exactly_one_email_on_repeated_calls(self):
        make_active_user('citizen3', 'citizen3@example.com')
        self._call_send_email_to_all('First event', 'First message')
        self._call_send_email_to_all('Second event', 'Second message')
        self.assertEqual(len(mail.outbox), 2,
            f"Expected 2 emails (one per event), got {len(mail.outbox)}. Each event sends 1 email per user.")

    def test_no_email_when_no_active_users(self):
        self._call_send_email_to_all('Empty subject', 'Empty message')
        self.assertEqual(len(mail.outbox), 0,
            f"Expected 0 emails with no active users, got {len(mail.outbox)}.")


@override_settings(**FAST_EMAIL_SETTINGS)
class ChatMessagesEmailTest(TestCase):
    def setUp(self):
        self.sender = make_active_user('sender', 'sender@example.com')
        self.recipient = make_active_user('recipient', 'recipient@example.com')
        self.room = Room.objects.create(title='Test Room', public=True)
        self.room.allowed.set([self.sender, self.recipient])
        past = make_aware(datetime(1900, 1, 1))
        Uzytkownik.objects.filter(uid=self.recipient).update(last_broadcast=past)
        Uzytkownik.objects.filter(uid=self.sender).update(last_broadcast=past)

    def _run_chat_messages_command(self):
        call_command('chat_messages')
        _drain_threads()

    def _add_message(self, text='Hello'):
        return Message.objects.create(sender=self.sender, room=self.room, text=text)

    def test_one_email_per_user_with_new_messages(self):
        self._add_message('Hello there')
        self._run_chat_messages_command()
        recipient_emails = [e for e in mail.outbox if self.recipient.email in e.to]
        self.assertEqual(len(recipient_emails), 1,
            f"Expected 1 email for recipient, got {len(recipient_emails)}.")

    def test_no_email_when_no_new_messages(self):
        Uzytkownik.objects.filter(uid=self.recipient).update(last_broadcast=now())
        self._run_chat_messages_command()
        recipient_emails = [e for e in mail.outbox if self.recipient.email in e.to]
        self.assertEqual(len(recipient_emails), 0,
            f"Expected 0 emails when no new messages, got {len(recipient_emails)}.")

    def test_one_email_aggregates_multiple_messages(self):
        self._add_message('Message 1')
        self._add_message('Message 2')
        self._add_message('Message 3')
        self._run_chat_messages_command()
        recipient_emails = [e for e in mail.outbox if self.recipient.email in e.to]
        self.assertEqual(len(recipient_emails), 1,
            f"Expected 1 aggregated email, got {len(recipient_emails)}.")

    def test_running_command_twice_sends_two_emails(self):
        self._add_message('First batch')
        self._run_chat_messages_command()
        past = make_aware(datetime(1900, 1, 1))
        Uzytkownik.objects.filter(uid=self.recipient).update(last_broadcast=past)
        self._add_message('Second batch')
        self._run_chat_messages_command()
        recipient_emails = [e for e in mail.outbox if self.recipient.email in e.to]
        self.assertEqual(len(recipient_emails), 2,
            f"Expected 2 emails (one per run), got {len(recipient_emails)}.")

    def test_muted_room_no_email(self):
        self.room.muted_by.add(self.recipient)
        self._add_message('Should not be notified')
        self._run_chat_messages_command()
        recipient_emails = [e for e in mail.outbox if self.recipient.email in e.to]
        self.assertEqual(len(recipient_emails), 0,
            f"Expected 0 emails for muted room, got {len(recipient_emails)}.")

    def test_sender_does_not_receive_own_message_email(self):
        self._add_message('My own message')
        self._run_chat_messages_command()
        sender_emails = [e for e in mail.outbox if self.sender.email in e.to]
        self.assertEqual(len(sender_emails), 0,
            f"Sender should not receive email for own message, got {len(sender_emails)}.")
