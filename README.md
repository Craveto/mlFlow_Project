# BTCUSD 1-Hour Forecasting Dashboard

This project combines a small BTCUSD forecasting pipeline with a Django dashboard.

## What the project does

- Downloads hourly BTC-USD historical price data from Yahoo Finance
- Preprocesses the data into model features
- Trains forecasting models and logs runs to MLflow
- Saves local inference bundles for dashboard predictions
- Shows forecast and experiment information in a Django dashboard

## Current architecture

### Data flow

```text
yfinance (1h)
  -> data/raw/btc-usd_1h_historical.csv
  -> data/processed/btcusd_1h_processed.csv
  -> model training
  -> mlflow.db + artifacts/
  -> Django dashboard
```

### Important folders

- `src/data/ingestion.py`
  Downloads hourly BTCUSD data and builds processed features.
- `src/models/linear_regression.py`
  Trains the baseline forecast model, logs to MLflow, and saves the local inference bundle.
- `src/models/arima_model.py`
  Trains the ARIMA baseline and saves the ARIMA inference bundle.
- `src/models/train.py`
  Trains the RNN model, logs to MLflow, and saves the RNN inference bundle.
- `src/models/forecast_service.py`
  Loads the saved forecast bundles and performs dashboard inference.
- `dashboard/`
  Django project and apps for monitoring, A/B testing, and ROI views.
- `project_config.py`
  Shared absolute paths and MLflow tracking configuration.
- `run_project.py`
  One-command bootstrap and startup script.

## What was fixed

The project previously showed empty values in the dashboard because:

- Django was reading a different MLflow database than the training scripts
- the forecast card was hardcoded to `N/A`
- duplicate app names at the repo root and inside `dashboard/` made imports fragile

The project now uses one shared MLflow location from `project_config.py`, and Django is configured to use the dashboard apps explicitly as:

- `dashboard.monitoring`
- `dashboard.ab_testing`
- `dashboard.roi`

## Forecasting pipeline

### Data ingestion

Run:

```bash
python src/data/ingestion.py
```

This script:

- downloads BTC-USD data using `yfinance`
- uses Yahoo Finance period `730d` and interval `1h`
- saves raw data to `data/raw/btc-usd_1h_historical.csv`
- creates features like `MA7`, `MA21`, and `Return_1h`
- saves processed data to `data/processed/btcusd_1h_processed.csv`

### Model training

Run:

```bash
python src/models/linear_regression.py
```

This script:

- reads `data/processed/btcusd_1h_processed.csv`
- trains a `StandardScaler + LinearRegression` pipeline
- logs run metrics to the shared `mlflow.db`
- registers the model in MLflow
- saves a reusable local inference bundle to `artifacts/linear_regression_forecast.joblib`
- stores a latest-completed 1-hour validation check in the bundle

The dashboard forecast card now uses that saved bundle. It does not retrain on every page load.

### RNN model training

Run:

```bash
python src/models/train.py
```

This script:

- reads `data/processed/btcusd_1h_processed.csv`
- creates rolling sequences using the last `window_size` rows
- trains an LSTM or GRU model to predict the next hour
- logs run metrics to the shared `mlflow.db`
- saves a compact scaler/config/weights bundle to `artifacts/rnn_forecast_bundle.joblib`
- stores a latest-completed 1-hour validation check in the bundle

The dashboard forecast service prefers the saved RNN bundle when it exists. If it is missing, the dashboard falls back to the saved linear regression bundle.

### ARIMA model training

Run:

```bash
python src/models/arima_model.py
```

This script:

- reads `data/processed/btcusd_1h_processed.csv`
- trains an `ARIMA(p,d,q)` model on the `Close` series
- logs ARIMA metrics to the shared `mlflow.db`
- saves a reusable ARIMA inference bundle to `artifacts/arima_forecast_bundle.joblib`
- stores a latest-completed 1-hour validation check in the bundle

The dashboard can load this saved ARIMA bundle directly and show the ARIMA next-step forecast.

## Dashboard

Run:

```bash
python dashboard/manage.py runserver
```

Dashboard overview now shows:

- active next-1-hour forecast
- RNN forecast
- ARIMA forecast
- linear forecast
- data source, coverage window, latest market date, and dashboard refresh time
- model bundle update timestamps on each forecast card
- a larger active-forecast hero card with change vs close and model source
- a latest-completed 1-hour validation check showing predicted vs actual next hour
- cleaner comparison cards for RNN, ARIMA, linear, and best-model quality
- latest hourly BTC close
- predicted move percentage
- best model MSE from MLflow
- best run per model
- registered model versions

The `/monitoring/` page now works as a dedicated drift-monitoring screen and uses the same theme as the overview page.

The `/ab-testing/` page now works as a lightweight A/B experiment workspace where you can create a new test from control/treatment MSE values and close active tests from the UI.

The `/roi/` page now works as a real hourly strategy replay instead of a placeholder KPI screen. It:

- replays the saved Linear Regression, ARIMA, and GRU/LSTM bundles over the latest 168 hourly bars
- converts forecasts into long, short, or flat decisions
- applies a confidence gate per model based on recent predicted-move strength
- charges a flat trading fee on executed trades
- compares each strategy against buy-and-hold on profit and drawdown
- saves best-strategy snapshots into the ROI history panel

## Easiest way to run everything

Use:

```bash
python run_project.py
```

This command will:

- run Django migrations
- create processed BTCUSD data if missing
- train the baseline linear regression model if the saved forecast bundle is missing
- start the dashboard at `http://127.0.0.1:8000/`

To bootstrap with the RNN bundle as well:

```bash
python run_project.py --prefer-rnn
```

To bootstrap with ARIMA as well:

```bash
python run_project.py --prefer-arima
```

## Manual run order

If you want to run the project step by step:

```bash
python src/data/ingestion.py
python src/models/linear_regression.py
python dashboard/manage.py runserver
```

Optional:

```bash
python src/models/arima_model.py
python src/models/train.py
```

## Dependencies

Install dependencies with:

```bash
pip install -r requirements.txt
```

## Notes

- `mlflow.db` in the project root is the shared MLflow store used by both training and Django.
- `dashboard/mlflow.db` is no longer the source of truth for experiments.
- The current dashboard forecast uses the saved linear regression bundle because it is the most reliable inference path in the current codebase.
- The dashboard forecast service now prefers the saved RNN bundle, then the saved ARIMA bundle, and finally the saved linear regression bundle.
- The dashboard run table shows the best saved/tracked run for each model type so LSTM rows do not hide GRU, ARIMA, and linear regression runs.
- The A/B testing page uses a simple rule: lower MSE wins, and challenger uplift is calculated from control vs treatment MSE.
- The drift monitoring page uses a simple heuristic based on recent daily-return volatility and distance from the 21-day moving average.
- The drift monitoring page now uses hourly-return volatility, comparing the last 24 hours against the last 7 days.
- The ROI page focuses on business impact instead of forecast accuracy alone; a model can have decent MSE and still underperform once fees and trade gating are applied.
- On this machine, MLflow model registration can fail because of a Windows temp-directory permission issue. The local saved inference bundle is therefore the primary serving artifact for the dashboard.
- If an RNN bundle is missing or cannot be loaded, the dashboard automatically falls back to the saved linear regression bundle instead of failing.
