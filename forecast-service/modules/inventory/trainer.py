"""Parallel trainer for all inventory forecasting models."""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests

from config import Config
from modules.inventory.forecaster import InventoryForecaster

# =========================================================================
# GLOBAL STATE — progress training disimpan di sini selama service hidup.
# Akan hilang jika service restart (diketahui, lihat README).
# =========================================================================
training_tasks: dict = {}
lock = threading.Lock()


def _update_task(task_id: str, **kwargs):
    """Update field tertentu di training_tasks secara thread-safe."""
    with lock:
        if task_id in training_tasks:
            training_tasks[task_id].update(kwargs)


# =========================================================================
# TRAINING SATU PASANGAN
# =========================================================================

def _train_single(store_id, ingr_id, task_id: str | None) -> tuple[bool, str]:
    """
    Latih satu pasangan (store_id, ingredient_id).

    Dijalankan di worker thread oleh ThreadPoolExecutor.
    Return (success: bool, pair_label: str) — dipakai untuk update counter di caller.
    """
    pair_label = f"{store_id} / {ingr_id}"
    try:
        fc = InventoryForecaster(store_id, ingr_id)
        fc.tune_and_train()

        # Simpan hasil forecast mingguan (4 minggu ke depan)
        fc.save_all_forecasts(periods=4, freq='W')
        # Simpan juga bulanan jika diperlukan (opsional)
        # fc.save_all_forecasts(periods=3, freq='M')

        return True, pair_label
    except Exception as e:
        # Log error tapi tidak stop training pasangan lain
        print(f"[GAGAL] {pair_label}: {e}")
        return False, pair_label
    

# =========================================================================
# TRAINING SEMUA PASANGAN
# =========================================================================

def train_all_inventory_models(task_id: str | None = None):
    """
    Latih semua pasangan (store_id, ingredient_id) dari data API.

    Training berjalan paralel — beberapa pasangan diproses sekaligus.
    Jumlah worker dikontrol oleh Config.TRAINING_MAX_WORKERS (default 4).

    Kenapa tidak lebih dari 4 worker?
      Prophet sendiri sudah multi-thread per model (Stan MCMC).
      Terlalu banyak worker justru berebut CPU dan memperlambat semuanya.
      4 worker adalah sweet spot untuk mesin dengan 4–8 core.
      Sesuaikan di .env jika server punya core lebih banyak.

    Args:
        task_id: jika diberikan, progress dicatat ke training_tasks[task_id].
                 Jika None (scheduled job), tidak ada tracking.
    """
    # Ambil semua pasangan dari API
    url = f"{Config.BACKEND_API_URL}/ingredient-stock-histories"
    try:
        resp = requests.get(url, headers=Config.backend_headers(), timeout=Config.BACKEND_REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
    except requests.RequestException as e:
        if task_id:
            _update_task(task_id, status="ERROR", message=str(e))
        print(f"[trainer] Gagal mengambil data dari API: {e}")
        return

    data    = resp.json()
    records = data['data'] if isinstance(data, dict) and 'data' in data else data

    if not records:
        if task_id:
            _update_task(task_id, status="ERROR", message="Tidak ada data dari API.")
        return

    df    = pd.DataFrame(records)
    pairs = df[['m_store_id', 'm_food_ingredient_id']].drop_duplicates()
    total = len(pairs)

    # [EDIT_POINT] Ubah jumlah worker default di Config.TRAINING_MAX_WORKERS (.env/config.py).
    print(f"[trainer] Mulai training {total} pasangan dengan max {Config.TRAINING_MAX_WORKERS} worker paralel")

    if task_id:
        _update_task(task_id, status="RUNNING", total=total, processed=0, current_pair=None, message="")

    processed_count = 0   # counter shared antar thread — update pakai lock

    with ThreadPoolExecutor(max_workers=Config.TRAINING_MAX_WORKERS) as executor:
        # Submit semua pekerjaan sekaligus; executor yang atur antrean
        futures = {
            executor.submit(_train_single, row['m_store_id'], row['m_food_ingredient_id'], task_id): row
            for _, row in pairs.iterrows()
        }

        for future in as_completed(futures):
            success, pair_label = future.result()

            # Update counter secara thread-safe
            with lock:
                processed_count += 1
                current = processed_count  # snapshot lokal untuk log

            if task_id:
                _update_task(
                    task_id,
                    processed=current,
                    current_pair=pair_label,
                )

            status_str = "OK" if success else "GAGAL"
            print(f"[trainer] [{current}/{total}] {status_str} — {pair_label}")

    if task_id:
        _update_task(task_id, status="DONE", processed=total, current_pair=None, message="")

    print(f"[trainer] Selesai. {total} pasangan diproses.")