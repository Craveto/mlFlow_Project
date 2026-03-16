from django.shortcuts import render

from src.models.roi_service import calculate_roi_dashboard

from .models import ROIMetric


def _sync_snapshot(best_strategy):
    if best_strategy is None:
        return

    latest = ROIMetric.objects.order_by('-calculated_at').first()
    if latest:
        same_model = latest.model_version == best_strategy.model_name
        same_period = latest.period == best_strategy.period_label
        same_profit = abs(latest.simulated_profit_usd - best_strategy.net_profit_usd) < 0.01
        same_risk = abs(latest.risk_reduction_pct - best_strategy.risk_reduction_pct) < 0.01
        if same_model and same_period and same_profit and same_risk:
            return

    ROIMetric.objects.create(
        model_version=best_strategy.model_name,
        period=best_strategy.period_label,
        simulated_profit_usd=best_strategy.net_profit_usd,
        risk_reduction_pct=best_strategy.risk_reduction_pct,
    )


def roi_index(request):
    """
    Displays a live ROI simulation from the saved hourly model bundles.
    """
    roi_dashboard = calculate_roi_dashboard()
    best_strategy = roi_dashboard["best_strategy"]
    _sync_snapshot(best_strategy)

    context = {"api_url": "/api/roi/"}
    return render(request, 'dashboard/roi_index.html', context)
