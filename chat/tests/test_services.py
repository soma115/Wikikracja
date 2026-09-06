import json
import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import firebase_admin
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from firebase_admin import messaging as firebase_messaging
from push_notifications.models import GCMDevice

from chat.exceptions import ClientError
from chat.models import Message, Room
from chat.permissions import _room_permission_checkers, get_room_permission_checker, register_room_permission_checker
from chat.services import CHAT_UNREAD_CACHE_KEY, ChatRepository, can_user_post_in_room, extract_mentions, get_avatar_url, get_unread_count_for_user, get_unseen_room_ids, send_message
from chat.tests.utils import make_user
from core import signals
from core.notifications import build_notification, send_fcm_to_all_sync, send_fcm_to_user_sync
from tasks.tests.utils import make_task


class _UserWithoutProfile:
    """Stub user where accessing .uzytkownik raises (simulating broken/missing relation)."""

    @property
    def uzytkownik(self):
        raise AttributeError("no related profile")


class GetAvatarUrlTest(TestCase):
    def test_returns_none_when_avatar_not_uploaded(self):
        # post_save signal auto-creates Uzytkownik; avatar field is empty by default.
        user = make_user("noavatar")
        self.assertIsNone(get_avatar_url(user))

    def test_returns_none_when_user_is_none(self):
        self.assertIsNone(get_avatar_url(None))

    def test_returns_none_when_uzytkownik_attribute_raises(self):
        self.assertIsNone(get_avatar_url(_UserWithoutProfile()))

    def test_returns_url_when_avatar_uploaded(self):
        user = make_user("withavatar")
        user.uzytkownik.avatar = SimpleUploadedFile("test.png", b"fake-bytes", content_type="image/png")
        user.uzytkownik.save()
        result = get_avatar_url(user)
        self.assertIsNotNone(result)
        self.assertIn("avatars/", result)
        self.assertTrue(result.endswith(".png"))


class ExtractMentionsTest(TestCase):
    def test_extracts_single_mention(self):
        self.assertEqual(extract_mentions("Cześć @alice"), {"alice"})

    def test_extracts_multiple_mentions(self):
        self.assertEqual(extract_mentions("@alice i @bob"), {"alice", "bob"})

    def test_returns_empty_when_no_mentions(self):
        self.assertEqual(extract_mentions("Bez wzmianki"), set())

    def test_ignores_email_like_text(self):
        self.assertEqual(extract_mentions("alice@example.com"), set())

    def test_handles_br_tags(self):
        self.assertEqual(extract_mentions("Cześć<br>@alice"), {"alice"})

    def test_deduplicates_mentions(self):
        self.assertEqual(extract_mentions("@alice @alice"), {"alice"})


