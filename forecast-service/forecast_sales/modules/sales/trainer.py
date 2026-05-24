import pandas as pd
import joblib
from sklearn.ensemble import RandomForestRegressor
from config import Config
from modules.sales.forecaster import SalesForecaster

def get_upgraded_rf_model():
    """Mengembalikan model Random Forest dengan Hyperparameter yang dioptimalkan"""
    return RandomForestRegressor(
        n_estimators=200,          # Menggunakan 200 pohon (Standar: 100). Lebih akurat dan stabil.
        max_depth=15,              # Mencegah model terlalu 'menghafal' data noise (overfitting).
        min_samples_split=4,       # Butuh minimal 4 data untuk memecah cabang pohon.
        min_samples_leaf=2,        # Minimal 2 data di hasil akhir prediksi pohon.
        random_state=42,           
        n_jobs=-1                  # Memaksimalkan seluruh core CPU agar training cepat.
    )

def train_all():
    Config.init_app()
    forecaster = SalesForecaster()
    
    print("=== MULAI TRAINING MODEL PENJUALAN HARIAN ===")
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
            
            if len(df_s) < 7: continue

            fitur_x = ['day_of_week', 'month', 'is_weekend', 'total_discount']
            
            # Gunakan model yang sudah di-upgrade
            rf = get_upgraded_rf_model()
            rf.fit(df_s[fitur_x], df_s['total_omzet'])
            
            models_dict[store_id] = {"model": rf, "fitur_x": fitur_x, "last_date": df_s['date'].max()}
        
        joblib.dump(models_dict, Config.DAILY_MODEL_PATH)
        print(f"-> Selesai! Model Harian disimpan di {Config.DAILY_MODEL_PATH}")

    print("\n=== MULAI TRAINING MODEL PENJUALAN BULANAN ===")
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
            
            if len(df_s) < 3: continue

            fitur_x = ['month', 'quarter', 'total_discount']
            
            # Gunakan model yang sudah di-upgrade
            rf = get_upgraded_rf_model()
            rf.fit(df_s[fitur_x], df_s['total_omzet'])
            
            models_dict_m[store_id] = {"model": rf, "fitur_x": fitur_x, "last_date": df_s['date'].max()}
            
        joblib.dump(models_dict_m, Config.MONTHLY_MODEL_PATH)
        print(f"-> Selesai! Model Bulanan disimpan di {Config.MONTHLY_MODEL_PATH}")

if __name__ == '__main__':
    train_all()