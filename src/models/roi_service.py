from dataclasses import dataclass

import joblib
import numpy as np
import pandas as pd
from tensorflow.keras.layers import LSTM, Dense, Dropout, GRU, Input
from tensorflow.keras.models import Sequential

from project_config import (
    ARIMA_FORECAST_BUNDLE,
    FORECAST_MODEL_BUNDLE,
    PROCESSED_BTCUSD_CSV,
    RNN_FORECAST_BUNDLE,
)


INITIAL_CAPITAL = 10_000.0
EVALUATION_HOURS = 24 * 7
SIGNAL_THRESHOLD = 0.0015
FEE_RATE = 0.0004
SIGNAL_QUANTILE = 0.65


@dataclass
class StrategyResult:
    model_name: str
    source_label: str
    period_label: str
    net_profit_usd: float
    return_pct: float
    trades: int
    win_rate_pct: float
    max_drawdown_pct: float
    risk_reduction_pct: float
    avg_predicted_edge_pct: float
    model_threshold_pct: float
    latest_signal: str
    sample_size: int
    benchmark_return_pct: float
    benchmark_profit_usd: float
    benchmark_drawdown_pct: float
    profit_vs_benchmark_usd: float
    signal_accuracy_pct: float
    long_trades: int
    short_trades: int
    window_start: pd.Timestamp
    window_end: pd.Timestamp


def _build_rnn_model(input_shape, model_type="LSTM", units=50, dropout=0.2):
    model = Sequential()
    model.add(Input(shape=input_shape))

    if model_type == "LSTM":
        model.add(LSTM(units=units, return_sequences=True))
        model.add(Dropout(dropout))
        model.add(LSTM(units=units, return_sequences=False))
        model.add(Dropout(dropout))
    else:
        model.add(GRU(units=units, return_sequences=True))
        model.add(Dropout(dropout))
        model.add(GRU(units=units, return_sequences=False))
        model.add(Dropout(dropout))

    model.add(Dense(units=25))
    model.add(Dense(units=1))
    model.compile(optimizer="adam", loss="mean_squared_error")
    return model


def _load_hourly_data():
    if not PROCESSED_BTCUSD_CSV.exists():
        return None
    df = pd.read_csv(PROCESSED_BTCUSD_CSV, index_col=0, parse_dates=True)
    if df.empty:
        return None
    return df.sort_index()


def _max_drawdown_pct(equity_curve):
    running_peak = equity_curve.cummax()
    drawdown = (equity_curve / running_peak) - 1
    return abs(float(drawdown.min()) * 100)


def _signal_from_predicted_return(predicted_return):
    if predicted_return > SIGNAL_THRESHOLD:
        return 1
    if predicted_return < -SIGNAL_THRESHOLD:
        return -1
    return 0


def _signal_label(signal_value):
    return {1: "Long", -1: "Short", 0: "Flat"}.get(int(signal_value), "Flat")