class CanPostInRoomTest(TestCase):
    def setUp(self):
        self.enterContext(patch("core.notifications._dispatch_notification"))
        self.coordinator = make_user("coordinator")
        self.helper = make_user("helper")
        self.approved = make_user("approved")
        self.stranger = make_user("stranger")
        self.task = make_task(created_by=self.coordinator, assigned_to=self.coordinator, team_mode=True)
        from tasks.models import TaskVote

        TaskVote.objects.create(task=self.task, user=self.helper, value=1)
        TaskVote.objects.create(task=self.task, user=self.approved, value=1)
        self.task.approve_helper(self.approved)

        self.room = self.task.chat_room

    def test_task_checker_registration_is_idempotent(self):
        checker = type(self.task).can_user_post_in_chat_room
        register_room_permission_checker('tasks', checker)
        register_room_permission_checker('tasks', type(self.task).can_user_post_in_chat_room)
        self.assertEqual(get_room_permission_checker('tasks'), checker)

    async def test_coordinator_can_post(self):
        repo = ChatRepository(self.coordinator)
        self.assertTrue(await repo.can_post_in_room(self.room))

    async def test_approved_helper_can_post(self):
        repo = ChatRepository(self.approved)
        self.assertTrue(await repo.can_post_in_room(self.room))

    async def test_unapproved_helper_cannot_post(self):
        repo = ChatRepository(self.helper)
        self.assertFalse(await repo.can_post_in_room(self.room))

    async def test_stranger_cannot_post(self):
        repo = ChatRepository(self.stranger)
        self.assertFalse(await repo.can_post_in_room(self.room))

    async def test_old_task_allows_everyone(self):
        old_task = await database_sync_to_async(make_task)(created_by=self.coordinator, team_mode=False)
        repo = ChatRepository(self.stranger)
        self.assertTrue(await repo.can_post_in_room(old_task.chat_room))

    async def test_unauthenticated_users_cannot_post_in_public_or_private_rooms(self):
        for public in (True, False):
            self.room.public = public
            for user in (None, AnonymousUser()):
                with self.subTest(public=public, user=user):
                    self.assertFalse(await ChatRepository(user).can_post_in_room(self.room))

    async def test_private_membership_allows_unapproved_helper(self):
        self.room.public = False
        await database_sync_to_async(self.room.allowed.set)([self.helper])
        self.assertTrue(await ChatRepository(self.helper).can_post_in_room(self.room))

    async def test_private_nonmember_coordinator_cannot_post(self):
        self.room.public = False
        await database_sync_to_async(self.room.allowed.set)([self.helper])
        self.assertFalse(await ChatRepository(self.coordinator).can_post_in_room(self.room))

    async def test_plain_public_room_allows_nonmember(self):
        room = await database_sync_to_async(Room.objects.create)(title="Plain public room", public=True)
        self.assertTrue(await ChatRepository(self.stranger).can_post_in_room(room))

    async def test_public_task_room_without_object_id_allows_nonmember(self):
        room = await database_sync_to_async(Room.objects.create)(title="Task without object ID", public=True, source_app="tasks")
        self.assertTrue(await ChatRepository(self.stranger).can_post_in_room(room))

    async def test_public_task_room_with_missing_task_currently_allows_nonmember(self):
        room = await database_sync_to_async(Room.objects.create)(title="Missing task", public=True, source_app="tasks", source_object_id=self.task.pk + 1)
        self.assertTrue(await ChatRepository(self.stranger).can_post_in_room(room))

    async def test_assigned_coordinator_not_creator_controls_team_posting(self):
        task = await database_sync_to_async(make_task)(created_by=self.stranger, assigned_to=self.coordinator, team_mode=True)
        self.assertTrue(await ChatRepository(self.coordinator).can_post_in_room(task.chat_room))
        self.assertFalse(await ChatRepository(self.stranger).can_post_in_room(task.chat_room))

    async def test_creator_of_unassigned_team_task_cannot_post(self):
        task = await database_sync_to_async(make_task)(created_by=self.stranger, team_mode=True)
        self.assertFalse(await ChatRepository(self.stranger).can_post_in_room(task.chat_room))

    async def test_revoked_helper_approval_removes_posting_permission(self):
        repo = ChatRepository(self.approved)
        self.assertTrue(await repo.can_post_in_room(self.room))
        await database_sync_to_async(self.task.remove_helper)(self.approved)
        self.assertTrue(await database_sync_to_async(self.task.is_user_helper)(self.approved))
        self.assertFalse(await repo.can_post_in_room(self.room))


