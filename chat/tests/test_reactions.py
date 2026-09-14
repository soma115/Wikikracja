from types import SimpleNamespace
from unittest.mock import AsyncMock

from django.test import SimpleTestCase

from chat.exceptions import ClientError
from chat.reactions import ChatReactionService


class ChatReactionServiceTest(SimpleTestCase):
    def setUp(self):
        self.repository = SimpleNamespace(
            get_vote=AsyncMock(),
            add_vote=AsyncMock(return_value=(2, 1)),
            remove_vote=AsyncMock(return_value=(1, 1)),
            toggle_reaction=AsyncMock(return_value=True),
            get_reaction_counts=AsyncMock(return_value={'bulb': 1, 'question': 0}),
        )
        self.service = ChatReactionService(self.repository)

    async def test_switching_vote_removes_opposite_before_adding(self):
        self.repository.get_vote.return_value = SimpleNamespace(vote='downvote')

        result = await self.service.add_vote('upvote', 4)

        self.repository.remove_vote.assert_awaited_once_with('downvote', 4)
        self.repository.add_vote.assert_awaited_once_with('upvote', 4)
        self.assertEqual(result, (2, 1))

    async def test_repeating_same_vote_is_ignored(self):
        self.repository.get_vote.return_value = SimpleNamespace(vote='upvote')

        result = await self.service.add_vote('upvote', 4)

        self.assertIsNone(result)
        self.repository.remove_vote.assert_not_awaited()
        self.repository.add_vote.assert_not_awaited()

    async def test_unknown_reaction_is_rejected_before_repository_access(self):
        with self.assertRaises(ClientError) as raised:
            await self.service.toggle_reaction('heart', 4)

        self.assertEqual(raised.exception.code, 'INVALID_REACTION')
        self.repository.toggle_reaction.assert_not_awaited()

    async def test_toggle_reaction_returns_state_and_counts(self):
        result = await self.service.toggle_reaction('bulb', 4)
        self.assertEqual(result, (True, {'bulb': 1, 'question': 0}))
