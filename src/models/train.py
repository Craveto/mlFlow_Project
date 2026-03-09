import pandas as pd
import numpy as np
import sys
from pathlib import Path
import joblib
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout, GRU, Input
from sklearn.preprocessing import MinMaxScaler
import mlflow
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from project_config import (
    PROCESSED_BTCUSD_CSV,
    RNN_FORECAST_BUNDLE,
    configure_mlflow,
)

import mlflow.tensorflow

# Set up MLflow
mlflow.set_tracking_uri(configure_mlflow())
mlflow.set_experiment("BTCUSD_Forecasting")

FEATURE_COLUMNS = ['Close', 'MA7', 'MA21', 'Return_1h', 'Volume']

def prepare_sequences(data, target_col='Close', window_size=60):
    """
    Prepare sequences for RNN training.
    """
    scaler = MinMaxScaler()
    scaled_data = scaler.fit_transform(data[FEATURE_COLUMNS])
    
    X, y = [], []
    for i in range(window_size, len(scaled_data)):
        X.append(scaled_data[i-window_size:i])
        y.append(scaled_data[i, 0])  # Predicting the next hour's close price
        
    return np.array(X), np.array(y), scaler

def build_model(input_shape, model_type='LSTM', units=50, dropout=0.2):
    """
    Build LSTM or GRU model using modern Keras Input object.
    """
    model = Sequential()
    model.add(Input(shape=input_shape))
    
    if model_type == 'LSTM':
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
    
    model.compile(optimizer='adam', loss='mean_squared_error')
    return model

def train_model(model_type='LSTM', window_size=60, epochs=1, batch_size=64, register_model=False):
    # Load processed data
    data_path = PROCESSED_BTCUSD_CSV
    if not data_path.exists():
        print(f"Error: {data_path} not found. Run ingestion.py first.")
        return

    df = pd.read_csv(data_path, index_col=0, parse_dates=True)
    # Take only the last 500 rows for faster training in sandbox verification
    df = df.tail(500)
    
    X, y, scaler = prepare_sequences(df, window_size=window_size)
    
    # Split data
    split = int(0.8 * len(X))
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    
    # MLflow tracking
    with mlflow.start_run():
        mlflow.log_param("model_type", model_type)
        mlflow.log_param("window_size", window_size)
        mlflow.log_param("epochs", epochs)
        mlflow.log_param("batch_size", batch_size)
        mlflow.log_param("features", FEATURE_COLUMNS)
        mlflow.log_param("register_model", register_model)
        
        model = build_model((X_train.shape[1], X_train.shape[2]), model_type=model_type)
        
        # Train
        history = model.fit(
            X_train, y_train,
            epochs=epochs,
            batch_size=batch_size,
            validation_data=(X_test, y_test),
            verbose=1
        )
        
        # Evaluate
        test_loss = model.evaluate(X_test, y_test)
        mlflow.log_metric("test_mse", test_loss)
        if history.history.get("loss"):
            mlflow.log_metric("train_loss", history.history["loss"][-1])
        if history.history.get("val_loss"):
            mlflow.log_metric("val_loss", history.history["val_loss"][-1])

        RNN_FORECAST_BUNDLE.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "scaler": scaler,
                "features": FEATURE_COLUMNS,
                "window_size": window_size,
                "model_type": model_type,
                "units": 50,
                "dropout": 0.2,
                "weights": model.get_weights(),
                "source_data": str(PROCESSED_BTCUSD_CSV),
                "target_horizon": "next_1_hour",
            },
            RNN_FORECAST_BUNDLE,
        )

        if len(df) > window_size:
            latest_completed_sequence = np.array([scaler.transform(df[FEATURE_COLUMNS])[-(window_size + 1):-1]])
            latest_completed_scaled_prediction = float(model.predict(latest_completed_sequence, verbose=0)[0][0])
            restored_row = scaler.transform(df[FEATURE_COLUMNS]).copy()[-1]
            restored_row[0] = latest_completed_scaled_prediction
            latest_completed_prediction = float(scaler.inverse_transform([restored_row])[0][0])
            latest_completed_actual = float(df["Close"].iloc[-1])
            bundle = joblib.load(RNN_FORECAST_BUNDLE)
            bundle["latest_completed_prediction"] = latest_completed_prediction
            bundle["latest_completed_actual"] = latest_completed_actual
            bundle["latest_completed_abs_error"] = abs(latest_completed_prediction - latest_completed_actual)
            joblib.dump(bundle, RNN_FORECAST_BUNDLE)

        model_uri = "Not registered"
        if register_model:
            try:
                model_info = mlflow.tensorflow.log_model(
                    model,
                    "model",
                    registered_model_name="BTCUSD_RNN_Model"
                )
                model_uri = model_info.model_uri
            except Exception as exc:
                print(f"MLflow model registration skipped: {exc}")
        
        print(f"Training complete. Test Loss (MSE): {test_loss}")
        print(f"Model registered as 'BTCUSD_RNN_Model' at: {model_uri}")
        print(f"RNN inference bundle saved to: {RNN_FORECAST_BUNDLE}")
        return model, history

if __name__ == "__main__":
    try:
        train_model(model_type='LSTM', epochs=1, register_model=False)
    except Exception as e:
        print(f"Training failed: {e}")
