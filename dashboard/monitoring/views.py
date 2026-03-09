from django.shortcuts import render
import mlflow
from mlflow.tracking import MlflowClient
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

from project_config import (
    ARIMA_FORECAST_BUNDLE,
    BTC_SYMBOL,
    DATA_FREQUENCY_LABEL,
    DEFAULT_EXPERIMENTS,
    FORECAST_HORIZON_LABEL,
    FORECAST_MODEL_BUNDLE,
    PROCESSED_BTCUSD_CSV,
    RNN_FORECAST_BUNDLE,
    configure_mlflow,
)
from src.models.forecast_service import (
    get_arima_forecast,
    get_linear_forecast,
    get_preferred_forecast,
    get_rnn_forecast,
)


mlflow.set_tracking_uri(configure_mlflow())
DISPLAY_TZ = ZoneInfo("Asia/Kolkata")


def _get_run_mse(run):
    if "test_mse" in run.data.metrics:
        return run.data.metrics["test_mse"]
    if "mse" in run.data.metrics:
        return run.data.metrics["mse"]
    return None


def _normalize_model_type(run, fallback_name):
    model_type = run.data.params.get("model_type", fallback_name)
    if model_type == "LinearRegression":
        return "Linear Regression"
    return model_type


def _format_path_mtime(path):
    if not path.exists():
        return "Not generated"
    timestamp = datetime.fromtimestamp(path.stat().st_mtime, tz=DISPLAY_TZ)
    return timestamp.strftime("%Y-%m-%d %I:%M %p IST")


def _get_data_context():
    context = {
        "data_source": "Yahoo Finance",
        "symbol": BTC_SYMBOL,
        "data_frequency": DATA_FREQUENCY_LABEL,
        "coverage_start": "N/A",
        "coverage_end": "N/A",
        "latest_market_time": "N/A",
        "dashboard_time": datetime.now(DISPLAY_TZ).strftime("%Y-%m-%d %I:%M %p IST"),
    }

    if not PROCESSED_BTCUSD_CSV.exists():
        return context

    df = pd.read_csv(PROCESSED_BTCUSD_CSV, index_col=0, parse_dates=True)
    if df.empty:
        return context

    index = pd.to_datetime(df.index)
    start_time = index.min()
    end_time = index.max()
    context["coverage_start"] = start_time.strftime("%Y-%m-%d %H:%M")
    context["coverage_end"] = end_time.strftime("%Y-%m-%d %H:%M")
    context["latest_market_time"] = end_time.strftime("%Y-%m-%d %H:%M")
    return context


def _load_processed_data():
    if not PROCESSED_BTCUSD_CSV.exists():
        return None
    df = pd.read_csv(PROCESSED_BTCUSD_CSV, index_col=0, parse_dates=True)
    if df.empty:
        return None
    return df


def _format_change_amount(summary):
    if summary.latest_close is None or summary.next_step_forecast is None:
        return "N/A"
    change_amount = summary.next_step_forecast - summary.latest_close
    return f"{change_amount:+,.2f}"


def _format_validation(summary):
    if summary.latest_completed_prediction is None or summary.latest_completed_actual is None:
        return {
            "prediction": "N/A",
            "actual": "N/A",
            "error": "N/A",
        }
    return {
        "prediction": f"{summary.latest_completed_prediction:,.2f}",
        "actual": f"{summary.latest_completed_actual:,.2f}",
        "error": f"{summary.latest_completed_abs_error:,.2f}" if summary.latest_completed_abs_error is not None else "N/A",
    }


def _summarize_model_source(model_source):
    if "LSTM" in model_source or "GRU" in model_source:
        return "Neural"
    if "ARIMA" in model_source:
        return "Statistical"
    if "linear regression" in model_source.lower():
        return "Baseline"
    return "Model"


