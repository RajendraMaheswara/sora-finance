import pandas as pd
import numpy as np
import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    mean_absolute_error, mean_squared_error, r2_score, 
    mean_absolute_percentage_error, explained_variance_score
)
from config import Config
from modules.sales.forecaster import SalesForecaster

def get_upgraded_rf_model():
    return RandomForestRegressor(
        n_estimators=200, max_depth=15, min_samples_split=4, 
        min_samples_leaf=2, random_state=42, n_jobs=-1
    )

def calculate_metrics(y_true, y_pred):
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mape = 0 if (y_true == 0).any() else mean_absolute_percentage_error(y_true, y_pred) * 100
    r2 = r2_score(y_true, y_pred)
    ev = explained_variance_score(y_true, y_pred)
    return {"mae": round(mae, 4), "rmse": round(rmse, 4), "mape": round(mape, 4), "r2_score": round(r2, 4), "explained_variance": round(ev, 4)}

def train_all():
    Config.init_app()
    forecaster = SalesForecaster()
    
    # ==========================================
    # 1. TRAINING HARIAN
    # ==========================================
    print("=== MULAI TRAINING MODEL HARIAN ===")
    sales_daily = forecaster.fetch_data("sales-daily-summaries")
    if sales_daily:
        df = pd.DataFrame(sales_daily)
        df['date'] = pd.to_datetime(df['date'])
        models_dict = {}
        for store_id in df['m_store_id'].unique():
            df_s = df[df['m_store_id'] == store_id].copy().sort_values('date')
            df_s['day_of_week'] = df_s['date'].dt.dayofweek 
            df_s['month'] = df_s['date'].dt.month
            df_s['is_weekend'] = df_s['day_of_week'].apply(lambda x: 1 if x >= 5 else 0)
            df_s['total_discount'] = df_s.get('total_discount', 0).fillna(0)
            
            if len(df_s) < 15: continue

            fitur_x = ['day_of_week', 'month', 'is_weekend', 'total_discount']
            X, y = df_s[fitur_x], df_s['total_omzet']

            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
            rf_eval = get_upgraded_rf_model()
            rf_eval.fit(X_train, y_train)
            metrics = calculate_metrics(y_test, rf_eval.predict(X_test))

            rf_final = get_upgraded_rf_model()
            rf_final.fit(X, y)
            
            models_dict[store_id] = {"model": rf_final, "fitur_x": fitur_x, "last_date": df_s['date'].max(), "metrics": metrics}
            print(f"-> Model Harian Toko {store_id} selesai.")
        
        joblib.dump(models_dict, Config.DAILY_MODEL_PATH)
        print(f"-> Disimpan di {Config.DAILY_MODEL_PATH}")

    # ==========================================
    # 2. TRAINING BULANAN
    # ==========================================
    print("\n=== MULAI TRAINING MODEL BULANAN ===")
    sales_monthly = forecaster.fetch_data("sales-monthly-summaries")
    if sales_monthly:
        df_m = pd.DataFrame(sales_monthly)
        df_m['date'] = pd.to_datetime(df_m['date'])
        models_dict_m = {}
        for store_id in df_m['m_store_id'].unique():
            df_s = df_m[df_m['m_store_id'] == store_id].copy().sort_values('date')
            df_s['month'] = df_s['date'].dt.month
            df_s['quarter'] = df_s['date'].dt.quarter
            df_s['total_discount'] = df_s.get('total_discount', 0).fillna(0)
            
            if len(df_s) < 5: continue

            fitur_x = ['month', 'quarter', 'total_discount']
            X, y = df_s[fitur_x], df_s['total_omzet']

            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
            rf_eval = get_upgraded_rf_model()
            rf_eval.fit(X_train, y_train)
            metrics = calculate_metrics(y_test, rf_eval.predict(X_test))

            rf_final = get_upgraded_rf_model()
            rf_final.fit(X, y)
            
            models_dict_m[store_id] = {"model": rf_final, "fitur_x": fitur_x, "last_date": df_s['date'].max(), "metrics": metrics}
            print(f"-> Model Bulanan Toko {store_id} selesai.")
            
        joblib.dump(models_dict_m, Config.MONTHLY_MODEL_PATH)
        print(f"-> Disimpan di {Config.MONTHLY_MODEL_PATH}")

if __name__ == '__main__':
    train_all()