def _simulate_strategy(frame, model_name, source_label):
    if frame is None or frame.empty:
        return None

    working = frame.tail(EVALUATION_HOURS).copy()
    if working.empty:
        return None

    adaptive_threshold = max(
        SIGNAL_THRESHOLD / 10,
        float(working["predicted_return"].abs().quantile(SIGNAL_QUANTILE)),
    )
    working["signal"] = working["predicted_return"].apply(
        lambda predicted_return: _signal_from_predicted_return(
            predicted_return / adaptive_threshold * SIGNAL_THRESHOLD
        )
    )
    working["trade_return"] = working["signal"] * working["actual_return"] - np.where(
        working["signal"] != 0, FEE_RATE, 0.0
    )
    working["equity"] = INITIAL_CAPITAL * (1 + working["trade_return"]).cumprod()
    working["benchmark_equity"] = INITIAL_CAPITAL * (1 + working["actual_return"]).cumprod()

    executed = working[working["signal"] != 0]
    trade_count = int(len(executed))
    win_rate = float((executed["trade_return"] > 0).mean() * 100) if trade_count else 0.0
    signal_accuracy = (
        float(((np.sign(executed["predicted_return"]) == np.sign(executed["actual_return"])).mean()) * 100)
        if trade_count
        else 0.0
    )

    final_equity = float(working["equity"].iloc[-1])
    benchmark_final_equity = float(working["benchmark_equity"].iloc[-1])
    strategy_drawdown = _max_drawdown_pct(working["equity"])
    benchmark_drawdown = _max_drawdown_pct(working["benchmark_equity"])
    risk_reduction = (
        ((benchmark_drawdown - strategy_drawdown) / benchmark_drawdown) * 100
        if benchmark_drawdown > 0
        else 0.0
    )

    latest_signal_value = int(working["signal"].iloc[-1])
    return StrategyResult(
        model_name=model_name,
        source_label=source_label,
        period_label=f"Last {len(working)} Hours",
        net_profit_usd=final_equity - INITIAL_CAPITAL,
        return_pct=((final_equity / INITIAL_CAPITAL) - 1) * 100,
        trades=trade_count,
        win_rate_pct=win_rate,
        max_drawdown_pct=strategy_drawdown,
        risk_reduction_pct=risk_reduction,
        avg_predicted_edge_pct=float(working["predicted_return"].mean() * 100),
        model_threshold_pct=adaptive_threshold * 100,
        latest_signal=_signal_label(latest_signal_value),
        sample_size=int(len(working)),
        benchmark_return_pct=((benchmark_final_equity / INITIAL_CAPITAL) - 1) * 100,
        benchmark_profit_usd=benchmark_final_equity - INITIAL_CAPITAL,
        benchmark_drawdown_pct=benchmark_drawdown,
        profit_vs_benchmark_usd=(final_equity - benchmark_final_equity),
        signal_accuracy_pct=signal_accuracy,
        long_trades=int((executed["signal"] == 1).sum()),
        short_trades=int((executed["signal"] == -1).sum()),
        window_start=working.index[0],
        window_end=working.index[-1],
    )


def _linear_prediction_frame(df):
    if not FORECAST_MODEL_BUNDLE.exists():
        return None
    bundle = joblib.load(FORECAST_MODEL_BUNDLE)
    model = bundle["model"]
    features = bundle["features"]
    working = df.dropna(subset=features).copy()
    working["predicted_close"] = model.predict(working[features])
    working["next_close"] = working["Close"].shift(-1)
    working = working.dropna(subset=["predicted_close", "next_close"])
    working["predicted_return"] = (working["predicted_close"] / working["Close"]) - 1
    working["actual_return"] = (working["next_close"] / working["Close"]) - 1
    return working


def _arima_prediction_frame(df):
    if not ARIMA_FORECAST_BUNDLE.exists():
        return None
    bundle = joblib.load(ARIMA_FORECAST_BUNDLE)
    model_fit = bundle["model_fit"]
    series = df["Close"]
    if len(series) < 3:
        return None
    preds = model_fit.predict(start=1, end=len(series) - 1, dynamic=False)
    frame = pd.DataFrame(
        {
            "Close": series.iloc[:-1].values,
            "predicted_close": preds.values,
            "next_close": series.iloc[1:].values,
        },
        index=series.index[1:],
    )
    frame["predicted_return"] = (frame["predicted_close"] / frame["Close"]) - 1
    frame["actual_return"] = (frame["next_close"] / frame["Close"]) - 1
    return frame