class RoomPermissionRegistryTest(TestCase):
    def setUp(self):
        self.enterContext(patch.dict(_room_permission_checkers))
        self.enterContext(patch("core.notifications._dispatch_notification"))
        self.notify = self.enterContext(patch("chat.services._dispatch_message_notifications", new_callable=AsyncMock))
        self.user = make_user("permission-user")
        self.room = Room.objects.create(title="Custom source room", public=True, source_app="test_source", source_object_id=1)
        self.checker = MagicMock(return_value=True)
        self.channel_layer = SimpleNamespace(group_send=AsyncMock())

    def test_unknown_source_defaults_to_public_access(self):
        self.assertIsNone(get_room_permission_checker(self.room.source_app))
        self.assertTrue(can_user_post_in_room(self.room, self.user))

    def test_registration_is_idempotent_but_rejects_conflicting_checker(self):
        register_room_permission_checker(self.room.source_app, self.checker)
        register_room_permission_checker(self.room.source_app, self.checker)
        self.assertIs(get_room_permission_checker(self.room.source_app), self.checker)
        with self.assertRaises(ValueError):
            register_room_permission_checker(self.room.source_app, MagicMock())
        self.assertIs(get_room_permission_checker(self.room.source_app), self.checker)

    def test_registration_rejects_noncallable_checker(self):
        for checker in (None, True):
            with self.subTest(checker=checker), self.assertRaises(TypeError):
                register_room_permission_checker(self.room.source_app, checker)
        self.assertIsNone(get_room_permission_checker(self.room.source_app))

    def test_custom_source_controls_public_posting(self):
        register_room_permission_checker(self.room.source_app, self.checker)
        for allowed in (True, False):
            with self.subTest(allowed=allowed):
                self.checker.reset_mock()
                self.checker.return_value = allowed
                self.assertIs(can_user_post_in_room(self.room, self.user), allowed)
                self.checker.assert_called_once_with(self.room, self.user)

    def test_anonymous_private_and_missing_id_guards_skip_checker(self):
        self.checker.side_effect = AssertionError("Checker must not run before room guards")
        register_room_permission_checker(self.room.source_app, self.checker)
        for public in (True, False):
            self.room.public = public
            for user in (None, AnonymousUser()):
                with self.subTest(public=public, user=user):
                    self.assertFalse(can_user_post_in_room(self.room, user))
        self.assertFalse(can_user_post_in_room(self.room, self.user))
        self.room.allowed.add(self.user)
        self.assertTrue(can_user_post_in_room(self.room, self.user))
        self.room.public = True
        for object_id in (None, 0):
            with self.subTest(object_id=object_id):
                self.room.source_object_id = object_id
                self.assertTrue(can_user_post_in_room(self.room, self.user))
        self.checker.assert_not_called()

    def test_checker_errors_propagate(self):
        self.checker.side_effect = RuntimeError("Permission lookup failed")
        register_room_permission_checker(self.room.source_app, self.checker)
        with self.assertRaisesRegex(RuntimeError, "Permission lookup failed"):
            can_user_post_in_room(self.room, self.user)
        self.checker.assert_called_once_with(self.room, self.user)

    async def test_send_message_rejects_denied_or_failed_checker_without_side_effects(self):
        register_room_permission_checker(self.room.source_app, self.checker)
        for error in (None, RuntimeError("Permission lookup failed")):
            with self.subTest(error=error):
                self.checker.reset_mock()
                self.checker.return_value = False
                self.checker.side_effect = error
                with self.assertRaises(RuntimeError if error else ClientError) as raised:
                    await send_message(self.room, "Rejected", sender=self.user, anonymous=False, channel_layer=self.channel_layer, online_registry=MagicMock())
                if error is None:
                    self.assertEqual(raised.exception.code, "ACCESS_DENIED")
                else:
                    self.assertIs(raised.exception, error)
                self.checker.assert_called_once_with(self.room, self.user)
                self.assertFalse(await database_sync_to_async(self.room.messages.exists)())
                self.channel_layer.group_send.assert_not_awaited()
                self.notify.assert_not_awaited()

    async def test_send_message_saves_and_broadcasts_when_checker_allows(self):
        register_room_permission_checker(self.room.source_app, self.checker)
        message = await send_message(self.room, "Permitted", sender=self.user, anonymous=False, channel_layer=self.channel_layer, online_registry=MagicMock())
        self.checker.assert_called_once_with(self.room, self.user)
        self.assertEqual(await database_sync_to_async(self.room.messages.count)(), 1)
        self.assertEqual(message.sender_id, self.user.id)
        self.channel_layer.group_send.assert_awaited_once()
        group, event = self.channel_layer.group_send.await_args.args
        self.assertEqual(group, self.room.group_name)
        self.assertEqual(event["message_id"], message.pk)
        self.assertEqual(event["message"], "Permitted")
        self.notify.assert_awaited_once()

    async def test_system_sender_bypasses_checker_and_still_sends(self):
        self.checker.side_effect = AssertionError("System messages bypass user permissions")
        register_room_permission_checker(self.room.source_app, self.checker)
        message = await send_message(self.room, "System update", sender=None, anonymous=False, channel_layer=self.channel_layer, online_registry=MagicMock())
        self.checker.assert_not_called()
        self.assertEqual(await database_sync_to_async(self.room.messages.count)(), 1)
        self.assertIsNone(message.sender_id)
        self.channel_layer.group_send.assert_awaited_once()
        self.notify.assert_awaited_once()


