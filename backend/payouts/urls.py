from django.urls import path
from . import views

urlpatterns = [
    path("payouts", views.CreatePayoutView.as_view(), name="payout-create"),
    path("payouts/list", views.PayoutListView.as_view(), name="payout-list"),
    path("payouts/<uuid:pk>", views.PayoutDetailView.as_view(), name="payout-detail"),
]
