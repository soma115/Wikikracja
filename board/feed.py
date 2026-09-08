from django.utils import timezone

from core.richtext import plain_text

from .models import Post


def get_feed_items(since: timezone.datetime) -> list[dict]:
    """Return feed items for board posts modified since `since`."""
    posts = Post.objects.filter(updated__gte=since).select_related('author', 'author__uzytkownik').order_by('-updated')
    items = []
    for post in posts:
        items.append(
            {
                'content_type': 'post',
                'title': post.title,
                'description': plain_text(post.text, 125),
                'author': post.author,
                'timestamp': post.updated,
                'url': f"/board/view/{post.pk}/",
                'object_id': post.pk,
                'is_public': post.is_public,
                'author_id': post.author_id,
            }
        )
    return items


def prepare_items(items, user):
    """Hide private posts from everyone except the author."""
    prepared = []
    for item in items:
        if item['is_public']:
            prepared.append(item)
        elif user.is_authenticated and item['author_id'] == user.pk:
            prepared.append(item)
        else:
            prepared.append(None)
    return prepared


def prepare_digest_items(items, user, since):
    """Hide private posts from everyone except the author in email digests."""
    return prepare_items(items, user)