class GetUnseenRoomIdsTest(TestCase):
    def setUp(self):
        self.enterContext(patch("core.notifications._dispatch_notification"))
        self.user = make_user("unseen-user")
        self.other = make_user("other-unseen-user")
        for user in (self.user, self.other):
            user.seen_rooms.set(Room.objects.all())
            key = CHAT_UNREAD_CACHE_KEY.format(user_id=user.id)
            cache.delete(key)
            self.addCleanup(cache.delete, key)

    def make_message_room(self, title, *, member=True, **kwargs):
        room = Room.objects.create(title=title, **kwargs)
        Message.objects.create(room=room, sender=self.user, text="Unread message")
        if member:
            room.allowed.add(self.user, self.other)
        return room

    def test_unseen_ids_include_archived_inbox_and_unlisted_rooms_but_not_empty_or_seen(self):
        regular = self.make_message_room("Regular")
        archived = self.make_message_room("Archived")
        archived.archived = True
        archived.save(update_fields=["archived"])
        inbox = self.make_message_room("Test inbox", is_inbox=True)
        unlisted = self.make_message_room("Unlisted public", member=False)
        private = self.make_message_room("Unlisted private", member=False, public=False)
        seen = self.make_message_room("Seen")
        seen.seen_by.add(self.user)
        empty = Room.objects.create(title="Empty")
        empty.allowed.add(self.user)
        self.assertEqual(get_unseen_room_ids(self.user), {regular.id, archived.id, inbox.id, unlisted.id, private.id})
        self.assertEqual(get_unread_count_for_user(self.user), 1)

    def test_seen_flags_are_independent_per_user_and_recomputed(self):
        first = self.make_message_room("First")
        second = self.make_message_room("Second")
        first.seen_by.add(self.user)
        second.seen_by.add(self.other)
        self.assertEqual(get_unseen_room_ids(self.user), {second.id})
        self.assertEqual(get_unseen_room_ids(self.other), {first.id})
        first.seen_by.remove(self.user)
        second.seen_by.add(self.user)
        self.assertEqual(get_unseen_room_ids(self.user), {first.id})
        self.assertEqual(get_unseen_room_ids(self.other), {first.id})

    def test_unseen_ids_ignore_stale_unread_count_cache(self):
        room = self.make_message_room("Cached count")
        key = CHAT_UNREAD_CACHE_KEY.format(user_id=self.user.id)
        cache.set(key, 777)
        self.assertEqual(get_unread_count_for_user(self.user), 777)
        self.assertEqual(get_unseen_room_ids(self.user), {room.id})
        room.seen_by.add(self.user)
        self.assertEqual(get_unseen_room_ids(self.user), set())
        self.assertEqual(cache.get(key), 777)

    def test_query_count_stays_two_for_multiple_rooms_and_messages(self):
        room_ids = set()
        for index in range(5):
            room = self.make_message_room(f"Batch room {index}")
            Message.objects.create(room=room, sender=self.other, text="Second unread message")
            room_ids.add(room.id)
            with self.subTest(room_count=len(room_ids)), self.assertNumQueries(2):
                self.assertEqual(get_unseen_room_ids(self.user), room_ids)


