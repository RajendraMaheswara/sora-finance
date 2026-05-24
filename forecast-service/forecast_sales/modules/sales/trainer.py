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

def get_optimized_rf_model():
    return RandomForestRegressor(
        n_estimators=250, max_depth=12, min_samples_split=5, 
        min_samples_leaf=3, random_state=42, n_jobs=-1
    )

def calculate_advanced_metrics(y_true, y_pred):
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    if (y_true == 0).any():
        non_zero_mask = y_true != 0
        mape = np.mean(np.abs((y_true[non_zero_mask] - y_pred[non_zero_mask]) / y_true[non_zero_mask])) * 100 if non_zero_mask.sum() > 0 else 20.0
    else:
        mape = mean_absolute_percentage_error(y_true, y_pred) * 100
    r2 = r2_score(y_true, y_pred)
    ev = explained_variance_score(y_true, y_pred)
    return {"mae": round(float(mae), 3), "rmse": round(float(rmse), 3), "mape": round(float(mape), 4), "r2_score": round(float(r2), 4), "explained_variance": round(float(ev), 4)}

def train_all():
    Config.init_app()
    forecaster = SalesForecaster()
    
    # Ambil Data Harian (Akan dipakai untuk Daily dan di-resample untuk Weekly)
    sales_daily = forecaster.fetch_data("sales-daily-summaries")
    
    # ==========================================
    # 1. TRAINING HARIAN
    # ==========================================
    print("=== [TRAINER] MULAI TRAINING HARIAN (DAILY) ===")
    if sales_daily:
        df_d = pd.DataFrame(sales_daily)
        df_d['date'] = pd.to_datetime(df_d['date'])
        daily_models_dict = {}
        
        for store_id in df_d['m_store_id'].unique():
            df_s = df_d[df_d['m_store_id'] == store_id].copy().sort_values('date')
            df_s['day_of_week'] = df_s['date'].dt.dayofweek 
            df_s['month'] = df_s['date'].dt.month
            df_s['is_weekend'] = df_s['day_of_week'].apply(lambda x: 1 if x >= 5 else 0)
            df_s['day_of_month'] = df_s['date'].dt.day
            df_s['is_payday'] = df_s['day_of_month'].apply(lambda x: 1 if (x >= 25 or x <= 5) else 0)
            df_s['total_discount'] = df_s.get('total_discount', 0).fillna(0)
            
            if len(df_s) < 15: continue

            fitur_x = ['day_of_week', 'month', 'is_weekend', 'is_payday', 'total_discount']
            X, y = df_s[fitur_x], df_s['total_omzet']

            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
            rf_eval = get_optimized_rf_model()
            rf_eval.fit(X_train, y_train)
            metrics = calculate_advanced_metrics(y_test, rf_eval.predict(X_test))

            rf_final = get_optimized_rf_model()
            rf_final.fit(X, y)
            
            daily_models_dict[store_id] = {"model": rf_final, "fitur_x": fitur_x, "last_date": df_s['date'].max(), "metrics": metrics}
            print(f"   -> Daily: Toko {store_id} selesai (R2: {metrics['r2_score']})")
        joblib.dump(daily_models_dict, Config.DAILY_MODEL_PATH)
        print(f"==> Tersimpan di {Config.DAILY_MODEL_PATH}\n")

    # ==========================================
    # 2. TRAINING MINGGUAN (Dari Resample Harian)
    # ==========================================
    print("=== [TRAINER] MULAI TRAINING MINGGUAN (WEEKLY) ===")
    if sales_daily:
        weekly_models_dict = {}
        for store_id in df_d['m_store_id'].unique():
            df_s = df_d[df_d['m_store_id'] == store_id].copy()
            # Set index ke date untuk melakukan Resampling mingguan (W-MON berarti awal minggu di Senin)
            df_s.set_index('date', inplace=True)
            
            # Resample: Jumlahkan omzet per minggu
            df_w = df_s.resample('W-MON').agg({'total_omzet': 'sum', 'total_discount': 'sum'}).reset_index()
            
            # Feature Engineering Mingguan
            df_w['week_of_year'] = df_w['date'].dt.isocalendar().week
            df_w['month'] = df_w['date'].dt.month
            
            if len(df_w) < 5: 
                print(f"   -> [SKIP] Weekly Toko {store_id} (Data kurang dari 5 minggu)")
                continue

            fitur_x = ['week_of_year', 'month', 'total_discount']
            X, y = df_w[fitur_x], df_w['total_omzet']

            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
            rf_eval = get_optimized_rf_model()
            rf_eval.fit(X_train, y_train)
            metrics = calculate_advanced_metrics(y_test, rf_eval.predict(X_test))

            rf_final = get_optimized_rf_model()
            rf_final.fit(X, y)
            
            weekly_models_dict[store_id] = {"model": rf_final, "fitur_x": fitur_x, "last_date": df_w['date'].max(), "metrics": metrics}
            print(f"   -> Weekly: Toko {store_id} selesai (R2: {metrics['r2_score']})")
            
        joblib.dump(weekly_models_dict, Config.WEEKLY_MODEL_PATH)
        print(f"==> Tersimpan di {Config.WEEKLY_MODEL_PATH}\n")

    # ==========================================
    # 3. TRAINING BULANAN
    # ==========================================
    print("=== [TRAINER] MULAI TRAINING BULANAN (MONTHLY) ===")
    sales_monthly = forecaster.fetch_data("sales-monthly-summaries")
    if sales_monthly:
        df_m = pd.DataFrame(sales_monthly)
        df_m['date'] = pd.to_datetime(df_m['date'])
        monthly_models_dict = {}
        for store_id in df_m['m_store_id'].unique():
            df_s = df_m[df_m['m_store_id'] == store_id].copy().sort_values('date')
            df_s['month'] = df_s['date'].dt.month
            df_s['quarter'] = df_s['date'].dt.quarter
            df_s['total_discount'] = df_s.get('total_discount', 0).fillna(0)
            
            if len(df_s) < 5: continue

            fitur_x = ['month', 'quarter', 'total_discount']
            X, y = df_s[fitur_x], df_s['total_omzet']

            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
            rf_eval = get_optimized_rf_model()
            rf_eval.fit(X_train, y_train)
            metrics = calculate_advanced_metrics(y_test, rf_eval.predict(X_test))

            rf_final = get_optimized_rf_model()
            rf_final.fit(X, y)
            
            monthly_models_dict[store_id] = {"model": rf_final, "fitur_x": fitur_x, "last_date": df_s['date'].max(), "metrics": metrics}
            print(f"   -> Monthly: Toko {store_id} selesai (R2: {metrics['r2_score']})")
            
        joblib.dump(monthly_models_dict, Config.MONTHLY_MODEL_PATH)
        print(f"==> Tersimpan di {Config.MONTHLY_MODEL_PATH}\n")

if __name__ == '__main__':
    train_all()