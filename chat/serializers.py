from core.presence import presence_data
from core.richtext import strip_tags
from core.utils import citizen_color_class, user_display_name, user_initials

from .models import Message
from .reactions import _reactions, _voter_lists, _voter_names_by_id


def _reply_snippet(text, max_len=240):
    if not text:
        return ''
    plain = strip_tags(text)
    plain = plain.replace('… pokaż więcej', '').strip()
    return plain[:max_len]


def _username_to_color(username: str) -> str:
    """Deterministic hex color for username (for quote border-left)."""
    hue = sum(ord(char) for char in username) % 360
    return f"hsl({hue}, 60%, 55%)"


def _message_author_labels(message: Message) -> tuple[str, str]:
    """Return the username and display label, including snapshots for deleted authors."""
    if message.anonymous:
        label = message.sender_display_name if message.sender is None and message.sender_display_name else 'Anonymous'
        return label, label
    if message.sender is None:
        label = message.sender_display_name or 'System'
        return label, label
    return message.sender.username, user_display_name(message.sender)


def get_avatar_url(user):
    """Get user's uploaded avatar URL, or None when user has no avatar.

    Callers decide the fallback (placeholder image, initials, etc.).
    """
    try:
        profile = user.uzytkownik
        if profile.avatar:
            return profile.avatar.url
    except Exception:
        pass
    return None


def build_chat_message_event(message: Message, *, new: bool = False, temp_id: str = None, include_voters: bool = False, read_by=None, voter_names=None, reply_to=None) -> dict:
    """Build the transport event for a chat message.

    Single source of truth for the shape of a `chat.message` channel event
    and for the data returned by `get_recent_messages_batch`.
    """
    reactions_dict = _reactions(message)

    upvotes = getattr(message, 'upvotes', None)
    if upvotes is None:
        upvotes = len(reactions_dict.get('upvotes', []))
    downvotes = getattr(message, 'downvotes', None)
    if downvotes is None:
        downvotes = len(reactions_dict.get('downvotes', []))

    attachments = {}
    for attachment in message.attachments.all():
        attachments.setdefault(attachment.type, []).append(attachment.filename)

    reply_to_data = reply_to
    if reply_to_data is None and message.reply_to_id and message.reply_to:
        reply_message = message.reply_to
        reply_username, reply_display_name = _message_author_labels(reply_message)
        reply_to_data = {
            'id': reply_message.id,
            'username': reply_username,
            'display_name': reply_display_name,
            'text_snippet': _reply_snippet(reply_message.text),
            'author_color': _username_to_color(reply_username),
        }

    read_by_data = []
    if read_by:
        for entry in read_by:
            user = entry.user
            read_by_data.append(
                {
                    'user_id': user.id,
                    'username': user.username,
                    'display_name': user_display_name(user),
                    'initials': user_initials(user),
                    'avatar_url': get_avatar_url(user) or '/static/home/images/favicon.ico',
                    'citizen_color_class': citizen_color_class(user.username),
                    **presence_data(user),
                }
            )

    event = {
        'type': 'chat.message',
        'room_id': message.room_id,
        'user_id': message.sender_id,
        'message_id': message.id,
        'message': message.text,
        'anonymous': message.anonymous,
        'author_display_name': message.sender_display_name,
        'upvotes': upvotes,
        'downvotes': downvotes,
        'new': new,
        'edited': hasattr(message, 'messagehistory'),
        'timestamp': int(message.time.timestamp()) * 1000,
        'latest_timestamp': int(message.time.timestamp()) * 1000,
        'attachments': attachments,
        'reply_to': reply_to_data,
        'reactions': {'bulb': len(reactions_dict.get('bulb', [])), 'question': len(reactions_dict.get('question', []))},
        'read_by': read_by_data,
        'temp_id': temp_id,
    }

    if include_voters:
        if voter_names is None:
            voter_ids = set(reactions_dict.get('upvotes', [])) | set(reactions_dict.get('downvotes', []))
            voter_names = _voter_names_by_id(voter_ids)
        event.update(_voter_lists(reactions_dict, voter_names))

    return event


def build_chat_message_payloads(batch_data, current_user, avatar_url_for_user):
    """Serialize one repository batch using the canonical message serializer."""
    users = batch_data['users']
    votes = batch_data['user_votes']
    return [
        build_chat_message_payload(event, user=users.get(event['user_id']), vote_value=votes.get(event['message_id']), current_user=current_user, avatar_url=avatar_url_for_user(users.get(event['user_id'])))
        for event in batch_data['messages']
    ]


def build_chat_message_payload(event, *, user, vote_value, current_user, your_reactions=None, avatar_url=None):
    """Buduje payload wiadomości chata wysyłany do klienta (WebSocket -> JS).

    Wycina pola wewnętrzne (`type`), zostawia `user_id` żeby frontend mógł
    zbudować link do profilu autora. Dla wiadomości anonimowych `user_id`
    jest zerowane na None — nie zdradzamy autora po stronie klienta.
    Wiadomości systemowe (`user=None`, nie-anonimowe — np. rename pokoju)
    dostają `username='System'`, żeby front nie renderował autora jako '—:'.
    """
    anonymous = event.get("anonymous", False)
    payload = {k: v for k, v in event.items() if k not in ("type",)}
    author_display_name = event.get("author_display_name", "")
    username = "Anonymous" if anonymous else ("System" if user is None else user.username)
    if user is None and author_display_name:
        username = author_display_name
    payload["user_id"] = None if anonymous or user is None else user.id
    payload["username"] = username
    payload["display_name"] = user_display_name(user) if (user and not anonymous) else username
    payload["initials"] = user_initials(user) if (user and not anonymous) else username[:2].upper()
    payload["avatar_url"] = "/static/home/images/anonymous.svg" if anonymous else avatar_url
    payload["citizen_color_class"] = citizen_color_class(username)
    payload.update(presence_data(user) if user and not anonymous else {'presence_status': 'red', 'presence_source': '', 'presence_timestamp': None})
    payload["new"] = event["new"] if current_user != user else False
    payload["read_by_current_user"] = event.get("read_by_current_user", False)
    payload["your_vote"] = vote_value if vote_value else None
    payload["own"] = current_user == user

    reactions = event.get("reactions", {})
    if isinstance(reactions, dict):
        payload["bulb_count"] = reactions.get("bulb", 0)
        payload["question_count"] = reactions.get("question", 0)
    else:
        payload["bulb_count"] = event.get("bulb_count", 0)
        payload["question_count"] = event.get("question_count", 0)

    if your_reactions is not None:
        payload["your_reactions"] = your_reactions

    return payload
