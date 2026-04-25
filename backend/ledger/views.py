from uuid import UUID
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError
from .models import Merchant, BankAccount, LedgerEntry
from .services import get_merchant_balance_summary
from .serializers import LedgerEntrySerializer, BalanceSerializer, MerchantSerializer, BankAccountSerializer


class BalanceView(APIView):
    """
    GET /api/v1/balance

    Returns merchant's balance information.
    Reads X-Merchant-Id header for authentication.
    No transaction needed — read-only, eventual consistency is fine.
    """

    def get(self, request):
        merchant_id_str = request.headers.get('X-Merchant-Id')
        if not merchant_id_str:
            return Response(
                {"error": "X-Merchant-Id header required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            merchant_id = UUID(merchant_id_str)
        except ValueError:
            return Response(
                {"error": "Invalid merchant ID format"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            merchant = Merchant.objects.get(id=merchant_id)
        except Merchant.DoesNotExist:
            return Response(
                {"error": "Merchant not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        balance_data = get_merchant_balance_summary(merchant_id)
        serializer = BalanceSerializer(balance_data)
        return Response(serializer.data)


class LedgerListView(APIView):
    """
    GET /api/v1/ledger

    Paginated list of recent ledger entries for the merchant.
    Query params: limit (default 25, max 100), offset.
    Order by -created_at.
    """

    def get(self, request):
        merchant_id_str = request.headers.get('X-Merchant-Id')
        if not merchant_id_str:
            return Response(
                {"error": "X-Merchant-Id header required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            merchant_id = UUID(merchant_id_str)
        except ValueError:
            return Response(
                {"error": "Invalid merchant ID format"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            merchant = Merchant.objects.get(id=merchant_id)
        except Merchant.DoesNotExist:
            return Response(
                {"error": "Merchant not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get query parameters
        limit = min(int(request.query_params.get('limit', 25)), 100)
        offset = int(request.query_params.get('offset', 0))

        # Get paginated ledger entries
        queryset = LedgerEntry.objects.filter(merchant=merchant).order_by('-created_at')
        total_count = queryset.count()

        entries = queryset[offset:offset + limit]
        serializer = LedgerEntrySerializer(entries, many=True)

        return Response({
            "entries": serializer.data,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
        })


class MerchantListView(APIView):
    """GET /api/v1/merchants — list all seeded merchants for the dashboard selector."""

    def get(self, request):
        merchants = Merchant.objects.all()
        serializer = MerchantSerializer(merchants, many=True)
        return Response(serializer.data)


class BankAccountListView(APIView):
    """GET /api/v1/bank-accounts — list bank accounts for the current merchant."""

    def get(self, request):
        merchant_id_str = request.headers.get('X-Merchant-Id')
        if not merchant_id_str:
            return Response(
                {"error": "X-Merchant-Id header required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            merchant_id = UUID(merchant_id_str)
        except ValueError:
            return Response(
                {"error": "Invalid merchant ID format"},
                status=status.HTTP_400_BAD_REQUEST
            )
        accounts = BankAccount.objects.filter(merchant_id=merchant_id)
        serializer = BankAccountSerializer(accounts, many=True)
        return Response(serializer.data)
