from django.http import JsonResponse

from .api_payloads import (
    build_drift_payload,
    build_forecast_payload,
    build_overview_payload,
    build_roi_payload,
)


def overview_api(request):
    return JsonResponse(build_overview_payload())


def forecast_api(request):
    return JsonResponse(build_forecast_payload())


def drift_api(request):
    return JsonResponse(build_drift_payload())


def roi_api(request):
    return JsonResponse(build_roi_payload())
