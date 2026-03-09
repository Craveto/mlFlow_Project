from django.shortcuts import get_object_or_404, redirect, render

from .models import ABTestRun


def _seed_ab_test_data():
    active_tests = ABTestRun.objects.filter(status='Active').order_by('-start_date')
    past_tests = ABTestRun.objects.exclude(status='Active').order_by('-start_date')

    if not active_tests and not past_tests:
        ABTestRun.objects.create(
            test_name="LSTM vs GRU Base",
            control_model_version="LSTM",
            treatment_model_version="GRU",
            control_mse=0.0733,
            treatment_mse=0.0519,
            improvement_pct=29.20,
            status='Active'
        )
        active_tests = ABTestRun.objects.filter(status='Active').order_by('-start_date')

    return active_tests, past_tests


def _build_summary(active_tests, past_tests):
    all_tests = list(active_tests) + list(past_tests)
    avg_uplift = (
        sum(test.improvement_pct for test in all_tests) / len(all_tests)
        if all_tests else 0
    )
    best_test = max(all_tests, key=lambda test: test.improvement_pct, default=None)
    latest_launch = active_tests[0].start_date if active_tests else (past_tests[0].start_date if past_tests else None)
    return {
        "active_count": len(active_tests),
        "past_count": len(past_tests),
        "avg_uplift": avg_uplift,
        "best_test": best_test,
        "latest_launch": latest_launch,
    }


def ab_testing_index(request):
    """
    Displays and creates A/B tests between model versions.
    """
    form_error = None
    if request.method == "POST":
        try:
            test_name = request.POST.get("test_name", "").strip()
            control_model_version = request.POST.get("control_model_version", "").strip()
            treatment_model_version = request.POST.get("treatment_model_version", "").strip()
            control_mse = float(request.POST.get("control_mse", "0"))
            treatment_mse = float(request.POST.get("treatment_mse", "0"))

            if not test_name or not control_model_version or not treatment_model_version:
                raise ValueError("All fields are required.")
            if control_mse <= 0 or treatment_mse <= 0:
                raise ValueError("MSE values must be positive.")

            improvement_pct = ((control_mse - treatment_mse) / control_mse) * 100
            ABTestRun.objects.create(
                test_name=test_name,
                control_model_version=control_model_version,
                treatment_model_version=treatment_model_version,
                control_mse=control_mse,
                treatment_mse=treatment_mse,
                improvement_pct=improvement_pct,
                status='Active'
            )
            return redirect('ab_testing_index')
        except Exception as exc:
            form_error = str(exc)

    active_tests, past_tests = _seed_ab_test_data()
    summary = _build_summary(list(active_tests), list(past_tests))

    context = {
        'active_tests': active_tests,
        'past_tests': past_tests,
        'form_error': form_error,
        'summary': summary,
    }
    return render(request, 'dashboard/ab_testing_index.html', context)


def complete_ab_test(request, test_id):
    if request.method == "POST":
        test = get_object_or_404(ABTestRun, id=test_id)
        test.status = "Completed"
        test.save(update_fields=["status"])
    return redirect('ab_testing_index')
