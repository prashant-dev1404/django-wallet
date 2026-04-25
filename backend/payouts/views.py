import hashlib
import json
from uuid import UUID
from django.core.serializers.json import DjangoJSONEncoder
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.core.exceptions import ValidationError
from .models import Payout
from .services import create_payout, InsufficientBalance
from .serializers import PayoutSerializer, PayoutCreateSerializer
from idempotency.services import check_or_record, record_response, IdempotencyResult
from ledger.models import Merchant


def _hash_request_body(data: dict) -> str:
    """Create SHA256 hash of canonical JSON request body."""
    canonical_json = json.dumps(data, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical_json.encode()).hexdigest()


class CreatePayoutView(APIView):
    """
    POST /api/v1/payouts

    Create a new payout request with idempotency support.
    """

    def post(self, request):
        merchant_id_str = request.headers.get('X-Merchant-Id')
        idempotency_key = request.headers.get('Idempotency-Key')

        if not merchant_id_str:
            return Response(
                {"error": "X-Merchant-Id header required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not idempotency_key:
            return Response(
                {"error": "Idempotency-Key header required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Key must be a UUID string
        try:
            UUID(idempotency_key)
        except ValueError:
            return Response(
                {"error": "Idempotency-Key must be a valid UUID"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            merchant_id = UUID(merchant_id_str)
        except ValueError:
            return Response(
                {"error": "Invalid merchant ID format"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate merchant exists
        try:
            merchant = Merchant.objects.get(id=merchant_id)
        except Merchant.DoesNotExist:
            return Response(
                {"error": "Merchant not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Validate request body
        serializer = PayoutCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Hash the request body for idempotency — use raw request.data so
        # the hash matches on replay without UUID serialization issues.
        request_hash = _hash_request_body(request.data)

        # Check idempotency
        result_type, idempotency_record = check_or_record(
            merchant_id, idempotency_key, request_hash
        )

        if result_type == IdempotencyResult.REPLAY:
            # Return stored response
            return Response(
                json.loads(idempotency_record.response_body),
                status=idempotency_record.response_status
            )

        elif result_type == IdempotencyResult.IN_FLIGHT:
            return Response(
                {"error": "Request in flight, retry shortly"},
                status=status.HTTP_409_CONFLICT
            )

        elif result_type == IdempotencyResult.CONFLICT:
            return Response(
                {"error": "Idempotency key reused with different payload"},
                status=status.HTTP_409_CONFLICT
            )

        # result_type == IdempotencyResult.PROCEED - continue with business logic
        try:
            payout = create_payout(
                merchant_id=merchant_id,
                bank_account_id=serializer.validated_data['bank_account_id'],
                amount_paise=serializer.validated_data['amount_paise']
            )

            # Serialize response
            response_serializer = PayoutSerializer(payout)
            response_data = response_serializer.data

            # Record the response for idempotency
            record_response(idempotency_record, json.dumps(response_data, cls=DjangoJSONEncoder), 201)

            return Response(response_data, status=status.HTTP_201_CREATED)

        except InsufficientBalance as e:
            error_data = {"error": str(e)}
            record_response(idempotency_record, json.dumps(error_data), 402)
            return Response(error_data, status=402)

        except ValidationError as e:
            error_data = {"error": str(e)}
            record_response(idempotency_record, json.dumps(error_data), 400)
            return Response(error_data, status=status.HTTP_400_BAD_REQUEST)


class PayoutListView(APIView):
    """
    GET /api/v1/payouts

    List payouts for the merchant with optional status filtering.
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

        # Validate merchant exists
        try:
            merchant = Merchant.objects.get(id=merchant_id)
        except Merchant.DoesNotExist:
            return Response(
                {"error": "Merchant not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get query parameters
        status_filter = request.query_params.get('status')
        limit = min(int(request.query_params.get('limit', 25)), 100)
        offset = int(request.query_params.get('offset', 0))

        # Build queryset
        queryset = Payout.objects.filter(merchant=merchant).order_by('-created_at')

        if status_filter:
            if status_filter not in dict(Payout.STATUS_CHOICES):
                return Response(
                    {"error": f"Invalid status: {status_filter}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            queryset = queryset.filter(status=status_filter)

        # Paginate
        total_count = queryset.count()
        payouts = queryset[offset:offset + limit]

        serializer = PayoutSerializer(payouts, many=True)

        return Response({
            "payouts": serializer.data,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
        })


class PayoutDetailView(APIView):
    """
    GET /api/v1/payouts/{id}

    Get details of a specific payout.
    """

    def get(self, request, pk):
        merchant_id_str = request.headers.get('X-Merchant-Id')
        if not merchant_id_str:
            return Response(
                {"error": "X-Merchant-Id header required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            merchant_id = UUID(merchant_id_str)
            payout_id = UUID(pk)
        except ValueError:
            return Response(
                {"error": "Invalid ID format"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            payout = Payout.objects.get(id=payout_id, merchant_id=merchant_id)
            serializer = PayoutSerializer(payout)
            return Response(serializer.data)
        except Payout.DoesNotExist:
            return Response(
                {"error": "Payout not found"},
                status=status.HTTP_404_NOT_FOUND
            )
#
# ============================================================================
# GET /api/v1/payouts/<uuid:pk>
# ============================================================================
# class PayoutDetailView(RetrieveAPIView):
#   - Filter queryset by X-Merchant-Id header — a merchant can only fetch
#     their own payouts. 404 otherwise.
#   - PayoutSerializer.
#
# ============================================================================
# Auth helper
# ============================================================================
# A small helper `get_merchant_id_from_request(request) -> UUID` that:
#   - reads X-Merchant-Id header
#   - validates it's a UUID
#   - confirms the merchant exists
#   - raises DRF's NotAuthenticated otherwise (-> 401)
#
# This is the simplified auth model. Real auth (JWTs, signed sessions) is
# out of scope per CLAUDE.md.
