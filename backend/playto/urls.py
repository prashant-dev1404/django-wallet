from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse

def health_view(request):
    """Health check endpoint that doesn't touch the database."""
    return HttpResponse("OK")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("payouts.urls")),
    path("api/v1/", include("ledger.urls")),
    path("healthz/", health_view),  # for Railway healthcheck
]
