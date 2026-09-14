"""Domain rules for message votes and reactions."""

from .exceptions import ClientError


class ChatReactionService:
    """Apply vote and reaction rules using a message data repository."""

    VALID_REACTIONS = frozenset({'bulb', 'question'})
    OPPOSITE_VOTES = {'upvote': 'downvote', 'downvote': 'upvote'}

    def __init__(self, message_repository):
        self.repository = message_repository

    async def add_vote(self, vote, message_id):
        existing_vote = await self.repository.get_vote(message_id)
        if existing_vote is not None:
            if existing_vote.vote == vote:
                return None
            opposite_vote = self.OPPOSITE_VOTES.get(vote)
            if opposite_vote is not None:
                await self.repository.remove_vote(opposite_vote, message_id)
        return await self.repository.add_vote(vote, message_id)

    async def remove_vote(self, vote, message_id):
        return await self.repository.remove_vote(vote, message_id)

    async def toggle_reaction(self, reaction, message_id):
        if reaction not in self.VALID_REACTIONS:
            raise ClientError('INVALID_REACTION')
        added = await self.repository.toggle_reaction(reaction, message_id)
        counts = await self.repository.get_reaction_counts(message_id)
        return added, counts
