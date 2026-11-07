from django.core.management.base import BaseCommand

from bookkeeping.models import Transaction
from bookkeeping.services import process_payment_reminders


class Command(BaseCommand):
    help = 'Generate the next payment periods and send due-date reminders.'

    def handle(self, *args, **options):
        process_payment_reminders()
        planned_count = Transaction.objects.filter(status=Transaction.Status.PLANNED, payment_due__cancelled_at__isnull=True).count()
        self.stdout.write(self.style.SUCCESS(f'Payment periods processed. Planned transactions available: {planned_count}.'))
