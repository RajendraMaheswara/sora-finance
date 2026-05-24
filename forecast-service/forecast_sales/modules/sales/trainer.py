import pandas as pd
import numpy as np
import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    mean_absolute_error, 
    mean_squared_error, 
    r2_score, 
    mean_absolute_percentage_error, 
    explained_variance_score
)
from config import Config
from modules.sales.forecaster import SalesForecaster

def get_optimized_rf_model():
    """
    Mengembalikan model Random Forest dengan Hyperparameter yang dioptimalkan 
    untuk meningkatkan akurasi (Confidence Score) dan mencegah overfitting.
    """
    return RandomForestRegressor(
        n_estimators=250,          # Ditambah menjadi 250 pohon untuk stabilitas prediksi yang lebih tinggi
        max_depth=12,              # Membatasi kedalaman agar tidak terlalu menghafal noise data historis
        min_samples_split=5,       # Minimal 5 sampel untuk memecah node internal
        min_samples_leaf=3,        # Minimal 3 sampel pada leaf node untuk memperhalus prediksi
        random_state=42,           # Mengunci seed agar hasil training konsisten
        n_jobs=-1                  # Menggunakan seluruh core CPU yang tersedia agar proses super cepat
    )

def calculate_advanced_metrics(y_true, y_pred):
    """
    Menghitung rapor evaluasi performa model AI secara mendalam.
    """
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    
    # Penanganan khusus jika terdapat data riil bernilai 0 untuk menghindari nilai kebenaran tak terhingga
    if (y_true == 0).any():
        # Menghitung MAPE hanya pada data yang tidak bernilai nol
        non_zero_mask = y_true != 0
        if non_zero_mask.sum() > 0:
            mape = np.mean(np.abs((y_true[non_zero_mask] - y_pred[non_zero_mask]) / y_true[non_zero_mask])) * 100
        else:
            mape = 20.0  # Nilai default aman jika seluruh data uji adalah nol
    else:
        mape = mean_absolute_percentage_error(y_true, y_pred) * 100
        
    r2 = r2_score(y_true, y_pred)
    ev = explained_variance_score(y_true, y_pred)
    
    return {
        "mae": round(float(mae), 3), 
        "rmse": round(float(rmse), 3), 
        "mape": round(float(mape), 4), 
        "r2_score": round(float(r2), 4), 
        "explained_variance": round(float(ev), 4)
    }

