from .models import Message
from .services import get_unread_count_for_user


def get_group_settings_context(user) -> dict:
    from .federation import decrypt_federation_secret, refresh_federated_status
    from .models import Room

    rooms = list(Room.objects.filter(source_app='federation').order_by('title'))
    for room in rooms:
        refresh_federated_status(room)
        secret = decrypt_federation_secret(room.federation_secret_ciphertext) if room.federation_secret_ciphertext else None
        room.federation_secret_display = secret.decode('utf-8') if secret else ''
    return {'federated_rooms': rooms}


def get_context(user, month_param: str = '') -> dict:
    """Return dashboard widgets for public chat messages and unread count."""
    recent_chat_messages = Message.objects.filter(room__public=True, room__allowed=user).select_related('sender', 'sender__uzytkownik', 'room').order_by('-time')[:4]
    chat_unread_count = get_unread_count_for_user(user)

    return {'recent_chat_messages': recent_chat_messages, 'chat_unread_count': chat_unread_count}
