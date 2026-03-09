import pandas as pd
import numpy as np
import joblib
import sys
from pathlib import Path
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, mean_absolute_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import mlflow
import mlflow.sklearn
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from project_config import FORECAST_MODEL_BUNDLE, PROCESSED_BTCUSD_CSV, configure_mlflow


FEATURE_COLUMNS = ['Close', 'MA7', 'MA21', 'Return_1h', 'Volume']

# Set up MLflow
mlflow.set_tracking_uri(configure_mlflow())
mlflow.set_experiment("BTCUSD_Linear_Regression")

def train_linear_regression(test_size=0.2):
    """
    Trains a Linear Regression model to predict the next hour's Close price.
    Uses 'Close', 'MA7', 'MA21', 'Return_1h', 'Volume' as features.
    """
    # Load processed data
    data_path = PROCESSED_BTCUSD_CSV
    if not data_path.exists():
        print(f"Error: {data_path} not found. Run ingestion.py first.")
        return

    df = pd.read_csv(data_path, index_col=0, parse_dates=True)
    
    # Feature Engineering for Linear Regression
    # Predict the next hour's close using the current hour's features.
    df['Target'] = df['Close'].shift(-1)
    df = df.dropna()
    
    X = df[FEATURE_COLUMNS]
    y = df['Target']
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, shuffle=False)
    
    with mlflow.start_run(run_name="Linear_Regression_Baseline"):
        # Log parameters
        mlflow.log_param("model_type", "LinearRegression")
        mlflow.log_param("test_size", test_size)
        mlflow.log_param("features", FEATURE_COLUMNS)
        
        # Train model
        model = Pipeline(
            steps=[
                ("scaler", StandardScaler()),
                ("regressor", LinearRegression()),
            ]
        )
        model.fit(X_train, y_train)
        
        # Predict
        predictions = model.predict(X_test)
        
        # Metrics
        mse = mean_squared_error(y_test, predictions)
        mae = mean_absolute_error(y_test, predictions)
        
        # Log metrics
        mlflow.log_metric("mse", mse)
        mlflow.log_metric("mae", mae)
        
        FORECAST_MODEL_BUNDLE.parent.mkdir(parents=True, exist_ok=True)
        bundle = {
            "model": model,
            "features": FEATURE_COLUMNS,
            "target": "Target",
            "source_data": str(PROCESSED_BTCUSD_CSV),
            "target_horizon": "next_1_hour",
        }

        if len(df) >= 2:
            latest_completed_features = df[FEATURE_COLUMNS].iloc[[-2]]
            latest_completed_prediction = float(model.predict(latest_completed_features)[0])
            latest_completed_actual = float(df["Close"].iloc[-1])
            bundle["latest_completed_prediction"] = latest_completed_prediction
            bundle["latest_completed_actual"] = latest_completed_actual
            bundle["latest_completed_abs_error"] = abs(latest_completed_prediction - latest_completed_actual)
        joblib.dump(bundle, FORECAST_MODEL_BUNDLE)

        model_uri = "Not registered"
        try:
            model_info = mlflow.sklearn.log_model(
                model,
                "model",
                registered_model_name="BTCUSD_Linear_Regression"
            )
            model_uri = model_info.model_uri
        except Exception as exc:
            print(f"MLflow model registration skipped: {exc}")
        
        print(f"Linear Regression Training complete.")
        print(f"MSE: {mse:.4f}, MAE: {mae:.4f}")
        print(f"Model registered as 'BTCUSD_Linear_Regression' at: {model_uri}")
        print(f"Local inference bundle saved to: {FORECAST_MODEL_BUNDLE}")
        
        return model, mse, mae

if __name__ == "__main__":
    try:
        train_linear_regression()
    except Exception as e:
        print(f"Training failed: {e}")
