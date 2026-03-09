from pathlib import Path
import os
import sys


PROJECT_ROOT = Path(__file__).resolve().parent
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
DATA_DIR = PROJECT_ROOT / "data"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
BTC_SYMBOL = "BTC-USD"
YFINANCE_PERIOD = "730d"
YFINANCE_INTERVAL = "1h"
FORECAST_HORIZON_LABEL = "Next 1 Hour"
DATA_FREQUENCY_LABEL = "1-hour candles"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
RAW_BTCUSD_CSV = RAW_DATA_DIR / "btc-usd_1h_historical.csv"
PROCESSED_BTCUSD_CSV = PROCESSED_DATA_DIR / "btcusd_1h_processed.csv"
FORECAST_MODEL_BUNDLE = ARTIFACTS_DIR / "linear_regression_forecast.joblib"
RNN_FORECAST_BUNDLE = ARTIFACTS_DIR / "rnn_forecast_bundle.joblib"
ARIMA_FORECAST_BUNDLE = ARTIFACTS_DIR / "arima_forecast_bundle.joblib"
MLFLOW_DB_PATH = PROJECT_ROOT / "mlflow.db"
MLFLOW_TRACKING_URI = f"sqlite:///{MLFLOW_DB_PATH.as_posix()}"
DEFAULT_EXPERIMENTS = [
    "BTCUSD_Forecasting",
    "BTCUSD_Linear_Regression",
    "BTCUSD_ARIMA_Forecasting",
]
DEFAULT_REGISTERED_MODELS = [
    "BTCUSD_RNN_Model",
    "BTCUSD_Linear_Regression",
]


def ensure_project_root_on_path():
    project_root = str(PROJECT_ROOT)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


def configure_mlflow():
    os.environ.setdefault("MLFLOW_TRACKING_URI", MLFLOW_TRACKING_URI)
    return MLFLOW_TRACKING_URI
