from django.conf import settings
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils.translation import gettext as _

from home.services.feed import invalidate_feed_cache_on_change
from zzz.utils import get_site_domain

from .models import Post

# Import the utility function we created
try:
    from chat.utils import send_message_to_room
except ImportError:
    # Fallback if the function isn't available
    def send_message_to_room(room_title, message_text, sender=None, anonymous=True):
        print(f"Would send message to {room_title}: {message_text}")
        return None


@receiver(post_save, sender=Post)
def notify_important_chat_on_important_post(sender, instance, created, **kwargs):
    """
    Send notification to "Ważne" chat room when a post is important

    Args:
        sender: The model class that sent the signal
        instance: The actual instance being saved
        created: Boolean indicating if this is a new instance
        **kwargs: Additional keyword arguments
    """
    # Only process if the post is important
    if not instance.is_important:
        return

    # Determine if this is a new important post or an update to an existing one
    post_path = reverse('board:view_post', args=[instance.pk])
    protocol = 'http' if settings.DEBUG else 'https'
    post_url = f"{protocol}://{get_site_domain()}{post_path}"

    if created:
        message = _("New important document by %(username)s: %(title)s - %(post_url)s") % {'username': instance.author.username, 'post_url': post_url, 'title': instance.title}
    else:
        message = _("Updated important document by %(username)s: %(title)s - %(post_url)s") % {'username': instance.author.username, 'post_url': post_url, 'title': instance.title}

    # Send a message to the "Ważne" room with the post author as sender
    # Set anonymous=False to ensure the sender is properly attributed in the UI
    send_message_to_room(room_title="Ważne", message_text=message, sender=instance.author, anonymous=False)  # This ensures the message is NOT anonymous


@receiver(post_save, sender=Post)
@receiver(post_delete, sender=Post)
def _invalidate_feed_cache_on_post_change(sender, **kwargs):
    invalidate_feed_cache_on_change(sender, **kwargs)
