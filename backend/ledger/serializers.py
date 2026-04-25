from rest_framework import serializers
from .models import LedgerEntry, Merchant, BankAccount


class LedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = ["id", "entry_type", "amount_paise", "reference_type",
                  "reference_id", "description", "created_at"]
        read_only_fields = fields


class BalanceSerializer(serializers.Serializer):
    available_paise = serializers.IntegerField()
    held_paise = serializers.IntegerField()
    total_credited_paise = serializers.IntegerField()
    total_debited_paise = serializers.IntegerField()


class MerchantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Merchant
        fields = ["id", "name", "email"]
        read_only_fields = fields


class BankAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankAccount
        fields = ["id", "account_number_masked", "ifsc", "account_holder_name"]
        read_only_fields = fields
