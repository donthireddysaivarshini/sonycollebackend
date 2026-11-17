from django.core.management.base import BaseCommand
from payments.tasks import process_pending_refund_records


class Command(BaseCommand):
    help = 'Executes recoverable customer refund queue against Razorpay with idempotency protection.'

    def handle(self, *args, **options):
        count = process_pending_refund_records()
        self.stdout.write(
            self.style.SUCCESS(f"Successfully processed {count} pending refund record(s).")
        )