def train_all():
    # Inisialisasi folder models/sales otomatis jika belum terbentuk
    Config.init_app()
    forecaster = SalesForecaster()
    
    # =========================================================================
    # 1. MODUL TRAINING PENJUALAN HARIAN (Mendukung Fitur Psikologis Siklus Gajian)
    # =========================================================================
    print("=== [TRAINER] MULAI PROSES PELATIHAN MODEL HARIAN (DAILY) ===")
    sales_daily = forecaster.fetch_data("sales-daily-summaries")
    
    if sales_daily:
        df_d = pd.DataFrame(sales_daily)
        df_d['date'] = pd.to_datetime(df_d['date'])
        daily_models_dict = {}
        
        unique_stores = df_d['m_store_id'].unique()
        print(f"[DAILY] Ditemukan {len(unique_stores)} toko yang siap diproses.")
        
        for store_id in unique_stores:
            df_s = df_d[df_d['m_store_id'] == store_id].copy().sort_values('date')
            
            # --- FEATURE ENGINEERING ADVANCED (HARIAN) ---
            df_s['day_of_week'] = df_s['date'].dt.dayofweek 
            df_s['month'] = df_s['date'].dt.month
            df_s['is_weekend'] = df_s['day_of_week'].apply(lambda x: 1 if x >= 5 else 0)
            df_s['total_discount'] = df_s.get('total_discount', 0).fillna(0)
            
            # Upgrade: Menambahkan Pola Siklus Gajian (Payday Effect) untuk Dongkrak Akurasi
            df_s['day_of_month'] = df_s['date'].dt.day
            df_s['is_payday'] = df_s['day_of_month'].apply(lambda x: 1 if (x >= 25 or x <= 5) else 0)
            
            # Validasi kecukupan data untuk evaluasi (Minimal 15 hari)
            if len(df_s) < 15: 
                print(f"   -> [SKIP] Toko '{store_id}' dilewati. Data historis terlalu sedikit ({len(df_s)} hari).")
                continue

            fitur_x = ['day_of_week', 'month', 'is_weekend', 'is_payday', 'total_discount']
            X = df_s[fitur_x]
            y = df_s['total_omzet']

            # Tahap Evaluasi (Simulasi Ujian Akurasi menggunakan 20% data terakhir)
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
            rf_eval = get_optimized_rf_model()
            rf_eval.fit(X_train, y_train)
            metrics = calculate_advanced_metrics(y_test, rf_eval.predict(X_test))

            # Tahap Produksi Final (Latih ulang dengan 100% data riil untuk meramal masa depan)
            rf_final = get_optimized_rf_model()
            rf_final.fit(X, y)
            
            daily_models_dict[store_id] = {
                "model": rf_final, 
                "fitur_x": fitur_x, 
                "last_date": df_s['date'].max(), 
                "metrics": metrics
            }
            print(f"   -> [SUCCESS] Model Harian Toko '{store_id}' berhasil dilatih. (R2 Score: {metrics['r2_score']})")
        
        # Simpan struktur dictionary harian ke file binari .joblib
        joblib.dump(daily_models_dict, Config.DAILY_MODEL_PATH)
        print(f"==> [DAILY] Seluruh Otak AI Harian Berhasil Disimpan di: {Config.DAILY_MODEL_PATH}\n")
    else:
        print("[DAILY] WARNING: Endpoint 'sales-daily-summaries' kosong atau gagal diakses.\n")

    # =========================================================================
    # 2. MODUL TRAINING PENJUALAN BULANAN (Mendukung Tren Makro & Pola Kuartal)
    # =========================================================================
    print("=== [TRAINER] MULAI PROSES PELATIHAN MODEL BULANAN (MONTHLY) ===")
    sales_monthly = forecaster.fetch_data("sales-monthly-summaries")
    
    if sales_monthly:
        df_m = pd.DataFrame(sales_monthly)
        df_m['date'] = pd.to_datetime(df_m['date'])
        monthly_models_dict = {}
        
        unique_stores_m = df_m['m_store_id'].unique()
        print(f"[MONTHLY] Ditemukan {len(unique_stores_m)} toko yang siap diproses.")
        
        for store_id in unique_stores_m:
            df_s = df_m[df_m['m_store_id'] == store_id].copy().sort_values('date')
            
            # --- FEATURE ENGINEERING ADVANCED (BULANAN) ---
            df_s['month'] = df_s['date'].dt.month
            df_s['quarter'] = df_s['date'].dt.quarter  # Pola performa bisnis per kuartal (Q1 - Q4)
            df_s['total_discount'] = df_s.get('total_discount', 0).fillna(0)
            
            # Validasi kecukupan data bulanan untuk evaluasi (Minimal 5 bulan record)
            if len(df_s) < 5: 
                print(f"   -> [SKIP] Toko '{store_id}' dilewati. Data historis bulanan tidak cukup ({len(df_s)} bulan).")
                continue

            fitur_x = ['month', 'quarter', 'total_discount']
            X = df_s[fitur_x]
            y = df_s['total_omzet']

            # Tahap Evaluasi
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
            rf_eval = get_optimized_rf_model()
            rf_eval.fit(X_train, y_train)
            metrics = calculate_advanced_metrics(y_test, rf_eval.predict(X_test))

            # Tahap Produksi Final
            rf_final = get_optimized_rf_model()
            rf_final.fit(X, y)
            
            monthly_models_dict[store_id] = {
                "model": rf_final, 
                "fitur_x": fitur_x, 
                "last_date": df_s['date'].max(), 
                "metrics": metrics
            }
            print(f"   -> [SUCCESS] Model Bulanan Toko '{store_id}' berhasil dilatih. (R2 Score: {metrics['r2_score']})")
            
        # Simpan struktur dictionary bulanan ke file binari .joblib
        joblib.dump(monthly_models_dict, Config.MONTHLY_MODEL_PATH)
        print(f"==> [MONTHLY] Seluruh Otak AI Bulanan Berhasil Disimpan di: {Config.MONTHLY_MODEL_PATH}\n")
    else:
        print("[MONTHLY] WARNING: Endpoint 'sales-monthly-summaries' kosong atau gagal diakses.\n")

if __name__ == '__main__':
    train_all()
