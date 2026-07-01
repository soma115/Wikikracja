from django.test import TestCase

from chat.serializers import build_chat_message_payload
from chat.tests.utils import make_user


class BuildChatMessagePayloadTest(TestCase):
    def setUp(self):
        self.sender = make_user("alice")
        self.viewer = make_user("bob")
        self.base_event = {
            "type": "chat.message",
            "user_id": self.sender.id,
            "message_id": 42,
            "room_id": 1,
            "message": "hi",
            "anonymous": False,
            "new": True,
        }

    def test_payload_keeps_user_id_for_non_anonymous(self):
        payload = build_chat_message_payload(
            self.base_event,
            user=self.sender,
            vote_value=None,
            current_user=self.viewer,
        )
        self.assertEqual(payload["user_id"], self.sender.id)
        self.assertEqual(payload["username"], "alice")

    def test_payload_user_id_is_none_for_anonymous(self):
        event = {**self.base_event, "anonymous": True}
        payload = build_chat_message_payload(
            event,
            user=self.sender,
            vote_value=None,
            current_user=self.viewer,
        )
        self.assertIsNone(payload["user_id"])
        self.assertEqual(payload["username"], "Anonymous")

    def test_payload_user_id_is_none_when_user_missing(self):
        payload = build_chat_message_payload(
            self.base_event,
            user=None,
            vote_value=None,
            current_user=self.viewer,
        )
        self.assertIsNone(payload["user_id"])

    def test_system_message_has_system_username(self):
        # Wiadomości systemowe: sender=None, anonymous=False (np. rename pokoju).
        # Powinny zwracać username='System', nie None (co renderuje się jako '—:' w sidebarze).
        event = {**self.base_event, "user_id": None, "anonymous": False}
        payload = build_chat_message_payload(
            event,
            user=None,
            vote_value=None,
            current_user=self.viewer,
        )
        self.assertEqual(payload["username"], "System")
        self.assertIsNone(payload["user_id"])

    def test_your_vote_passthrough_upvote(self):
        payload = build_chat_message_payload(
            self.base_event, user=self.sender, vote_value="upvote", current_user=self.viewer,
        )
        self.assertEqual(payload["your_vote"], "upvote")

    def test_your_vote_none_when_no_vote(self):
        payload = build_chat_message_payload(
            self.base_event, user=self.sender, vote_value=None, current_user=self.viewer,
        )
        self.assertIsNone(payload["your_vote"])

    def test_reactions_dict_extracts_bulb_and_question_counts(self):
        event = {**self.base_event, "reactions": {"bulb": 3, "question": 7}}
        payload = build_chat_message_payload(
            event, user=self.sender, vote_value=None, current_user=self.viewer,
        )
        self.assertEqual(payload["bulb_count"], 3)
        self.assertEqual(payload["question_count"], 7)

    def test_reactions_non_dict_falls_back_to_event_counts(self):
        event = {**self.base_event, "reactions": None, "bulb_count": 2, "question_count": 5}
        payload = build_chat_message_payload(
            event, user=self.sender, vote_value=None, current_user=self.viewer,
        )
        self.assertEqual(payload["bulb_count"], 2)
        self.assertEqual(payload["question_count"], 5)

    def test_your_reactions_omitted_when_none(self):
        payload = build_chat_message_payload(
            self.base_event, user=self.sender, vote_value=None, current_user=self.viewer,
        )
        self.assertNotIn("your_reactions", payload)

    def test_your_reactions_included_when_list(self):
        payload = build_chat_message_payload(
            self.base_event,
            user=self.sender,
            vote_value=None,
            current_user=self.viewer,
            your_reactions=["bulb"],
        )
        self.assertEqual(payload["your_reactions"], ["bulb"])

    def test_new_forced_to_false_when_current_user_is_author(self):
        payload = build_chat_message_payload(
            self.base_event, user=self.sender, vote_value=None, current_user=self.sender,
        )
        self.assertFalse(payload["new"])

    def test_new_preserved_when_current_user_is_not_author(self):
        payload = build_chat_message_payload(
            self.base_event, user=self.sender, vote_value=None, current_user=self.viewer,
        )
        self.assertTrue(payload["new"])

    def test_own_true_when_current_user_is_author(self):
        payload = build_chat_message_payload(
            self.base_event, user=self.sender, vote_value=None, current_user=self.sender,
        )
        self.assertTrue(payload["own"])

    def test_own_false_when_current_user_is_different(self):
        payload = build_chat_message_payload(
            self.base_event, user=self.sender, vote_value=None, current_user=self.viewer,
        )
        self.assertFalse(payload["own"])

    def test_payload_passes_avatar_url_through(self):
        payload = build_chat_message_payload(
            self.base_event, user=self.sender, vote_value=None,
            current_user=self.viewer, avatar_url="/media/avatars/alice.png",
        )
        self.assertEqual(payload["avatar_url"], "/media/avatars/alice.png")

    def test_payload_avatar_url_is_none_when_not_provided(self):
        payload = build_chat_message_payload(
            self.base_event, user=self.sender, vote_value=None, current_user=self.viewer,
        )
        self.assertIsNone(payload["avatar_url"])

    def test_payload_avatar_url_forced_to_anonymous_icon_for_anonymous(self):
        event = {**self.base_event, "anonymous": True}
        payload = build_chat_message_payload(
            event, user=self.sender, vote_value=None,
            current_user=self.viewer, avatar_url="/media/avatars/alice.png",
        )
        self.assertEqual(payload["avatar_url"], "/static/home/images/anonymous.svg")

    def test_payload_avatar_url_is_none_when_user_has_no_avatar(self):
        payload = build_chat_message_payload(
            self.base_event, user=self.sender, vote_value=None,
            current_user=self.viewer, avatar_url=None,
        )
        self.assertIsNone(payload["avatar_url"])
