"""Parallel trainer for inventory forecasting – store-level joblib."""

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import joblib
import pandas as pd
import requests

from config import Config
from modules.inventory.forecaster import InventoryForecaster

# =========================================================================
# GLOBAL STATE
# =========================================================================
training_tasks: dict = {}
lock = threading.Lock()

def _update_task(task_id: str, **kwargs):
    with lock:
        if task_id in training_tasks:
            training_tasks[task_id].update(kwargs)


# =========================================================================
# TRAINING SATU TOKO UNTUK SATU HORIZON
# =========================================================================
def _train_store_for_horizon(store_id: str, freq: str, task_id: str | None = None) -> tuple[bool, str]:
    """
    Latih semua ingredient satu toko untuk satu horizon (D/W/M).
    Simpan hasil dalam 4 file joblib/json.
    """
    label = {'D': 'daily', 'W': 'weekly', 'M': 'monthly'}[freq]

    # 1. Ambil daftar ingredient untuk toko ini
    url = f"{Config.BACKEND_API_URL}/ingredient-stock-histories"
    try:
        resp = requests.get(url, headers=Config.backend_headers(), timeout=Config.BACKEND_REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[trainer] Gagal ambil data untuk {store_id}: {e}")
        return False, f"{store_id} ({label})"

    data = resp.json()
    records = data['data'] if isinstance(data, dict) and 'data' in data else data
    if not records:
        return False, f"{store_id} ({label})"

    df = pd.DataFrame(records)
    df_store = df[df['m_store_id'] == store_id]
    ingredient_ids = df_store['m_food_ingredient_id'].unique()

    if len(ingredient_ids) == 0:
        return False, f"{store_id} ({label})"

    # 2. Latih setiap ingredient, kumpulkan model & metrik
    models = {}
    metadata = {}
    for ing_id in ingredient_ids:
        try:
            fc = InventoryForecaster(store_id, ing_id, freq)
            fc.tune_and_train()                   # latih, simpan model internal
            models[ing_id] = fc.model
            metadata[ing_id] = {
                "metrics": fc._load_metrics(),
                "train_start": fc.model.history['ds'].min().strftime('%Y-%m-%d'),
                "train_end":   fc.model.history['ds'].max().strftime('%Y-%m-%d'),
                "data_days":   len(fc.model.history)
            }
        except Exception as e:
            print(f"[trainer] Gagal latih {ing_id}: {e}")
            models[ing_id] = None
            metadata[ing_id] = {"error": str(e)}

    # 3. Simpan ke file joblib
    model_dir = os.path.join(Config.MODEL_DIR, 'inventory')
    os.makedirs(model_dir, exist_ok=True)

    base = f"inventory_{label}_"
    joblib.dump(models,    os.path.join(model_dir, f"{base}model_store_{store_id}.joblib"))
    joblib.dump(None,      os.path.join(model_dir, f"{base}scaler_store_{store_id}.joblib"))   # tidak terpakai
    with open(os.path.join(model_dir, f"{base}features_store_{store_id}.json"), 'w') as f:
        json.dump(["is_weekend", "is_national_holiday", "is_store_closed"], f)
    with open(os.path.join(model_dir, f"{base}metadata_store_{store_id}.json"), 'w') as f:
        json.dump(metadata, f, indent=2, default=str)

    return True, f"{store_id} ({label})"


# =========================================================================
# TRAINING SEMUA TOKO DAN SEMUA HORIZON
# =========================================================================
def train_all_inventory_models(task_id: str | None = None):
    """
    Melatih model untuk semua toko, untuk semua horizon (daily, weekly, monthly).
    """
    # 1. Ambil semua store_id yang memiliki data
    url = f"{Config.BACKEND_API_URL}/ingredient-stock-histories"
    try:
        resp = requests.get(url, headers=Config.backend_headers(), timeout=Config.BACKEND_REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
    except requests.RequestException as e:
        if task_id:
            _update_task(task_id, status="ERROR", message=str(e))
        print(f"[trainer] Gagal mengambil data dari API: {e}")
        return

    data = resp.json()
    records = data['data'] if isinstance(data, dict) and 'data' in data else data
    if not records:
        if task_id:
            _update_task(task_id, status="ERROR", message="Tidak ada data dari API.")
        return

    df = pd.DataFrame(records)
    store_ids = df['m_store_id'].unique()
    horizons = ['D', 'W', 'M']
    total_jobs = len(store_ids) * len(horizons)

    print(f"[trainer] Mulai training {len(store_ids)} toko x 3 horizon ({total_jobs} job) "
          f"dengan max {Config.TRAINING_MAX_WORKERS} worker paralel")

    if task_id:
        _update_task(task_id, status="RUNNING", total=total_jobs, processed=0,
                     current_pair=None, message="")

    processed_count = 0

    with ThreadPoolExecutor(max_workers=Config.TRAINING_MAX_WORKERS) as executor:
        futures = {}
        for store_id in store_ids:
            for freq in horizons:
                f = executor.submit(_train_store_for_horizon, store_id, freq, task_id)
                futures[f] = (store_id, freq)

        for future in as_completed(futures):
            success, label = future.result()
            with lock:
                processed_count += 1
                current = processed_count
            if task_id:
                _update_task(task_id, processed=current, current_pair=label)
            status_str = "OK" if success else "GAGAL"
            print(f"[trainer] [{current}/{total_jobs}] {status_str} — {label}")

    if task_id:
        _update_task(task_id, status="DONE", processed=total_jobs, current_pair=None, message="")
    print(f"[trainer] Selesai. {total_jobs} job diproses.")

def retrain_inventory_store(store_id: str, force: bool = False) -> dict:
    """Retrain inventory models for one store across daily, weekly, monthly horizons.

    The `force` flag is accepted for API consistency with visitors/sales. The
    current trainer always overwrites the model artifacts for the requested
    store/horizon when training succeeds.
    """
    horizons = [('D', 'daily'), ('W', 'weekly'), ('M', 'monthly')]
    horizon_results = []
    success_count = 0

    for freq, label in horizons:
        ok, message = _train_store_for_horizon(store_id, freq, task_id=None)
        horizon_results.append({
            "horizon_label": label,
            "status": "success" if ok else "failed",
            "message": message,
        })
        if ok:
            success_count += 1

    status = "success" if success_count == len(horizons) else "partial_success" if success_count else "failed"
    return {
        "store_id": store_id,
        "status": status,
        "message": f"Retrain inventory selesai: {success_count}/{len(horizons)} horizon berhasil.",
        "force": bool(force),
        "horizons": horizon_results,
    }
