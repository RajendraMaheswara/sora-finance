import pandas as pd
import requests
import threading
import uuid
import time
from config import Config
from modules.inventory.forecaster import InventoryForecaster

# ========== GLOBAL STATE UNTUK PROGRESS ==========
training_tasks = {}
lock = threading.Lock()

def _update_task(task_id, **kwargs):
    with lock:
        if task_id in training_tasks:
            training_tasks[task_id].update(kwargs)

def train_all_inventory_models(task_id=None):
    """
    Latih semua pasangan (store_id, ingredient_id).
    Jika task_id diberikan, progress akan dicatat ke global training_tasks.
    """
    # Ambil data pasangan dari API
    url = f"{Config.BACKEND_API_URL}/ingredient-stock-histories"
    try:
        resp = requests.get(url)
        resp.raise_for_status()
    except requests.RequestException as e:
        if task_id:
            _update_task(task_id, status="ERROR", message=str(e))
        return

    data = resp.json()
    if isinstance(data, dict) and 'data' in data:
        records = data['data']
    else:
        records = data

    if not records:
        if task_id:
            _update_task(task_id, status="ERROR", message="Tidak ada data.")
        return

    df = pd.DataFrame(records)
    pairs = df[['m_store_id', 'm_food_ingredient_id']].drop_duplicates()
    total = len(pairs)
    if task_id:
        _update_task(task_id, status="RUNNING", total=total, processed=0, current_pair=None)

    for i, (_, row) in enumerate(pairs.iterrows(), start=1):
        store_id = row['m_store_id']
        ingr_id = row['m_food_ingredient_id']
        current = f"{store_id} / {ingr_id}"
        if task_id:
            _update_task(task_id, current_pair=current, processed=i-1)

        try:
            fc = InventoryForecaster(store_id, ingr_id)
            fc.tune_and_train()
        except Exception as e:
            # Log error tapi lanjut
            print(f"Gagal training {store_id}-{ingr_id}: {e}")

    if task_id:
        _update_task(task_id, status="DONE", processed=total, current_pair=None)