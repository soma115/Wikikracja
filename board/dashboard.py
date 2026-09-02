from .models import Post


def get_public_context() -> dict:
    """Return public landing page content managed by the board app."""
    return {'start': Post.get_system_post('start')}
