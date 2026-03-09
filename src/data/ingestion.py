import yfinance as yf
import pandas as pd
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from project_config import PROCESSED_BTCUSD_CSV, RAW_BTCUSD_CSV
from project_config import BTC_SYMBOL, YFINANCE_INTERVAL, YFINANCE_PERIOD

def download_btcusd_data(symbol=BTC_SYMBOL, period=YFINANCE_PERIOD, interval=YFINANCE_INTERVAL):
    """
    Downloads historical BTC-USD data from Yahoo Finance.
    """
    print(f"Downloading data for {symbol}...")
    try:
        # Fetch data and reset index to handle MultiIndex columns
        data = yf.download(symbol, period=period, interval=interval)
        if data.empty:
            raise ValueError("Downloaded data is empty.")
        
        # Yahoo Finance returns MultiIndex for columns if single ticker is used sometimes, 
        # or just standard columns. Let's flatten if needed.
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
            
        RAW_BTCUSD_CSV.parent.mkdir(parents=True, exist_ok=True)
        
        # Save to CSV
        data.to_csv(RAW_BTCUSD_CSV)
        print(f"Data saved to {RAW_BTCUSD_CSV}")
        return data
    except Exception as e:
        print(f"Error downloading data: {e}")
        return None

def preprocess_data(df):
    """
    Basic preprocessing: handling missing values and ensuring correct types.
    """
    if df is None:
        return None
    
    # Fill missing values if any
    df = df.ffill()
    
    # Build hourly features from the latest available candles.
    df['MA7'] = df['Close'].rolling(window=7).mean()
    df['MA21'] = df['Close'].rolling(window=21).mean()
    df['Return_1h'] = df['Close'].pct_change()
    
    # Drop rows with NaN from rolling calculations
    df = df.dropna()
    
    PROCESSED_BTCUSD_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(PROCESSED_BTCUSD_CSV)
    print(f"Processed data saved to {PROCESSED_BTCUSD_CSV}")
    return df

if __name__ == "__main__":
    raw_data = download_btcusd_data()
    if raw_data is not None:
        processed_data = preprocess_data(raw_data)
        print("Data Ingestion and Preprocessing Complete.")
