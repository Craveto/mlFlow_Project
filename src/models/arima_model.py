import pandas as pd
import numpy as np
import sys
from pathlib import Path
import joblib
from statsmodels.tsa.arima.model import ARIMA
from sklearn.metrics import mean_squared_error
import mlflow
import mlflow.sklearn
import warnings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from project_config import ARIMA_FORECAST_BUNDLE, PROCESSED_BTCUSD_CSV, configure_mlflow

# Set up MLflow
mlflow.set_tracking_uri(configure_mlflow())
mlflow.set_experiment("BTCUSD_ARIMA_Forecasting")

# Suppress ARIMA warnings
warnings.filterwarnings("ignore")

def train_arima_model(p=5, d=1, q=0):
    """
    Trains an ARIMA model on BTCUSD Close price.
    p: Lag order
    d: Degree of differencing
    q: Order of moving average
    """
    # Load processed data
    data_path = PROCESSED_BTCUSD_CSV
    if not data_path.exists():
        print(f"Error: {data_path} not found. Run ingestion.py first.")
        return

    df = pd.read_csv(data_path, index_col=0, parse_dates=True)
    
    # ARIMA uses univariate time series
    series = df['Close']
    
    # Split data (80% train, 20% test)
    split_point = int(len(series) * 0.8)
    train, test = series[0:split_point], series[split_point:]
    
    with mlflow.start_run(run_name="ARIMA_Model"):
        # Log parameters
        mlflow.log_param("model_type", "ARIMA")
        mlflow.log_param("p", p)
        mlflow.log_param("d", d)
        mlflow.log_param("q", q)
        
        # Fit model
        print(f"Training ARIMA({p},{d},{q})...")
        model = ARIMA(train, order=(p, d, q))
        model_fit = model.fit()
        
        # Forecast
        forecast_result = model_fit.forecast(steps=len(test))
        predictions = forecast_result
        
        # Calculate MSE
        mse = mean_squared_error(test, predictions)
        
        # Log metrics
        mlflow.log_metric("mse", mse)

        serving_fit = ARIMA(series, order=(p, d, q)).fit()
        latest_completed_prediction = None
        latest_completed_actual = None
        latest_completed_abs_error = None
        if len(series) > 30:
            eval_fit = ARIMA(series.iloc[:-1], order=(p, d, q)).fit()
            latest_completed_prediction = float(eval_fit.forecast(steps=1).iloc[0])
            latest_completed_actual = float(series.iloc[-1])
            latest_completed_abs_error = abs(latest_completed_prediction - latest_completed_actual)

        ARIMA_FORECAST_BUNDLE.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "model_fit": serving_fit,
                "order": (p, d, q),
                "source_data": str(PROCESSED_BTCUSD_CSV),
                "target_horizon": "next_1_hour",
                "latest_completed_prediction": latest_completed_prediction,
                "latest_completed_actual": latest_completed_actual,
                "latest_completed_abs_error": latest_completed_abs_error,
            },
            ARIMA_FORECAST_BUNDLE,
        )
        
        # Log model (Note: logging statsmodels objects directly can be tricky with mlflow.sklearn, 
        # so we often save it as a generic python function or artifact, but here we try basic logging)
        # For simplicity in this demo, we'll log the parameters and metrics primarily.
        
        print(f"ARIMA Training complete.")
        print(f"MSE: {mse:.4f}")
        print(f"ARIMA inference bundle saved to: {ARIMA_FORECAST_BUNDLE}")
        
        return model_fit, mse

if __name__ == "__main__":
    try:
        train_arima_model()
    except Exception as e:
        print(f"Training failed: {e}")
