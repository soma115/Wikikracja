from django.db.models import Q

from .models import Post


def get_context(user, month_param: str = '') -> dict:
    """Return dashboard widgets for the board app (featured documents carousel)."""
    visible = Q(is_public=True)
    if user.is_authenticated:
        visible |= Q(author=user)
    featured_documents = Post.objects.filter(visible).filter(featured_image__isnull=False).exclude(featured_image='').order_by('-updated').only('pk', 'title', 'subtitle', 'featured_image')[:10]
    return {'featured_documents': featured_documents}


def get_public_context() -> dict:
    """Return public landing page content managed by the board app."""
    return {'start': Post.get_system_post('start')}