class DomainNotificationSignalTest(TestCase):
    def setUp(self):
        self.dispatch = self.enterContext(patch("core.notifications._dispatch_notification"))
        self.user = SimpleNamespace(id=41, username="citizen", email="citizen@example.com")

    def assert_single_dispatch(self, notification_type, ws_type, tag, **entity_ids):
        self.dispatch.assert_called_once()
        args, kwargs = self.dispatch.call_args
        self.assertEqual(len(args), 4)
        self.assertEqual(args[3], tag)
        self.assertEqual(kwargs["notification_type"], notification_type)
        self.assertEqual(kwargs["ws_type"], ws_type)
        for key, value in entity_ids.items():
            self.assertEqual(kwargs[key], value)
        for key in ("candidate", "proposed_by", "user", "task", "post", "event", "survey", "decyzja", "transition"):
            self.assertNotIn(key, kwargs)
        return args, kwargs

    def test_fresh_django_startup_registers_notification_dispatch(self):
        code = dedent("""
            import os
            import sys
            from contextlib import ExitStack
            from importlib import import_module
            from types import ModuleType
            from unittest.mock import MagicMock, patch

            def assert_vote_dispatch():
                assert "core.notifications" in sys.modules, "Startup did not import notification receivers"
                assert "zzz.notifications" not in sys.modules, "Legacy notification module was imported"
                from core.signals import vote_state_changed

                with patch("core.notifications._dispatch_notification") as dispatch:
                    vote_state_changed.send(
                        sender=None, title="Startup vote", body="Vote body",
                        click_action="https://example.com/vote/46", tag="vote-46", vote_id=46,
                    )
                    dispatch.assert_called_once()
                    assert dispatch.call_args.args == ("Startup vote", "Vote body", "https://example.com/vote/46", "vote-46")
                    assert dispatch.call_args.kwargs["notification_type"] == "glosowania"
                    assert dispatch.call_args.kwargs["ws_type"] == "vote.notification"
                    assert dispatch.call_args.kwargs["vote_id"] == 46

            ready_modules = []
            scheduler_checks = []

            def start_scheduler():
                assert ready_modules == [sys.modules.get("core.notifications")], "Scheduler ran before CoreConfig.ready"
                assert_vote_dispatch()
                scheduler_checks.append(True)

            scheduler = ModuleType("zzz.scheduler")
            scheduler.start_scheduler = MagicMock(side_effect=start_scheduler)
            with ExitStack() as stack:
                stack.enter_context(patch("dotenv.load_dotenv", return_value=False))
                stack.enter_context(patch.dict(sys.modules, {"zzz.scheduler": scheduler}))
                guards = [
                    stack.enter_context(patch(target, side_effect=AssertionError(target + " must not run during startup")))
                    for target in (
                        "django.db.backends.base.base.BaseDatabaseWrapper.cursor",
                        "django.core.mail.send_mail", "firebase_admin.initialize_app", "firebase_admin.messaging.send_each",
                    )
                ]
                import django
                from django.conf import settings
                from django.contrib.auth import get_user_model
                from core.apps import CoreConfig

                settings.DATABASES["default"]["NAME"] = ":memory:"
                guards.append(stack.enter_context(patch("threading.Thread.start", side_effect=AssertionError("Startup must not start threads"))))
                original_ready = CoreConfig.ready

                def tracked_ready(config):
                    assert "core.notifications" not in sys.modules, "Receivers were imported before CoreConfig.ready"
                    original_ready(config)
                    assert get_user_model() is django.apps.apps.get_model(settings.AUTH_USER_MODEL)
                    ready_modules.append(sys.modules["core.notifications"])

                with patch.object(CoreConfig, "ready", autospec=True, side_effect=tracked_ready) as ready:
                    django.setup()
                    ready.assert_called_once_with(django.apps.apps.get_app_config("core"))

                app_labels = list(django.apps.apps.app_configs)
                assert app_labels.index("core") < app_labels.index("zzz")
                expected_starts = int(os.environ["SCHEDULER_ENABLED"] == "true" or os.environ["RUN_MAIN"] == "true")
                assert scheduler.start_scheduler.call_count == expected_starts
                assert len(scheduler_checks) == expected_starts, "Scheduler swallowed a startup assertion"
                assert "chat.permissions" in sys.modules, "Startup did not import room permission registry"
                task_model = django.apps.apps.get_model("tasks", "Task")
                checker = sys.modules["chat.permissions"].get_room_permission_checker("tasks")
                assert checker == task_model.can_user_post_in_chat_room, "Startup did not register task room permissions"
                assert_vote_dispatch()

                canonical = sys.modules["core.notifications"]
                assert ready_modules == [canonical]
                for _ in range(2):
                    django.apps.apps.get_app_config("core").ready()
                    for module_name in ("chat.services", "chat.push_api", "chat.consumers", "core.notifications"):
                        import_module(module_name)
                    assert sys.modules["core.notifications"] is canonical
                    assert_vote_dispatch()
                assert sys.modules["zzz.scheduler"] is scheduler
                assert scheduler.start_scheduler.call_count == expected_starts
                for guard in guards:
                    guard.assert_not_called()
            """)
        env = os.environ | {
            "DJANGO_SETTINGS_MODULE": "zzz.test_settings",
            "SCHEDULER_ENABLED": "false",
            "RUN_MAIN": "false",
            "SECRET_KEY": "isolated-notification-startup-test-key",
            "DEBUG": "false",
            "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
            "FIREBASE_CERT_PATH": "",
            "GOOGLE_APPLICATION_CREDENTIALS": "",
            "FIREBASE_CERT_JSON": "",
            "FIREBASE_CERT_BASE64": "",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        for scheduler_enabled, run_main in (("false", "false"), ("true", "false"), ("false", "true"), ("true", "true")):
            with self.subTest(scheduler_enabled=scheduler_enabled, run_main=run_main):
                case_env = env | {"SCHEDULER_ENABLED": scheduler_enabled, "RUN_MAIN": run_main}
                result = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[2], env=case_env, capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, f"Startup subprocess failed:\n{result.stdout}\n{result.stderr}")

    def test_domain_signals_dispatch_once_after_startup(self):
        task = SimpleNamespace(id=42, title="Task title")
        post = SimpleNamespace(id=43, title="Post title", author=self.user)
        event = SimpleNamespace(id=44, title="Event title", link="https://example.com/event")
        survey = SimpleNamespace(id=45, title="Survey title")
        cases = (
            ("citizen signup", signals.citizen_proposed, {"candidate": self.user}, "obywatele", "citizen.notification", "citizen-signup-41", {"citizen_id": 41}),
            ("citizen proposed", signals.citizen_proposed, {"candidate": self.user, "proposed_by": self.user}, "obywatele", "citizen.notification", "citizen-41", {"citizen_id": 41}),
            ("task", signals.task_created, {"task": task, "url": "https://example.com/task"}, "task", "task.notification", "task-42", {"task_id": 42}),
            ("new post", signals.important_post_published, {"post": post, "url": "https://example.com/post", "created": True}, "post", "post.notification", "post-43", {"post_id": 43}),
            ("updated post", signals.important_post_published, {"post": post, "url": "https://example.com/post", "created": False}, "post", "post.notification", "post-43", {"post_id": 43}),
            ("event", signals.event_starting, {"event": event, "body": "Starting now"}, "events", "event.notification", "event-44", {"event_id": 44}),
            ("survey", signals.survey_created, {"survey": survey, "url": "https://example.com/survey"}, "survey", "survey.notification", "survey-45", {"survey_id": 45}),
        )
        for name, signal, payload, notification_type, ws_type, tag, entity_ids in cases:
            with self.subTest(signal=name):
                self.dispatch.reset_mock()
                signal.send(sender=type(self), **payload)
                self.assert_single_dispatch(notification_type, ws_type, tag, **entity_ids)

    def test_vote_signals_preserve_payload_strings_without_domain_objects(self):
        decision = SimpleNamespace(id=46)
        payload = {"title": "Vote <b>title</b>", "body": "Vote body\nSecond line", "click_action": "https://example.com/vote/46?state=started", "tag": "vote-46-started"}
        for name, signal in (("vote_started", signals.vote_started), ("vote_state_changed", signals.vote_state_changed)):
            with self.subTest(signal=name):
                self.dispatch.reset_mock()
                signal.send(sender=type(self), decyzja=decision, transition="started", vote_id=decision.id, **payload)
                args, kwargs = self.assert_single_dispatch("glosowania", "vote.notification", payload["tag"], vote_id=decision.id)
                self.assertEqual(args, (payload["title"], payload["body"], payload["click_action"], payload["tag"]))
                self.assertFalse(kwargs["in_thread"])
                self.assertFalse(kwargs["daemon"])
                self.assertFalse(kwargs["send_email"])

    def test_citizen_accepted_dispatches_one_welcome_email(self):
        with patch("chat.signals.Room.create_all_one2one_rooms") as create_rooms:
            signals.citizen_accepted.send(sender=type(self), user=self.user, recipient_subject="Welcome", recipient_body="Welcome body")
        create_rooms.assert_called_once_with()
        args, kwargs = self.assert_single_dispatch("obywatele", "citizen.notification", "citizen-accepted-41")
        self.assertEqual(args, ("Welcome", "Welcome body", "", "citizen-accepted-41"))
        self.assertEqual(kwargs["recipient_email"], self.user.email)
        self.assertTrue(kwargs["send_email"])
        self.assertFalse(kwargs["send_push"])
        self.assertFalse(kwargs["send_websocket"])

    def test_citizen_accepted_without_email_content_does_not_dispatch(self):
        with patch("chat.signals.Room.create_all_one2one_rooms"):
            signals.citizen_accepted.send(sender=type(self), user=self.user)
        self.dispatch.assert_not_called()

    def test_citizen_blocked_dispatches_one_broadcast(self):
        signals.citizen_blocked.send(
            sender=type(self), user=self.user, title="Citizen blocked", body="Blocked body", click_action="https://example.com/citizens", tag="citizen-blocked-41", was_previously_active=False
        )
        args, kwargs = self.assert_single_dispatch("obywatele", "citizen.notification", "citizen-blocked-41", citizen_id=self.user.id)
        self.assertEqual(args, ("Citizen blocked", "Blocked body", "https://example.com/citizens", "citizen-blocked-41"))
        self.assertNotIn("was_previously_active", kwargs)
        self.assertTrue(kwargs["send_push"])
        self.assertTrue(kwargs["send_websocket"])
        self.assertFalse(kwargs["send_email"])

    def test_citizen_blocked_dispatches_one_personal_email(self):
        signals.citizen_blocked.send(sender=type(self), user=self.user, recipient_subject="Membership ended", recipient_body="Personal body", was_previously_active=False)
        args, kwargs = self.assert_single_dispatch("obywatele", "citizen.notification", "citizen-blocked-41")
        self.assertEqual(args, ("Membership ended", "Personal body", "", "citizen-blocked-41"))
        self.assertEqual(kwargs["recipient_email"], self.user.email)
        self.assertTrue(kwargs["send_email"])
        self.assertFalse(kwargs["send_push"])
        self.assertFalse(kwargs["send_websocket"])


