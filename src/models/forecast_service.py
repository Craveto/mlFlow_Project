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


@dataclass
class ForecastSummary:
    latest_close: float | None
    next_step_forecast: float | None
    predicted_move_pct: float | None
    model_ready: bool
    model_source: str
    latest_completed_prediction: float | None = None
    latest_completed_actual: float | None = None
    latest_completed_abs_error: float | None = None


def _empty_summary(message, latest_close=None):
    return ForecastSummary(latest_close, None, None, False, message)


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


def _latest_close(df):
    return float(df["Close"].iloc[-1]) if not df.empty and "Close" in df.columns else None


def get_linear_forecast(df=None):
    if df is None:
        if not PROCESSED_BTCUSD_CSV.exists():
            return _empty_summary("No processed data available.")
        df = pd.read_csv(PROCESSED_BTCUSD_CSV, index_col=0, parse_dates=True)

    latest_close = _latest_close(df)
    if not FORECAST_MODEL_BUNDLE.exists():
        return _empty_summary("Saved linear regression model not available.", latest_close)

    bundle = joblib.load(FORECAST_MODEL_BUNDLE)
    model = bundle["model"]
    features = bundle["features"]

    latest_row = df.dropna(subset=features)
    if latest_row.empty:
        return _empty_summary("Processed data is missing linear model features.", latest_close)

    latest_features = latest_row[features].iloc[[-1]]
    prediction = float(model.predict(latest_features)[0])
    predicted_move_pct = ((prediction - latest_close) / latest_close) * 100 if latest_close else None

    return ForecastSummary(
        latest_close,
        prediction,
        predicted_move_pct,
        True,
        "From saved linear regression model bundle",
        bundle.get("latest_completed_prediction"),
        bundle.get("latest_completed_actual"),
        bundle.get("latest_completed_abs_error"),
    )


def get_rnn_forecast(df=None):
    if df is None:
        if not PROCESSED_BTCUSD_CSV.exists():
            return _empty_summary("No processed data available.")
        df = pd.read_csv(PROCESSED_BTCUSD_CSV, index_col=0, parse_dates=True)

    latest_close = _latest_close(df)
    if not RNN_FORECAST_BUNDLE.exists():
        return _empty_summary("Saved RNN bundle not available.", latest_close)

    try:
        bundle = joblib.load(RNN_FORECAST_BUNDLE)
        scaler = bundle["scaler"]
        features = bundle["features"]
        window_size = bundle["window_size"]
        model_type = bundle.get("model_type", "RNN")
        units = bundle.get("units", 50)
        dropout = bundle.get("dropout", 0.2)
        weights = bundle["weights"]

        working_df = df.dropna(subset=features)
        if len(working_df) < window_size:
            return _empty_summary("Not enough rows for RNN inference window.", latest_close)

        scaled_data = scaler.transform(working_df[features])
        latest_sequence = np.array([scaled_data[-window_size:]])

        model = _build_rnn_model(
            (latest_sequence.shape[1], latest_sequence.shape[2]),
            model_type=model_type,
            units=units,
            dropout=dropout,
        )
        model.set_weights(weights)
        scaled_prediction = float(model.predict(latest_sequence, verbose=0)[0][0])

        restored_row = scaled_data[-1].copy()
        restored_row[0] = scaled_prediction
        prediction = float(scaler.inverse_transform([restored_row])[0][0])
        predicted_move_pct = ((prediction - latest_close) / latest_close) * 100 if latest_close else None

        return ForecastSummary(
            latest_close,
            prediction,
            predicted_move_pct,
            True,
            f"From saved {model_type} bundle",
            bundle.get("latest_completed_prediction"),
            bundle.get("latest_completed_actual"),
            bundle.get("latest_completed_abs_error"),
        )
    except Exception:
        return _empty_summary("Saved RNN bundle could not be loaded.", latest_close)


def get_arima_forecast(df=None):
    if df is None:
        if not PROCESSED_BTCUSD_CSV.exists():
            return _empty_summary("No processed data available.")
        df = pd.read_csv(PROCESSED_BTCUSD_CSV, index_col=0, parse_dates=True)

    latest_close = _latest_close(df)
    if not ARIMA_FORECAST_BUNDLE.exists():
        return _empty_summary("Saved ARIMA bundle not available.", latest_close)

    try:
        bundle = joblib.load(ARIMA_FORECAST_BUNDLE)
        model_fit = bundle["model_fit"]
        prediction = float(model_fit.forecast(steps=1).iloc[0])
        predicted_move_pct = ((prediction - latest_close) / latest_close) * 100 if latest_close else None

        return ForecastSummary(
            latest_close,
            prediction,
            predicted_move_pct,
            True,
            f"From saved ARIMA{bundle.get('order', '')} bundle",
            bundle.get("latest_completed_prediction"),
            bundle.get("latest_completed_actual"),
            bundle.get("latest_completed_abs_error"),
        )
    except Exception:
        return _empty_summary("Saved ARIMA bundle could not be loaded.", latest_close)


def get_preferred_forecast():
    if not PROCESSED_BTCUSD_CSV.exists():
        return _empty_summary("No processed data available.")

    df = pd.read_csv(PROCESSED_BTCUSD_CSV, index_col=0, parse_dates=True)
    if df.empty:
        return _empty_summary("No processed data available.")

    rnn_summary = get_rnn_forecast(df)
    if rnn_summary.model_ready:
        return rnn_summary

    arima_summary = get_arima_forecast(df)
    if arima_summary.model_ready:
        return arima_summary

    return get_linear_forecast(df)
