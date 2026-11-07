from channels.db import database_sync_to_async

from .exceptions import ClientError
from .message_repository import ChatMessageRepository
from .reactions import _reactions, _voter_lists, _voter_names_by_id


class ChatReactionRepository:
    """Persist votes and reactions on chat messages."""

    def __init__(self, user, message_repository=None):
        self.user = user
        self.message_repository = message_repository or ChatMessageRepository(user)

    def _get_accessible_message(self, message_id):
        return self.message_repository.get_accessible_message_sync(message_id)

    @database_sync_to_async
    def add_vote(self, event: str, message_id: int):
        """Add a vote directly to the message's reactions JSONField."""
        message = self._get_accessible_message(message_id)
        reactions_dict = _reactions(message)
        user_id = self.user.id

        if 'upvotes' not in reactions_dict:
            reactions_dict['upvotes'] = []
        if 'downvotes' not in reactions_dict:
            reactions_dict['downvotes'] = []

        if user_id in reactions_dict['upvotes']:
            reactions_dict['upvotes'].remove(user_id)
        if user_id in reactions_dict['downvotes']:
            reactions_dict['downvotes'].remove(user_id)

        if event == 'upvote':
            reactions_dict['upvotes'].append(user_id)
        else:
            reactions_dict['downvotes'].append(user_id)

        message.reactions = reactions_dict
        message.save(update_fields=['reactions'])

        return len(reactions_dict.get('upvotes', [])), len(reactions_dict.get('downvotes', []))

    @database_sync_to_async
    def remove_vote(self, event: str, message_id: int):
        """Remove a vote directly from the message's reactions JSONField."""
        message = self._get_accessible_message(message_id)
        reactions_dict = _reactions(message)
        user_id = self.user.id

        if event == 'upvote' and user_id in reactions_dict.get('upvotes', []):
            reactions_dict['upvotes'].remove(user_id)
        elif event == 'downvote' and user_id in reactions_dict.get('downvotes', []):
            reactions_dict['downvotes'].remove(user_id)

        message.reactions = reactions_dict
        message.save(update_fields=['reactions'])

        return len(reactions_dict.get('upvotes', [])), len(reactions_dict.get('downvotes', []))

    @database_sync_to_async
    def get_vote(self, message_id: int):
        """Check the reactions JSONField on the message."""
        try:
            message = self._get_accessible_message(message_id)
        except ClientError as error:
            if error.code == "MESSAGE_INVALID":
                return None
            raise
        reactions_dict = _reactions(message)
        user_id = self.user.id

        if user_id in reactions_dict.get('upvotes', []):
            return type('Vote', (), {'vote': 'upvote'})()
        if user_id in reactions_dict.get('downvotes', []):
            return type('Vote', (), {'vote': 'downvote'})()
        return None

    @database_sync_to_async
    def get_vote_voters(self, message_id: int) -> dict:
        """Return voter display names for messages in task rooms."""
        try:
            message = self._get_accessible_message(message_id)
        except ClientError as error:
            if error.code == "MESSAGE_INVALID":
                return {'upvoters': [], 'downvoters': []}
            raise
        reactions_dict = _reactions(message)
        voter_ids = set(reactions_dict.get('upvotes', [])) | set(reactions_dict.get('downvotes', []))
        return _voter_lists(reactions_dict, _voter_names_by_id(voter_ids))

    @database_sync_to_async
    def toggle_reaction(self, reaction: str, message_id: int) -> bool:
        """Toggle reaction for current user. Returns True if added, False if removed."""
        message = self._get_accessible_message(message_id)
        reactions_dict = _reactions(message)
        user_id = self.user.id

        if reaction not in reactions_dict:
            reactions_dict[reaction] = []

        if user_id in reactions_dict[reaction]:
            reactions_dict[reaction].remove(user_id)
            added = False
        else:
            reactions_dict[reaction].append(user_id)
            added = True

        message.reactions = reactions_dict
        message.save(update_fields=['reactions'])
        return added

    @database_sync_to_async
    def get_reaction_counts(self, message_id: int) -> dict:
        """Return reaction counts for a message."""
        try:
            reactions_dict = _reactions(self._get_accessible_message(message_id))
        except ClientError as error:
            if error.code == "MESSAGE_INVALID":
                return {'bulb': 0, 'question': 0}
            raise
        return {'bulb': len(reactions_dict.get('bulb', [])), 'question': len(reactions_dict.get('question', []))}

    @database_sync_to_async
    def get_user_reactions(self, user_id: int, message_id: int) -> list:
        """Return the reactions a user added to a message."""
        try:
            reactions_dict = _reactions(self._get_accessible_message(message_id))
        except ClientError as error:
            if error.code == "MESSAGE_INVALID":
                return []
            raise
        return [reaction for reaction in ('bulb', 'question') if user_id in reactions_dict.get(reaction, [])]
