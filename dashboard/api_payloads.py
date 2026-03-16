from datetime import datetime
from zoneinfo import ZoneInfo

import mlflow
import pandas as pd
from mlflow.tracking import MlflowClient

from dashboard.roi.models import ROIMetric
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
from src.models.roi_service import calculate_roi_dashboard


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
        return {"prediction": "N/A", "actual": "N/A", "error": "N/A"}
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


def build_data_context():
    context = {
        "data_source": "Yahoo Finance",
        "symbol": BTC_SYMBOL,
        "data_frequency": DATA_FREQUENCY_LABEL,
        "coverage_start": "N/A",
        "coverage_end": "N/A",
        "latest_market_time": "N/A",
        "dashboard_time": datetime.now(DISPLAY_TZ).strftime("%Y-%m-%d %I:%M %p IST"),
    }
    df = _load_processed_data()
    if df is None:
        return context

    index = pd.to_datetime(df.index)
    context["coverage_start"] = index.min().strftime("%Y-%m-%d %H:%M")
    context["coverage_end"] = index.max().strftime("%Y-%m-%d %H:%M")
    context["latest_market_time"] = index.max().strftime("%Y-%m-%d %H:%M")
    return context


def build_drift_payload():
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
    if df is not None and "Return_1h" in df.columns:
        working_df = df.dropna(subset=["Return_1h", "MA21", "Close"]).copy()
        if len(working_df) >= 168:
            latest_return = float(working_df["Return_1h"].iloc[-1] * 100)
            vol_24 = float(working_df["Return_1h"].tail(24).std() * 100)
            vol_168 = float(working_df["Return_1h"].tail(168).std() * 100)
            vol_ratio = vol_24 / vol_168 if vol_168 else 0
            price_vs_ma21 = float(((working_df["Close"].iloc[-1] / working_df["MA21"].iloc[-1]) - 1) * 100)
            latest_date = pd.to_datetime(working_df.index.max()).strftime("%Y-%m-%d %H:%M")
            if vol_ratio >= 1.8:
                snapshot["status"] = "Alert"
                snapshot["status_class"] = "danger"
                snapshot["summary"] = "Short-term hourly volatility is materially above the 7-day baseline."
            elif vol_ratio >= 1.3:
                snapshot["status"] = "Watch"
                snapshot["status_class"] = "warning"
                snapshot["summary"] = "Recent hourly volatility is rising. Monitor model stability closely."
            else:
                snapshot["status"] = "Stable"
                snapshot["status_class"] = "success"
                snapshot["summary"] = "Recent hourly volatility is still close to the baseline range."

            snapshot.update(
                {
                    "latest_return": f"{latest_return:+.2f}%",
                    "latest_volatility": f"{vol_24:.2f}%",
                    "volatility_ratio": f"{vol_ratio:.2f}x",
                    "price_vs_ma21": f"{price_vs_ma21:+.2f}%",
                    "latest_date": latest_date,
                }
            )
        else:
            snapshot["summary"] = "Not enough processed rows to evaluate an hourly drift window."

    return {
        "data_context": build_data_context(),
        "drift_snapshot": snapshot,
        "thresholds": {"stable": "Below 1.30x", "watch": "1.30x to 1.80x", "alert": "Above 1.80x"},
    }


def _serialize_forecast_summary(summary, updated_at=None):
    return {
        "forecast": f"{summary.next_step_forecast:,.2f}" if summary.next_step_forecast is not None else "N/A",
        "delta_pct": f"{summary.predicted_move_pct:+.2f}%" if summary.predicted_move_pct is not None else "N/A",
        "change_amount": _format_change_amount(summary),
        "status": summary.model_source,
        "source_label": _summarize_model_source(summary.model_source),
        "updated_at": updated_at or "Not generated",
        "validation": _format_validation(summary),
    }


