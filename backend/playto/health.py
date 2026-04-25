# playto/health.py
#
# Minimal health endpoint for Railway's healthcheck system.
#
# from django.http import JsonResponse
#
# def health(request):
#     # Return 200 unconditionally. Do NOT touch the database here — if the DB
#     # is down, we want the app to keep showing as "up" so Railway routes
#     # traffic and lets it reconnect when the DB comes back. A DB-touching
#     # health endpoint causes restart loops.
#     return JsonResponse({"status": "ok"})
#
# Wire in playto/urls.py:
#   from playto.health import health
#   urlpatterns += [path("healthz/", health)]
