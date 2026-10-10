import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from board.models import Post
from site_settings.params import get_param

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Delete archived documents after their retention period'

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=get_param('delete_archived_document_after'))
        expired_posts = Post.objects.filter(visibility=Post.Visibility.ARCHIVE, system_key__isnull=True, updated__lt=cutoff).order_by('pk')
        deleted_count = 0

        for post in expired_posts.iterator():
            log.info('Archived document %s deleted after retention period.', post.pk)
            post.delete()
            deleted_count += 1

        self.stdout.write(f'Deleted {deleted_count} archived document(s).')
