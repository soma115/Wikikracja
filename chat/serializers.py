from home.templatetags.feed_filters import citizen_color_class


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
    username = "System" if user is None else ("Anonymous" if anonymous else user.username)
    payload["user_id"] = None if anonymous or user is None else user.id
    payload["username"] = username
    payload["avatar_url"] = "/static/home/images/anonymous.svg" if anonymous else avatar_url
    payload["citizen_color_class"] = citizen_color_class(username)
    payload["new"] = event["new"] if current_user != user else False
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