def _rnn_prediction_frame(df):
    if not RNN_FORECAST_BUNDLE.exists():
        return None
    bundle = joblib.load(RNN_FORECAST_BUNDLE)
    scaler = bundle["scaler"]
    features = bundle["features"]
    window_size = bundle["window_size"]
    model_type = bundle.get("model_type", "RNN")
    units = bundle.get("units", 50)
    dropout = bundle.get("dropout", 0.2)
    weights = bundle["weights"]

    working = df.dropna(subset=features).copy()
    if len(working) <= window_size:
        return None

    scaled = scaler.transform(working[features])
    sequence_count = len(working) - window_size
    sequences = np.array(
        [scaled[start:start + window_size] for start in range(sequence_count)],
        dtype=np.float32,
    )

    model = _build_rnn_model((window_size, len(features)), model_type=model_type, units=units, dropout=dropout)
    model.set_weights(weights)
    scaled_predictions = model.predict(sequences, verbose=0).reshape(-1)

    restored_rows = scaled[window_size:].copy()
    restored_rows[:, 0] = scaled_predictions
    predicted_close = scaler.inverse_transform(restored_rows)[:, 0]
    current_close = working["Close"].iloc[window_size - 1:-1].to_numpy(dtype=float)
    next_close = working["Close"].iloc[window_size:].to_numpy(dtype=float)
    prediction_index = working.index[window_size:]

    frame = pd.DataFrame(
        {
            "Close": current_close,
            "predicted_close": predicted_close,
            "next_close": next_close,
        },
        index=prediction_index,
    )
    frame["predicted_return"] = (frame["predicted_close"] / frame["Close"]) - 1
    frame["actual_return"] = (frame["next_close"] / frame["Close"]) - 1
    return frame


def _build_recommendation(best_strategy):
    if best_strategy is None:
        return {
            "title": "No strategy available",
            "summary": "Generate the saved model bundles first so the ROI simulator has forecasts to replay.",
            "confidence_label": "Waiting",
        }

    delta_vs_benchmark = best_strategy.net_profit_usd - best_strategy.benchmark_profit_usd
    if best_strategy.net_profit_usd > 0 and delta_vs_benchmark > 0:
        confidence = "Deploy candidate"
        summary = (
            f"{best_strategy.model_name} is currently the strongest candidate because it beat buy-and-hold by "
            f"${delta_vs_benchmark:,.2f} over the latest {best_strategy.sample_size} hours after fees."
        )
    elif best_strategy.net_profit_usd > 0:
        confidence = "Watch closely"
        summary = (
            f"{best_strategy.model_name} stayed profitable, but it still trailed buy-and-hold by "
            f"${abs(delta_vs_benchmark):,.2f}. Good signal quality, weak monetization."
        )
    else:
        confidence = "Do not deploy"
        summary = (
            f"{best_strategy.model_name} lost ${abs(best_strategy.net_profit_usd):,.2f} in the replay window. "
            "The forecast may still be informative, but the current trade rule is not production-ready."
        )

    return {
        "title": best_strategy.model_name,
        "summary": summary,
        "confidence_label": confidence,
    }


def calculate_roi_dashboard():
    df = _load_hourly_data()
    assumptions = {
        "capital": INITIAL_CAPITAL,
        "threshold_pct": SIGNAL_THRESHOLD * 100,
        "fee_pct": FEE_RATE * 100,
        "window_hours": EVALUATION_HOURS,
        "signal_quantile_pct": SIGNAL_QUANTILE * 100,
    }
    if df is None:
        return {
            "best_strategy": None,
            "strategies": [],
            "assumptions": assumptions,
            "context": {},
            "recommendation": _build_recommendation(None),
        }

    strategies = []

    linear_frame = _linear_prediction_frame(df)
    if linear_frame is not None:
        result = _simulate_strategy(linear_frame, "Linear Regression", "Baseline")
        if result:
            strategies.append(result)

    arima_frame = _arima_prediction_frame(df)
    if arima_frame is not None:
        result = _simulate_strategy(arima_frame, "ARIMA", "Statistical")
        if result:
            strategies.append(result)

    rnn_frame = _rnn_prediction_frame(df)
    if rnn_frame is not None:
        source = joblib.load(RNN_FORECAST_BUNDLE).get("model_type", "RNN")
        result = _simulate_strategy(rnn_frame, source, "Neural")
        if result:
            strategies.append(result)

    strategies.sort(key=lambda item: item.net_profit_usd, reverse=True)
    best_strategy = strategies[0] if strategies else None

    return {
        "best_strategy": best_strategy,
        "strategies": strategies,
        "assumptions": assumptions,
        "context": {
            "coverage_start": df.index.min(),
            "coverage_end": df.index.max(),
            "latest_close": float(df["Close"].iloc[-1]),
            "bars": int(len(df)),
        },
        "recommendation": _build_recommendation(best_strategy),
    }
