from django.utils import timezone

from core.richtext import plain_text

from .models import Post


def get_feed_items(since: timezone.datetime) -> list[dict]:
    """Return feed items for board posts modified since `since`."""
    posts = Post.objects.filter(updated__gte=since, visibility__in=(Post.Visibility.GROUP, Post.Visibility.PUBLIC)).select_related('author', 'author__uzytkownik', 'category').order_by('-updated')
    items = []
    for post in posts:
        items.append(
            {
                'content_type': 'post',
                'title': post.get_display_title(),
                'subtitle': post.subtitle,
                'description': plain_text(post.text, 125),
                'author': post.author,
                'category_label': post.category.name if post.category else None,
                'timestamp': post.updated,
                'url': f"/board/view/{post.pk}/",
                'object_id': post.pk,
                'visibility': post.visibility,
                'is_public': post.visibility == Post.Visibility.PUBLIC,
                'author_id': post.author_id,
            }
        )
    return items


def prepare_items(items, user):
    """Show group documents only to authenticated members."""
    if user.is_authenticated:
        return items
    return [item if item['visibility'] == Post.Visibility.PUBLIC else None for item in items]


def prepare_digest_items(items, user, since):
    """Apply the same visibility policy to email digests."""
    return prepare_items(items, user)
