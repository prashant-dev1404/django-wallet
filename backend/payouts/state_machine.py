from .models import Payout


class IllegalStateTransition(Exception):
    def __init__(self, current: str, requested: str):
        self.current = current
        self.requested = requested
        super().__init__(
            f"Cannot transition from {current} to {requested}"
        )


def transition_to(payout: Payout, new_status: str) -> None:
    """
    Transition a payout to a new status, validating the transition is allowed.

    Args:
        payout: The Payout instance to transition
        new_status: The new status to transition to

    Raises:
        IllegalStateTransition: If the transition is not allowed
    """
    allowed = payout.ALLOWED_TRANSITIONS.get(payout.status, set())
    if new_status not in allowed:
        raise IllegalStateTransition(payout.status, new_status)

    payout.status = new_status
    payout.save(update_fields=["status", "updated_at"])


def can_transition(payout: Payout, new_status: str) -> bool:
    """
    Check if a payout can transition to a new status without raising an exception.

    Args:
        payout: The Payout instance to check
        new_status: The new status to check

    Returns:
        bool: True if the transition is allowed, False otherwise
    """
    allowed = payout.ALLOWED_TRANSITIONS.get(payout.status, set())
    return new_status in allowed