class VoteNotificationPayloadTest(TestCase):
    def test_vote_notification_payload_is_json_serializable(self):
        for signal in (signals.vote_started, signals.vote_state_changed):
            with self.subTest(signal=signal), patch('core.notifications.send_notification_to_all_sync') as deliver:
                signal.send(sender=type(self), title='Vote title', body='Vote body', click_action='https://example.com/vote/1', tag='vote-1', vote_id=1)

                deliver.assert_called_once()
                payload = deliver.call_args.args[0]
                self.assertEqual(json.loads(json.dumps(payload)), payload)
                self.assertNotIn('signal', payload)
                self.assertEqual(payload['vote_id'], 1)


class TaskRoomVoterNamesTest(TestCase):
    """W pokojach zadań głosy na wiadomościach są jawne — payload zawiera nicki głosujących."""

    def setUp(self):
        self.enterContext(patch("core.notifications._dispatch_notification"))
        self.author = make_user("msgauthor")
        self.voter_up = make_user("upvoter")
        self.voter_down = make_user("downvoter")
        self.task = make_task(created_by=self.author)
        self.room = self.task.chat_room
        self.msg = Message.objects.create(room=self.room, sender=self.author, text="Propozycja")
        self.msg.reactions = {'upvotes': [self.voter_up.id], 'downvotes': [self.voter_down.id]}
        self.msg.save(update_fields=['reactions'])
        self.repo = ChatRepository(self.author)

    async def test_batch_includes_voter_names_when_include_voters(self):
        batch = await self.repo.get_recent_messages_batch(self.room.id, self.author.id, include_voters=True)
        msg = batch['messages'][-1]
        self.assertEqual(msg['upvoters'], ['upvoter'])
        self.assertEqual(msg['downvoters'], ['downvoter'])

    async def test_batch_omits_voter_names_by_default(self):
        batch = await self.repo.get_recent_messages_batch(self.room.id, self.author.id)
        msg = batch['messages'][-1]
        self.assertNotIn('upvoters', msg)
        self.assertNotIn('downvoters', msg)

    async def test_get_vote_voters_returns_names(self):
        voters = await self.repo.get_vote_voters(self.msg.id)
        self.assertEqual(voters, {'upvoters': ['upvoter'], 'downvoters': ['downvoter']})

    async def test_get_vote_voters_missing_message(self):
        voters = await self.repo.get_vote_voters(999999)
        self.assertEqual(voters, {'upvoters': [], 'downvoters': []})

    async def test_voter_lists_skip_deleted_users(self):
        await database_sync_to_async(self.voter_up.delete)()
        voters = await self.repo.get_vote_voters(self.msg.id)
        self.assertEqual(voters, {'upvoters': [], 'downvoters': ['downvoter']})


