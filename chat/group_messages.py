from datetime import datetime


def format_chat_message(
    room_id: int,
    user_id: int,
    anonymous: bool,
    message: str,
    message_id: int,
    upvotes: int,
    downvotes: int,
    new: bool,
    edited: bool,
    date: datetime,
    latest_date: datetime,
    attachments: dict,
    reply_to: dict = None,
    reactions: dict = None,
    read_by: list = None,
    temp_id: str = None,
    upvoters: list = None,
    downvoters: list = None,
):
    """
    Return formatted dict with message data.
    Used to format messages loaded from DB or messages sent by user to chat.

    Nowe pola (ZMIANA 2, 4):
      reply_to  — {id, username, text_snippet} lub None
      reactions — {bulb: int, question: int, your_reactions: list} lub None
      read_by   — [{user_id, username, avatar_url}] lub None
      temp_id   — client-generated ID, echoed back so sender can match optimistic placeholder
      upvoters/downvoters — [usernames]; obecne tylko w pokojach zadań (głosy publiczne)
    """
    data = {
        "type": "chat.message",
        "room_id": room_id,
        "user_id": user_id,
        "message_id": message_id,
        "message": message,
        "anonymous": anonymous,
        "upvotes": upvotes,
        "downvotes": downvotes,
        "new": new,
        "edited": edited,
        "timestamp": int(date.timestamp()) * 1000,  # unix to ms
        "latest_timestamp": int(latest_date.timestamp()) * 1000,
        "attachments": attachments,
        # ZMIANA 2 — cytowanie
        "reply_to": reply_to,
        # ZMIANA 4 — reakcje + przeczytane
        "reactions": reactions or {"bulb": 0, "question": 0},
        "read_by": read_by or [],
        "temp_id": temp_id,
    }
    if upvoters is not None:
        data["upvoters"] = upvoters
    if downvoters is not None:
        data["downvoters"] = downvoters
    return data