def build_overview_payload():
    client = MlflowClient()
    preferred_summary = get_preferred_forecast()
    linear_summary = get_linear_forecast()
    arima_summary = get_arima_forecast()
    rnn_summary = get_rnn_forecast()

    linear_updated = _format_path_mtime(FORECAST_MODEL_BUNDLE)
    arima_updated = _format_path_mtime(ARIMA_FORECAST_BUNDLE)
    rnn_updated = _format_path_mtime(RNN_FORECAST_BUNDLE)
    active_updated = linear_updated
    active_source_label = _summarize_model_source(preferred_summary.model_source)
    if "LSTM" in preferred_summary.model_source or "GRU" in preferred_summary.model_source:
        active_updated = rnn_updated
    elif "ARIMA" in preferred_summary.model_source:
        active_updated = arima_updated

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
                    "mse": round(mse_value, 6) if mse_value is not None else None,
                    "start_time": pd.to_datetime(run.info.start_time, unit="ms").strftime("%Y-%m-%d %H:%M"),
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
        key=lambda run: (run["mse"] is None, run["mse"] if run["mse"] is not None else float("inf")),
    )

    best_model_metric = "N/A"
    best_model_name = "N/A"
    if runs_data and runs_data[0]["mse"] is not None:
        best_model_metric = f"{runs_data[0]['mse']:.6f}"
        best_model_name = runs_data[0]["model_type"]

    try:
        latest_versions = list(client.search_model_versions("name='BTCUSD_RNN_Model'"))
    except Exception:
        latest_versions = []

    return {
        "data_context": build_data_context(),
        "forecast_horizon": FORECAST_HORIZON_LABEL,
        "forecast_cards": {
            "active": {
                "forecast_horizon": FORECAST_HORIZON_LABEL,
                "latest_close": f"{preferred_summary.latest_close:,.2f}" if preferred_summary.latest_close is not None else "N/A",
                **_serialize_forecast_summary(preferred_summary, active_updated),
                "source_label": active_source_label,
            },
            "linear": _serialize_forecast_summary(linear_summary, linear_updated),
            "arima": _serialize_forecast_summary(arima_summary, arima_updated),
            "rnn": _serialize_forecast_summary(rnn_summary, rnn_updated),
        },
        "best_model_metric": best_model_metric,
        "best_model_name": best_model_name,
        "runs": runs_data,
        "registry_versions": [
            {"version": version.version, "stage": version.current_stage or "Unstaged", "name": version.name}
            for version in latest_versions
        ],
    }


def build_forecast_payload():
    overview = build_overview_payload()
    return {
        "forecast_horizon": overview["forecast_horizon"],
        "forecast_cards": overview["forecast_cards"],
        "best_model_metric": overview["best_model_metric"],
        "best_model_name": overview["best_model_name"],
    }


def _serialize_timestamp(value):
    if value is None:
        return None
    return value.strftime("%Y-%m-%d %H:%M")


def _serialize_strategy(strategy):
    if strategy is None:
        return None
    return {
        "model_name": strategy.model_name,
        "source_label": strategy.source_label,
        "period_label": strategy.period_label,
        "net_profit_usd": round(strategy.net_profit_usd, 2),
        "return_pct": round(strategy.return_pct, 2),
        "trades": strategy.trades,
        "win_rate_pct": round(strategy.win_rate_pct, 1),
        "max_drawdown_pct": round(strategy.max_drawdown_pct, 2),
        "risk_reduction_pct": round(strategy.risk_reduction_pct, 1),
        "avg_predicted_edge_pct": round(strategy.avg_predicted_edge_pct, 3),
        "model_threshold_pct": round(strategy.model_threshold_pct, 3),
        "latest_signal": strategy.latest_signal,
        "sample_size": strategy.sample_size,
        "benchmark_return_pct": round(strategy.benchmark_return_pct, 2),
        "benchmark_profit_usd": round(strategy.benchmark_profit_usd, 2),
        "benchmark_drawdown_pct": round(strategy.benchmark_drawdown_pct, 2),
        "profit_vs_benchmark_usd": round(strategy.profit_vs_benchmark_usd, 2),
        "signal_accuracy_pct": round(strategy.signal_accuracy_pct, 1),
        "long_trades": strategy.long_trades,
        "short_trades": strategy.short_trades,
        "window_start": _serialize_timestamp(strategy.window_start),
        "window_end": _serialize_timestamp(strategy.window_end),
    }


def build_roi_payload():
    roi_dashboard = calculate_roi_dashboard()
    context_data = roi_dashboard["context"]
    return {
        "best_strategy": _serialize_strategy(roi_dashboard["best_strategy"]),
        "strategies": [_serialize_strategy(strategy) for strategy in roi_dashboard["strategies"]],
        "assumptions": roi_dashboard["assumptions"],
        "context_data": {
            "coverage_start": _serialize_timestamp(context_data.get("coverage_start")) if context_data else None,
            "coverage_end": _serialize_timestamp(context_data.get("coverage_end")) if context_data else None,
            "latest_close": round(context_data.get("latest_close", 0), 2) if context_data and context_data.get("latest_close") is not None else None,
            "bars": context_data.get("bars") if context_data else 0,
        },
        "recommendation": roi_dashboard["recommendation"],
        "history": [
            {
                "model_version": entry.model_version,
                "period": entry.period,
                "simulated_profit_usd": round(entry.simulated_profit_usd, 2),
                "risk_reduction_pct": round(entry.risk_reduction_pct, 1),
                "calculated_at": entry.calculated_at.strftime("%Y-%m-%d %H:%M"),
            }
            for entry in ROIMetric.objects.all().order_by("-calculated_at")[:10]
        ],
    }
