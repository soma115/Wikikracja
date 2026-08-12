from django.utils import timezone
from django.utils.html import strip_tags

from .models import Post


def get_feed_items(since: timezone.datetime) -> list[dict]:
    """Return feed items for board posts modified since `since`."""
    posts = Post.objects.filter(updated__gte=since).select_related('author', 'author__uzytkownik').order_by('-updated')
    items = []
    for post in posts:
        clean_text = strip_tags(post.text)
        items.append(
            {
                'content_type': 'post',
                'title': post.title,
                'description': clean_text[:125] + '...' if len(clean_text) > 125 else clean_text,
                'author': post.author,
                'timestamp': post.updated,
                'url': f"/board/view/{post.pk}/",
                'object_id': post.pk,
            }
        )
    return items


def mark_as_read(object_id: int, user) -> None:
    from home.models import ReadStatus

    ReadStatus.objects.get_or_create(user=user, content_type=ReadStatus.ContentType.POST, object_id=object_id)


def mark_as_unread(object_id: int, user) -> None:
    from home.models import ReadStatus

    ReadStatus.objects.filter(user=user, content_type=ReadStatus.ContentType.POST, object_id=object_id).delete()
