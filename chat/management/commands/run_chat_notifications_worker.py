import logging
import socket
import time

import redis
from django.core.management.base import BaseCommand

from chat.notification_queue import CLAIM_IDLE_MS, acknowledge_notification, claim_notifications, ensure_consumer_group, read_notifications
from chat.notifications import deliver_notification_job

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Deliver chat notifications queued in Redis Streams."

    def add_arguments(self, parser):
        parser.add_argument('--consumer', default=f'{socket.gethostname()}-chat')
        parser.add_argument('--block-ms', type=int, default=5000)
        parser.add_argument('--batch-size', type=int, default=10)
        parser.add_argument('--claim-after-ms', type=int, default=CLAIM_IDLE_MS)

    def handle(self, *args, **options):
        from django.conf import settings

        client = redis.Redis.from_url(settings.REDIS_HOST, decode_responses=True)
        consumer = options['consumer']
        batch_size = options['batch_size']
        block_ms = options['block_ms']
        claim_after_ms = options['claim_after_ms']
        ensure_consumer_group(client)
        self.stdout.write(self.style.SUCCESS(f'Chat notification worker started as {consumer}'))

        try:
            while True:
                claimed = claim_notifications(client, consumer, count=batch_size, min_idle_ms=claim_after_ms)
                fresh = read_notifications(client, consumer, count=batch_size, block_ms=block_ms)
                for stream_id, job in [*claimed, *fresh]:
                    self._process_job(client, stream_id, job)
        except KeyboardInterrupt:
            self.stdout.write('Chat notification worker stopped.')

    @staticmethod
    def _process_job(client, stream_id, job):
        delivered_key = f"wikikracja:chat:notification-delivered:{job['job_id']}"
        if client.exists(delivered_key):
            acknowledge_notification(client, stream_id)
            return

        try:
            deliver_notification_job(job)
        except Exception as exc:
            log.error('Chat notification job %s failed and will be retried: %s', job['job_id'], exc, exc_info=True)
            time.sleep(0.1)
            return

        client.set(delivered_key, '1', ex=7 * 24 * 60 * 60)
        acknowledge_notification(client, stream_id)
