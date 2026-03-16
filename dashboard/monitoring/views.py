from django.shortcuts import render


def dashboard_overview(request):
    return render(request, "dashboard/overview.html", {"api_url": "/api/overview/"})


def drift_monitoring(request):
    return render(request, "dashboard/drift_monitoring.html", {"api_url": "/api/drift/"})
