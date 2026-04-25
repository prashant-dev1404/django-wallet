from django.core.management.base import BaseCommand
from django_q.models import Schedule


class Command(BaseCommand):
    help = "Idempotently register recurring Django-Q tasks."

    SCHEDULES = [
        {
            "func": "payouts.workers.process_pending_payouts",
            "defaults": {"schedule_type": Schedule.MINUTES, "minutes": 1},
        },
        {
            "func": "payouts.workers.recover_stuck_payouts",
            "defaults": {"schedule_type": Schedule.MINUTES, "minutes": 1},
        },
        {
            "func": "payouts.workers.expire_idempotency_keys",
            "defaults": {"schedule_type": Schedule.HOURLY},
        },
    ]

    def handle(self, *args, **options):
        for item in self.SCHEDULES:
            _, created = Schedule.objects.update_or_create(
                func=item["func"],
                defaults=item["defaults"],
            )
            verb = "Created" if created else "Updated"
            self.stdout.write(f"{verb}: {item['func']}")
        self.stdout.write(self.style.SUCCESS("Schedules registered."))
