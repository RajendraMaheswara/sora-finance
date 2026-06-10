import pandas as pd
import numpy as np
import joblib
import os
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import (
    mean_absolute_error, mean_squared_error, r2_score, 
    mean_absolute_percentage_error, explained_variance_score
)
from config import Config
from modules.sales.forecaster import SalesForecaster

def get_global_rf_model():
    # Model Global raksasa
    return RandomForestRegressor(
        n_estimators=300, max_depth=16, min_samples_split=4, 
        min_samples_leaf=2, random_state=42, n_jobs=-1
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
    GLOBAL_MODEL_PATH = os.path.join(os.path.dirname(Config.DAILY_MODEL_PATH), 'models_rf_global.joblib')
    
    # Ambil Data Harian
    sales_daily = forecaster.fetch_data("sales-daily-summaries")
    
    print("=== [TRAINER] MULAI TRAINING GLOBAL MODEL (DNA STORE PROFILING) ===")
    if sales_daily:
        df_d = pd.DataFrame(sales_daily)
        df_d['date'] = pd.to_datetime(df_d['date'])
        
        # 1. EKSTRAKSI DNA TOKO (Karakteristik Unik Masing-Masing Toko)
        store_stats = {}
        for store_id in df_d['m_store_id'].unique():
            df_store = df_d[df_d['m_store_id'] == store_id].copy()
            df_store['day_of_week'] = df_store['date'].dt.dayofweek
            
            mean_omzet = df_store['total_omzet'].mean()
            std_omzet = df_store['total_omzet'].std()
            if pd.isna(std_omzet): std_omzet = 0
            
            # Hitung perbandingan ramai weekend vs weekday
            wd_mean = df_store[df_store['day_of_week'] < 5]['total_omzet'].mean()
            we_mean = df_store[df_store['day_of_week'] >= 5]['total_omzet'].mean()
            wd_mean = 0 if pd.isna(wd_mean) else wd_mean
            we_mean = 0 if pd.isna(we_mean) else we_mean
            weekend_ratio = we_mean / (wd_mean + 1) # Tambah 1 untuk menghindari pembagian dengan nol
            
            store_stats[store_id] = {
                'store_mean': float(mean_omzet),
                'store_std': float(std_omzet),
                'weekend_ratio': float(weekend_ratio)
            }
        
        # Mapping DNA Toko kembali ke DataFrame Harian
        df_d['store_mean_omzet'] = df_d['m_store_id'].apply(lambda x: store_stats[x]['store_mean'])
        df_d['store_std_omzet'] = df_d['m_store_id'].apply(lambda x: store_stats[x]['store_std'])
        df_d['store_weekend_ratio'] = df_d['m_store_id'].apply(lambda x: store_stats[x]['weekend_ratio'])
        
        # Label Encoding untuk store_id
        le = LabelEncoder()
        df_d['store_id_encoded'] = le.fit_transform(df_d['m_store_id'])
        
        # 2. FEATURE ENGINEERING WAKTU (Kalender)
        df_d['day_of_week'] = df_d['date'].dt.dayofweek 
        df_d['month'] = df_d['date'].dt.month
        df_d['day_of_month'] = df_d['date'].dt.day
        df_d['week_of_month'] = ((df_d['date'].dt.day - 1) // 7) + 1
        df_d['is_weekend'] = df_d['day_of_week'].apply(lambda x: 1 if x >= 5 else 0)
        df_d['is_payday'] = df_d['day_of_month'].apply(lambda x: 1 if (x >= 25 or x <= 5) else 0)
        df_d['total_discount'] = df_d.get('total_discount', 0).fillna(0)
        
        df_d = df_d.dropna().sort_values('date')
        
        # List Fitur X Gabungan (DNA Toko + Kalender)
        fitur_x = [
            'store_id_encoded', 'store_mean_omzet', 'store_std_omzet', 'store_weekend_ratio', 
            'day_of_week', 'month', 'day_of_month', 'week_of_month', 'is_weekend', 'is_payday', 'total_discount'
        ]
        X, y = df_d[fitur_x], df_d['total_omzet']
        
        if len(X) < 20:
            print("Data keseluruhan terlalu kecil untuk dilatih.")
            return

        # Ujian Akurasi (Simulasi)
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.15, shuffle=False)
        rf_eval = get_global_rf_model()
        rf_eval.fit(X_train, y_train)
        metrics = calculate_advanced_metrics(y_test, rf_eval.predict(X_test))

        print(f"   -> Evaluasi Global Model selesai (R2 Keseluruhan: {metrics['r2_score']})")

        # Train Full Model untuk Produksi
        rf_final = get_global_rf_model()
        rf_final.fit(X, y)
        
        # Catat last_date per toko untuk titik mulai forecasting
        last_dates = df_d.groupby('m_store_id')['date'].max().to_dict()
        
        # Kemas semua ke dalam 1 file pintar
        global_model_dict = {
            "model": rf_final,
            "fitur_x": fitur_x,
            "label_encoder": le,
            "store_stats": store_stats,
            "last_dates": last_dates,
            "metrics": metrics
        }
        
        os.makedirs(os.path.dirname(GLOBAL_MODEL_PATH), exist_ok=True)
        joblib.dump(global_model_dict, GLOBAL_MODEL_PATH)
        print(f"==> Tersimpan di {GLOBAL_MODEL_PATH}\n")

        # Pembersihan Model Lama (Agar rapi)
        for old_model in [Config.DAILY_MODEL_PATH, Config.WEEKLY_MODEL_PATH, Config.MONTHLY_MODEL_PATH]:
            if os.path.exists(old_model):
                try: os.remove(old_model)
                except: pass

if __name__ == '__main__':
    train_all()