def _get_drift_snapshot():
    df = _load_processed_data()
    snapshot = {
        "status": "No data",
        "status_class": "secondary",
        "summary": "Processed BTC-USD data not available yet.",
        "latest_return": "N/A",
        "latest_volatility": "N/A",
        "volatility_ratio": "N/A",
        "price_vs_ma21": "N/A",
        "latest_date": "N/A",
    }
    if df is None or "Return_1h" not in df.columns:
        return snapshot

    working_df = df.dropna(subset=["Return_1h", "MA21", "Close"]).copy()
    if len(working_df) < 168:
        snapshot["summary"] = "Not enough processed rows to evaluate an hourly drift window."
        return snapshot

    latest_return = float(working_df["Return_1h"].iloc[-1] * 100)
    vol_24 = float(working_df["Return_1h"].tail(24).std() * 100)
    vol_168 = float(working_df["Return_1h"].tail(168).std() * 100)
    vol_ratio = vol_24 / vol_168 if vol_168 else 0
    price_vs_ma21 = float(((working_df["Close"].iloc[-1] / working_df["MA21"].iloc[-1]) - 1) * 100)
    latest_date = pd.to_datetime(working_df.index.max()).strftime("%Y-%m-%d %H:%M")

    if vol_ratio >= 1.8:
        status = "Alert"
        status_class = "danger"
        summary = "Short-term hourly volatility is materially above the 7-day baseline."
    elif vol_ratio >= 1.3:
        status = "Watch"
        status_class = "warning"
        summary = "Recent hourly volatility is rising. Monitor model stability closely."
    else:
        status = "Stable"
        status_class = "success"
        summary = "Recent hourly volatility is still close to the baseline range."

    snapshot.update(
        {
            "status": status,
            "status_class": status_class,
            "summary": summary,
            "latest_return": f"{latest_return:+.2f}%",
            "latest_volatility": f"{vol_24:.2f}%",
            "volatility_ratio": f"{vol_ratio:.2f}x",
            "price_vs_ma21": f"{price_vs_ma21:+.2f}%",
            "latest_date": latest_date,
        }
    )
    return snapshot


