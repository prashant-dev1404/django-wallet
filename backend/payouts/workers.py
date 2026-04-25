import random
import time
import logging
from datetime import timedelta
from django.utils import timezone
from .models import Payout
from . import services as payout_services
from idempotency.services import cleanup_expired_keys

logger = logging.getLogger(__name__)


def simulate_bank_settlement() -> str:
    """
    Simulate bank response. Distribution: 70% success, 20% failure, 10% hang.
    Runs OUTSIDE any database transaction — no locks are held during sleep.
    """
    r = random.random()
    if r < 0.70:
        time.sleep(random.uniform(0.1, 0.5))
        return "success"
    elif r < 0.90:
        time.sleep(random.uniform(0.1, 0.5))
        return "failure"
    else:
        # Hang longer than the 30s stuck threshold so recovery fires
        time.sleep(35)
        return "hang"


def process_pending_payouts() -> None:
    """
    Pick up PENDING payouts, call simulated settlement, record outcome.
    Scheduled every minute via Django-Q.
    """
    picked_ids = payout_services.pickup_pending_payouts(limit=50)
    logger.info(f"Picked up {len(picked_ids)} payouts for processing")

    for payout_id in picked_ids:
        # Bank call happens OUTSIDE the transaction that did the pickup
        outcome = simulate_bank_settlement()
        if outcome == "hang":
            logger.info(f"Payout {payout_id} hanging — recover_stuck_payouts will handle it")
            continue
        try:
            payout_services.settle_payout(payout_id, outcome)
            logger.info(f"Settled payout {payout_id} with outcome={outcome}")
        except Exception:
            logger.exception(f"Failed to settle payout {payout_id}")


def recover_stuck_payouts() -> None:
    """
    Find payouts stuck in PROCESSING for > 30 seconds and retry or fail them.
    Scheduled every minute via Django-Q.
    """
    cutoff = timezone.now() - timedelta(seconds=30)
    stuck_ids = list(
        Payout.objects
        .filter(status=Payout.PROCESSING, processing_started_at__lt=cutoff)
        .values_list("id", flat=True)[:50]
    )
    if stuck_ids:
        logger.info(f"Recovering {len(stuck_ids)} stuck payouts")
    for payout_id in stuck_ids:
        try:
            payout_services.retry_or_fail(payout_id)
        except Exception:
            logger.exception(f"Failed to retry/fail payout {payout_id}")


def expire_idempotency_keys() -> None:
    """Delete idempotency keys older than 24 hours. Scheduled hourly."""
    count = cleanup_expired_keys()
    logger.info(f"Expired {count} idempotency keys")
