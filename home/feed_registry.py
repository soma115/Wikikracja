"""Registry for per-application feed item providers and read-state hooks.

Each application that contributes items to the unified activity feed:
1. implements `get_feed_items(since)` in `<app>/feed.py`;
2. implements `mark_as_read(object_id, user)` and `mark_as_unread(object_id, user)`
   for its content type (the storage mechanism is up to the app: `ReadStatus`,
   `Room.seen_by`, its own table, etc.);
3. registers everything in `<app>/apps.py::ready()`.

`home` no longer needs to import models from other apps to build, mark or unmark
feed items.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

FeedProvider = Callable[[datetime], list[dict]]
MarkHook = Callable[[int, object], None]


@dataclass
class FeedEntry:
    content_type: str
    get_items: FeedProvider
    mark_as_read: Optional[MarkHook] = None
    mark_as_unread: Optional[MarkHook] = None


_providers: dict[str, FeedEntry] = {}


def register_feed_provider(
    content_type: str,
    *,
    get_items: FeedProvider,
    mark_as_read: Optional[MarkHook] = None,
    mark_as_unread: Optional[MarkHook] = None,
) -> None:
    _providers[content_type] = FeedEntry(
        content_type=content_type,
        get_items=get_items,
        mark_as_read=mark_as_read,
        mark_as_unread=mark_as_unread,
    )


def get_provider(content_type: str) -> Optional[FeedEntry]:
    return _providers.get(content_type)


def collect_feed_items(since: datetime) -> list[dict]:
    items = []
    for entry in _providers.values():
        items.extend(entry.get_items(since))
    return items