class SendPushNotificationSyncTest(TestCase):
    """Regression tests for the FCM message built by send_push_notification_sync."""

    def setUp(self):
        self.user = make_user("pushuser")
        self.repo = ChatRepository(self.user)

        self.mock_queryset = MagicMock()
        self.mock_queryset.exists.return_value = True
        self.mock_queryset.send_message.return_value = MagicMock(success_count=1, responses=[MagicMock(success=True)])

    def test_firebase_disabled_skips_user_and_broadcast_fcm(self):
        notification = {"notification_id": "disabled-fcm", "title": "Title", "body": "Body"}
        for send, args in ((send_fcm_to_user_sync, (self.user, notification)), (send_fcm_to_all_sync, (notification,))):
            with self.subTest(send=send.__name__), patch.object(firebase_admin, "_apps", {}), patch("core.notifications.GCMDevice") as devices:
                with patch.object(firebase_messaging, "send_each") as send_each, self.assertNumQueries(0):
                    self.assertEqual(send(*args, notification_type="chat"), 0)
                self.assertEqual(devices.mock_calls, [])
                send_each.assert_not_called()

    async def test_builds_full_fcm_message(self):
        """The message must contain top-level notification, data payload and webpush notification."""
        with patch("core.notifications.GCMDevice") as mock_gcm:
            mock_gcm.objects.filter.return_value = self.mock_queryset
            with patch.object(firebase_admin, "_apps", {"[DEFAULT]": MagicMock()}):
                await self.repo.send_push_notification_sync(self.user, "Room: Test", "Sender: Alice", "https://example.com/chat#room_id=1", 1, room_name="Test")

        self.assertTrue(self.mock_queryset.send_message.called)
        message = self.mock_queryset.send_message.call_args[0][0]
        self.assertIsInstance(message, firebase_messaging.Message)

        # Top-level notification lets the FCM SDK display the notification automatically.
        self.assertEqual(message.notification.title, "Room: Test")
        self.assertEqual(message.notification.body, "Sender: Alice")

        # Data payload is used by onMessage and onBackgroundMessage.
        self.assertEqual(message.data["title"], "Room: Test")
        self.assertEqual(message.data["body"], "Sender: Alice")
        self.assertEqual(message.data["room_id"], "1")
        self.assertEqual(message.data["room_name"], "Test")
        self.assertEqual(message.data["click_action"], "https://example.com/chat#room_id=1")
        self.assertIn("favicon.ico", message.data["icon"])

        # webpush.notification is needed for the killed-browser/PWA case.
        webpush_notification = message.webpush.notification
        self.assertEqual(webpush_notification.title, "Room: Test")
        self.assertEqual(webpush_notification.body, "Sender: Alice")
        self.assertEqual(webpush_notification.tag, "chat-1")
        self.assertTrue(webpush_notification.require_interaction)
        self.assertEqual(webpush_notification.data["room_id"], "1")
        self.assertEqual(webpush_notification.data["click_action"], "https://example.com/chat#room_id=1")
        self.assertIn("favicon.ico", webpush_notification.icon)
        self.assertIn("favicon.ico", webpush_notification.badge)

        # webpush.fcm_options.link handles notification click.
        self.assertEqual(message.webpush.fcm_options.link, "https://example.com/chat#room_id=1")


