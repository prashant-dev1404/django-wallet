from django.urls import path
from . import views

urlpatterns = [
    path("balance", views.BalanceView.as_view(), name="balance"),
    path("ledger", views.LedgerListView.as_view(), name="ledger"),
    path("merchants", views.MerchantListView.as_view(), name="merchant-list"),
    path("bank-accounts", views.BankAccountListView.as_view(), name="bank-account-list"),
]
