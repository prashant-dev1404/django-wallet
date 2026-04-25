class InvalidAmount(ValueError):
    """amount_paise <= 0 or exceeds MONEY_MAX_PAISE."""


class InsufficientBalance(Exception):
    """Available balance is less than the requested debit."""

    def __init__(self, available_paise: int, requested_paise: int):
        self.available_paise = available_paise
        self.requested_paise = requested_paise
        super().__init__(
            f"Insufficient balance: available={available_paise}, "
            f"requested={requested_paise}"
        )
