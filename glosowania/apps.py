from django.apps import AppConfig


class VotingConfig(AppConfig):
    name = 'glosowania'

    def ready(self):
        import glosowania.signals  # noqa
        from home.feed_registry import register_feed_provider

        from .feed import get_feed_items, mark_as_read, mark_as_unread
        register_feed_provider(
            'decision',
            get_items=get_feed_items,
            mark_as_read=mark_as_read,
            mark_as_unread=mark_as_unread,
        )
