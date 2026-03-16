from django.urls import path

from . import api_views


urlpatterns = [
    path("overview/", api_views.overview_api, name="api_overview"),
    path("forecast/", api_views.forecast_api, name="api_forecast"),
    path("drift/", api_views.drift_api, name="api_drift"),
    path("roi/", api_views.roi_api, name="api_roi"),
]
