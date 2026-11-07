from django.test import TestCase

from chat.exceptions import ClientError
from chat.models import Message, Room
from chat.reaction_repository import ChatReactionRepository
from chat.tests.utils import make_user


class ChatReactionRepositoryTest(TestCase):
    def setUp(self):
        self.user = make_user('reaction-repository-user')
        self.other_user = make_user('reaction-repository-other')
        self.room = Room.objects.create(title='Reaction repository room')
        self.message = Message.objects.create(room=self.room, sender=self.user, text='Message')
        self.repository = ChatReactionRepository(self.user)

    async def test_votes_are_saved_and_scoped_to_the_current_user(self):
        counts = await self.repository.add_vote('upvote', self.message.id)
        vote = await self.repository.get_vote(self.message.id)
        other_vote = await ChatReactionRepository(self.other_user).get_vote(self.message.id)

        self.assertEqual(counts, (1, 0))
        self.assertEqual(vote.vote, 'upvote')
        self.assertIsNone(other_vote)

        counts = await self.repository.remove_vote('upvote', self.message.id)

        self.assertEqual(counts, (0, 0))
        self.assertIsNone(await self.repository.get_vote(self.message.id))

    async def test_reactions_toggle_and_return_current_counts(self):
        self.assertTrue(await self.repository.toggle_reaction('bulb', self.message.id))
        self.assertEqual(await self.repository.get_reaction_counts(self.message.id), {'bulb': 1, 'question': 0})
        self.assertEqual(await self.repository.get_user_reactions(self.user.id, self.message.id), ['bulb'])

        self.assertFalse(await self.repository.toggle_reaction('bulb', self.message.id))
        self.assertEqual(await self.repository.get_user_reactions(self.user.id, self.message.id), [])

    async def test_missing_message_preserves_empty_read_results(self):
        self.assertIsNone(await self.repository.get_vote(999999))
        self.assertEqual(await self.repository.get_vote_voters(999999), {'upvoters': [], 'downvoters': []})
        self.assertEqual(await self.repository.get_reaction_counts(999999), {'bulb': 0, 'question': 0})
        self.assertEqual(await self.repository.get_user_reactions(self.user.id, 999999), [])

    async def test_private_room_access_is_required(self):
        private_room = await Room.objects.acreate(title='Private reaction room', public=False)
        message = await Message.objects.acreate(room=private_room, sender=self.user, text='Private')

        with self.assertRaises(ClientError) as raised:
            await self.repository.add_vote('upvote', message.id)

        self.assertEqual(raised.exception.code, 'ACCESS_DENIED')
