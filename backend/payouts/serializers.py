from rest_framework import serializers
from .models import Payout


class PayoutCreateSerializer(serializers.Serializer):
    """
    Serializer for creating payouts.
    Validates basic field constraints but not business rules.
    """
    amount_paise = serializers.IntegerField(min_value=1, max_value=1000000000)  # 10M rupees in paise
    bank_account_id = serializers.UUIDField()

    # Note: do NOT validate bank account ownership here. That's a business
    # rule, validated in the service layer where we already have the merchant
    # context. Serializers are for shape, services are for rules.


class PayoutSerializer(serializers.ModelSerializer):
    """
    Serializer for payout responses.
    """
    bank_account_id = serializers.SerializerMethodField()

    class Meta:
        model = Payout
        fields = ["id", "amount_paise", "bank_account_id", "status",
                  "attempt_count", "failure_reason", "created_at",
                  "updated_at"]
        read_only_fields = fields

    def get_bank_account_id(self, obj):
        return str(obj.bank_account_id)

    # `bank_account` serializes as the UUID by default. Add a nested
    # BankAccountSerializer if the dashboard needs the masked number, but
    # that's a frontend concern — keep the API minimal.