class FCMDeviceDeactivationTest(TestCase):
    """Regression tests for automatic deactivation of dead FCM tokens."""

    def setUp(self):
        self.user = make_user("deactivationuser")
        self.device = GCMDevice.objects.create(user=self.user, registration_id="dead_token", active=True, cloud_message_type="FCM")

    def test_unregistered_token_gets_deactivated(self):
        """django-push-notifications must mark an UnregisteredError token inactive."""
        unregistered = firebase_messaging.UnregisteredError("Token unregistered")
        response = firebase_messaging.SendResponse(None, unregistered)
        batch = firebase_messaging.BatchResponse([response])

        with patch.object(firebase_admin, "_apps", {"[DEFAULT]": MagicMock()}):
            with patch.object(firebase_messaging, "send_each", return_value=batch):
                send_fcm_to_user_sync(self.user, build_notification("Title", "Body", "https://example.com/", "tag-1"), notification_type="chat")

        self.device.refresh_from_db()
        self.assertFalse(self.device.active)


class FCMDeviceTypeFilterTest(TestCase):
    """Regression tests for per-device-type (phone/computer) push filtering."""

    def setUp(self):
        self.user = make_user("filteruser")

    def _mock_queryset(self):
        qs = MagicMock()
        qs.count.return_value = 1
        qs.send_message.return_value = MagicMock(success_count=1, responses=[MagicMock(success=True)])
        qs.exclude.return_value = qs
        return qs

    def _assert_send_called(self, mock_gcm, expected_exclude_call):
        # _migrate_legacy_gcm_devices() filters legacy GCM rows first, so the main
        # filter is the second call.
        filter_calls = [c for c in mock_gcm.objects.filter.call_args_list if c.kwargs.get("cloud_message_type") == "FCM"]
        self.assertEqual(len(filter_calls), 1)
        mock_gcm.objects.filter.assert_any_call(user=self.user, active=True, cloud_message_type="FCM")
        mock_gcm.objects.filter.return_value.exclude.assert_called_once_with(**expected_exclude_call)
        mock_gcm.objects.filter.return_value.send_message.assert_called_once()

    def test_phone_disabled_excludes_mobile_and_tablet(self):
        self.user.uzytkownik.push_phone_enabled = False
        self.user.uzytkownik.save()

        with patch("core.notifications.GCMDevice") as mock_gcm:
            mock_gcm.objects.filter.return_value = self._mock_queryset()
            with patch.object(firebase_admin, "_apps", {"[DEFAULT]": MagicMock()}):
                send_fcm_to_user_sync(self.user, build_notification("Title", "Body", "https://example.com/", "tag-1"), notification_type="chat")
        self._assert_send_called(mock_gcm, {"name__in": ("mobile", "tablet")})

    def test_computer_disabled_excludes_desktop(self):
        self.user.uzytkownik.push_computer_enabled = False
        self.user.uzytkownik.save()

        with patch("core.notifications.GCMDevice") as mock_gcm:
            mock_gcm.objects.filter.return_value = self._mock_queryset()
            with patch.object(firebase_admin, "_apps", {"[DEFAULT]": MagicMock()}):
                send_fcm_to_user_sync(self.user, build_notification("Title", "Body", "https://example.com/", "tag-1"), notification_type="chat")
        self._assert_send_called(mock_gcm, {"name": "desktop"})

    def test_both_disabled_excludes_both_device_types(self):
        self.user.uzytkownik.push_phone_enabled = False
        self.user.uzytkownik.push_computer_enabled = False
        self.user.uzytkownik.save()

        with patch("core.notifications.GCMDevice") as mock_gcm:
            qs = self._mock_queryset()
            mock_gcm.objects.filter.return_value = qs
            with patch.object(firebase_admin, "_apps", {"[DEFAULT]": MagicMock()}):
                send_fcm_to_user_sync(self.user, build_notification("Title", "Body", "https://example.com/", "tag-1"), notification_type="chat")
        mock_gcm.objects.filter.assert_any_call(user=self.user, active=True, cloud_message_type="FCM")
        self.assertEqual(qs.exclude.call_count, 2)
        qs.exclude.assert_any_call(name__in=("mobile", "tablet"))
        qs.exclude.assert_any_call(name="desktop")
        qs.send_message.assert_called_once()