def dashboard_overview(request):
    """
    Fetches experiment data and model registry info from the shared MLflow store.
    """
    client = MlflowClient()
    latest_close = "N/A"
    forecast_horizon = FORECAST_HORIZON_LABEL
    active_forecast = "N/A"
    active_forecast_delta = None
    active_forecast_change = "N/A"
    forecast_status = "Saved forecast model not available."
    active_source_label = "Model"
    active_model_updated = "Not generated"
    linear_forecast = "N/A"
    linear_forecast_delta = None
    linear_forecast_change = "N/A"
    linear_source_label = "Baseline"
    linear_model_updated = _format_path_mtime(FORECAST_MODEL_BUNDLE)
    arima_forecast = "N/A"
    arima_forecast_delta = None
    arima_forecast_change = "N/A"
    arima_status = "Saved ARIMA bundle not available."
    arima_source_label = "Statistical"
    arima_model_updated = _format_path_mtime(ARIMA_FORECAST_BUNDLE)
    rnn_forecast = "N/A"
    rnn_forecast_delta = None
    rnn_forecast_change = "N/A"
    rnn_status = "Saved RNN bundle not available."
    rnn_source_label = "Neural"
    rnn_model_updated = _format_path_mtime(RNN_FORECAST_BUNDLE)
    best_model_metric = "N/A"
    best_model_name = "N/A"
    runs_data = []
    data_context = _get_data_context()

    preferred_summary = get_preferred_forecast()
    linear_summary = get_linear_forecast()
    arima_summary = get_arima_forecast()
    rnn_summary = get_rnn_forecast()

    if preferred_summary.latest_close is not None:
        latest_close = f"{preferred_summary.latest_close:,.2f}"
    if preferred_summary.next_step_forecast is not None:
        active_forecast = f"{preferred_summary.next_step_forecast:,.2f}"
    if preferred_summary.predicted_move_pct is not None:
        active_forecast_delta = f"{preferred_summary.predicted_move_pct:+.2f}%"
    active_forecast_change = _format_change_amount(preferred_summary)
    forecast_status = preferred_summary.model_source
    active_source_label = _summarize_model_source(forecast_status)
    if "LSTM" in forecast_status or "GRU" in forecast_status:
        active_model_updated = rnn_model_updated
    elif "ARIMA" in forecast_status:
        active_model_updated = arima_model_updated
    elif "linear regression" in forecast_status.lower():
        active_model_updated = linear_model_updated

    if linear_summary.next_step_forecast is not None:
        linear_forecast = f"{linear_summary.next_step_forecast:,.2f}"
    if linear_summary.predicted_move_pct is not None:
        linear_forecast_delta = f"{linear_summary.predicted_move_pct:+.2f}%"
    linear_forecast_change = _format_change_amount(linear_summary)
    linear_source_label = _summarize_model_source(linear_summary.model_source)

    if arima_summary.next_step_forecast is not None:
        arima_forecast = f"{arima_summary.next_step_forecast:,.2f}"
    if arima_summary.predicted_move_pct is not None:
        arima_forecast_delta = f"{arima_summary.predicted_move_pct:+.2f}%"
    arima_forecast_change = _format_change_amount(arima_summary)
    arima_status = arima_summary.model_source
    arima_source_label = _summarize_model_source(arima_summary.model_source)

    if rnn_summary.next_step_forecast is not None:
        rnn_forecast = f"{rnn_summary.next_step_forecast:,.2f}"
    if rnn_summary.predicted_move_pct is not None:
        rnn_forecast_delta = f"{rnn_summary.predicted_move_pct:+.2f}%"
    rnn_forecast_change = _format_change_amount(rnn_summary)
    rnn_status = rnn_summary.model_source
    rnn_source_label = _summarize_model_source(rnn_summary.model_source)

    collected_runs = []
    for experiment_name in DEFAULT_EXPERIMENTS:
        experiment = client.get_experiment_by_name(experiment_name)
        if not experiment:
            continue

        runs = client.search_runs(
            experiment_ids=[experiment.experiment_id],
            order_by=["attributes.start_time DESC"],
            max_results=5,
        )
        for run in runs:
            mse_value = _get_run_mse(run)
            collected_runs.append(
                {
                    "run_id": run.info.run_id,
                    "status": run.info.status,
                    "model_type": _normalize_model_type(run, experiment_name),
                    "mse": mse_value,
                    "start_time": pd.to_datetime(
                        run.info.start_time, unit="ms"
                    ).strftime("%Y-%m-%d %H:%M"),
                }
            )

    best_run_by_model = {}
    for run in collected_runs:
        model_type = run["model_type"]
        current_best = best_run_by_model.get(model_type)
        if current_best is None:
            best_run_by_model[model_type] = run
            continue

        current_mse = current_best["mse"] if current_best["mse"] is not None else float("inf")
        candidate_mse = run["mse"] if run["mse"] is not None else float("inf")
        if candidate_mse < current_mse:
            best_run_by_model[model_type] = run

    runs_data = sorted(
        best_run_by_model.values(),
        key=lambda run: (
            run["mse"] is None,
            run["mse"] if run["mse"] is not None else float("inf"),
        )
    )

    if runs_data and runs_data[0]["mse"] is not None:
        best_model_metric = f"{runs_data[0]['mse']:.6f}"
        best_model_name = runs_data[0]["model_type"]

    try:
        latest_versions = list(client.search_model_versions("name='BTCUSD_RNN_Model'"))
    except Exception:
        latest_versions = []

    context = {
        "latest_close": latest_close,
        "forecast_horizon": forecast_horizon,
        "active_forecast": active_forecast,
        "active_forecast_delta": active_forecast_delta,
        "active_forecast_change": active_forecast_change,
        "forecast_status": forecast_status,
        "active_source_label": active_source_label,
        "active_model_updated": active_model_updated,
        "active_validation": _format_validation(preferred_summary),
        "linear_forecast": linear_forecast,
        "linear_forecast_delta": linear_forecast_delta,
        "linear_forecast_change": linear_forecast_change,
        "linear_source_label": linear_source_label,
        "linear_model_updated": linear_model_updated,
        "linear_validation": _format_validation(linear_summary),
        "arima_forecast": arima_forecast,
        "arima_forecast_delta": arima_forecast_delta,
        "arima_forecast_change": arima_forecast_change,
        "arima_status": arima_status,
        "arima_source_label": arima_source_label,
        "arima_model_updated": arima_model_updated,
        "arima_validation": _format_validation(arima_summary),
        "rnn_forecast": rnn_forecast,
        "rnn_forecast_delta": rnn_forecast_delta,
        "rnn_forecast_change": rnn_forecast_change,
        "rnn_status": rnn_status,
        "rnn_source_label": rnn_source_label,
        "rnn_model_updated": rnn_model_updated,
        "rnn_validation": _format_validation(rnn_summary),
        "best_model_metric": best_model_metric,
        "best_model_name": best_model_name,
        "runs": runs_data,
        "latest_versions": latest_versions,
        "data_context": data_context,
    }

    return render(request, "dashboard/overview.html", context)


def drift_monitoring(request):
    data_context = _get_data_context()
    drift_snapshot = _get_drift_snapshot()
    context = {
        "data_context": data_context,
        "drift_snapshot": drift_snapshot,
    }
    return render(request, "dashboard/drift_monitoring.html", context)
