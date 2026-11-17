from django.core.management.base import BaseCommand
from cart.models import StockReservation


class Command(BaseCommand):
    help = 'Expires stale active stock reservations past their 15-minute TTL and restores variant stock.'

    def handle(self, *args, **options):
        count = StockReservation.expire_stale_reservations()
        self.stdout.write(
            self.style.SUCCESS(f"Successfully processed and released {count} expired stock reservation(s).")
        )

