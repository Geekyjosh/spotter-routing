
from django.urls import path

from .views import hourly_forecast

urlpatterns = [
    path("forecast/", hourly_forecast, name="hourly-forecast"),
]
