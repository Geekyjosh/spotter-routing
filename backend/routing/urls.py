from django.urls import path
from .views import health_check, generate_routes

urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("routes/", generate_routes, name="generate-routes"),
]