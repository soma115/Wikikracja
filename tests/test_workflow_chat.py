"""Smoke test workflow chatu: Message + History (edycja) + ReadBy + Attachment + reactions JSON.

Weryfikuje że relacje między modelami chatu się trzymają i pole reactions (JSONField) przechowuje słownik.
"""

import pytest


@pytest.mark.django_db
def test_message_lifecycle(sample_users, chat_room):
    """Pełen cykl wiadomości: stworzenie → edycja z historią → read receipts → attachment → reactions."""
    from chat.models import Message, MessageAttachment, MessageHistory, MessageHistoryEntry, MessageReadBy

    room, _ = chat_room
    sender = sample_users[0]
    reader = sample_users[1]

    # 1. Wiadomość początkowa
    message = Message.objects.create(sender=sender, text='Initial message', room=room, anonymous=False)
    assert Message.objects.filter(room=room).count() == 1
    # Message.reactions = JSONField(default=dict, null=True) — po create() zawsze {}
    assert message.reactions == {}

    # 2. Historia (po edycji)
    history, _ = MessageHistory.objects.get_or_create(message=message)
    MessageHistoryEntry.objects.create(history=history, text='Previous version of message')
    message.text = 'Edited message'
    message.save()
    assert MessageHistoryEntry.objects.filter(history=history).count() == 1
    assert message.text == 'Edited message'

    # 3. Read receipts od dwóch userów
    MessageReadBy.objects.create(message=message, user=reader)
    MessageReadBy.objects.create(message=message, user=sender)
    assert MessageReadBy.objects.filter(message=message).count() == 2

    # 4. Attachment
    MessageAttachment.objects.create(type='document', filename='test_doc.pdf', message=message)
    assert MessageAttachment.objects.filter(message=message).count() == 1

    # 5. Reactions (JSONField) — bulb/question, listy user_id
    message.reactions = {'bulb': [reader.id], 'question': []}
    message.save()
    message.refresh_from_db()
    assert reader.id in message.reactions['bulb']
    assert message.reactions['question'] == []
