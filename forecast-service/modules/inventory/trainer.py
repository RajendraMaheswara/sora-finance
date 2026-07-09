"""Parallel trainer for inventory forecasting – store-level joblib."""

import json
import os
import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from statistics import mean

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


def _extract_items(payload):
    if isinstance(payload, dict):
        for key in ("data", "items", "results"):
            if isinstance(payload.get(key), list):
                return payload[key]
        return []
    if isinstance(payload, list):
        return payload
    return []


def _food_ingredient_id_from_item(item):
    value = (
        item.get("id")
        or item.get("ingredient_id")
        or item.get("m_food_ingredient_id")
        or item.get("food_ingredient_id")
        or item.get("mFoodIngredientId")
    )
    return str(value) if value else None


def _item_belongs_to_store(item, store_id):
    value = item.get("m_store_id") or item.get("store_id") or item.get("storeId") or item.get("mStoreId")
    return value in (None, "") or str(value) == str(store_id)


def _fetch_store_food_ingredient_ids(store_id: str) -> list[str]:
    """Fetch active master ingredients for a store.

    If the endpoint is unavailable, caller can safely fall back to history-only
    ingredient ids. This keeps retrain usable in older backend deployments.
    """
    url = f"{Config.BACKEND_API_URL}/food-ingredients"
    try:
        resp = requests.get(
            url,
            headers=Config.backend_headers(),
            params={"store_id": store_id},
            timeout=Config.BACKEND_REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"[trainer] Gagal ambil master ingredient untuk {store_id}: {exc}")
        return []

    seen = set()
    ingredient_ids = []
    for item in _extract_items(resp.json()):
        if not isinstance(item, dict) or not _item_belongs_to_store(item, store_id):
            continue
        ingredient_id = _food_ingredient_id_from_item(item)
        if ingredient_id and ingredient_id not in seen:
            ingredient_ids.append(ingredient_id)
            seen.add(ingredient_id)
    return ingredient_ids


def _no_history_metadata(ingredient_id: str) -> dict:
    message = "Belum ada histori stok; model forecast tidak dibuat."
    return {
        "status": "skipped",
        "reason_code": "no_stock_history",
        "message": message,
        "error": message,
        "history_count": 0,
    }


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _task_progress(processed: int, total: int, failed: int = 0) -> dict:
    percentage = round((processed / total) * 100, 2) if total else 0
    return {
        "total": total,
        "processed": processed,
        "failed": failed,
        "percentage": percentage,
    }


def _update_task(task_id: str, **kwargs):
    with lock:
        if task_id in training_tasks:
            kwargs.setdefault("updated_at", _utc_now_iso())
            training_tasks[task_id].update(kwargs)


def get_training_task(task_id: str) -> dict | None:
    """Return a shallow copy of a retrain/training task for API responses."""
    with lock:
        task = training_tasks.get(task_id)
        return dict(task) if isinstance(task, dict) else None


def _find_running_inventory_retrain_task(store_id: str) -> tuple[str, dict] | tuple[None, None]:
    with lock:
        for task_id, task in training_tasks.items():
            if not isinstance(task, dict):
                continue
            if task.get("job_type") != "inventory_retrain":
                continue
            if str(task.get("store_id")) != str(store_id):
                continue
            if task.get("status") in ("queued", "running"):
                return task_id, dict(task)
    return None, None


def _public_task(task_id: str, task: dict) -> dict:
    payload = dict(task or {})
    payload.setdefault("task_id", task_id)
    return payload


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
    history_ingredient_ids = [str(item) for item in df_store['m_food_ingredient_id'].dropna().unique()]
    master_ingredient_ids = _fetch_store_food_ingredient_ids(store_id)
    requested_ingredient_ids = master_ingredient_ids or history_ingredient_ids
    history_id_set = set(history_ingredient_ids)
    skipped_no_history_ids = [
        ingredient_id for ingredient_id in requested_ingredient_ids
        if ingredient_id not in history_id_set
    ]
    ingredient_ids = history_ingredient_ids

    if len(ingredient_ids) == 0:
        return False, f"{store_id} ({label})"

    # 2. Latih setiap ingredient yang punya histori, lalu catat master ingredient
    # yang belum punya histori sebagai skipped_no_history.
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
            metadata[ing_id] = {
                "status": "failed",
                "reason_code": "training_failed",
                "error": str(e),
            }

    for ing_id in skipped_no_history_ids:
        metadata[ing_id] = _no_history_metadata(ing_id)

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

def _inventory_metadata_path(store_id: str, horizon_label: str) -> str:
    model_dir = os.path.join(Config.MODEL_DIR, 'inventory')
    return os.path.join(model_dir, f"inventory_{horizon_label}_metadata_store_{store_id}.json")


def _average_metric(entries: list[dict], metric_name: str) -> float | None:
    values = []
    for entry in entries:
        metrics = entry.get("metrics") if isinstance(entry, dict) else None
        if not isinstance(metrics, dict):
            continue
        value = metrics.get(metric_name)
        if isinstance(value, (int, float)):
            values.append(float(value))
    return round(mean(values), 6) if values else None


def _summarize_inventory_horizon_metadata(store_id: str, horizon_label: str) -> dict:
    """Build a compact retrain summary from the saved per-ingredient metadata."""
    path = _inventory_metadata_path(store_id, horizon_label)
    if not os.path.exists(path):
        return {
            "trained_ingredient_count": 0,
            "skipped_ingredient_count": 0,
            "failed_ingredient_count": 0,
            "requested_ingredient_count": 0,
            "training_data_points": 0,
            "metrics": {},
            "skipped_ingredients": [],
            "failed_ingredients": [],
        }

    try:
        with open(path, "r") as f:
            metadata = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {
            "trained_ingredient_count": 0,
            "skipped_ingredient_count": 0,
            "failed_ingredient_count": 0,
            "requested_ingredient_count": 0,
            "training_data_points": 0,
            "metrics": {},
            "skipped_ingredients": [],
            "failed_ingredients": [],
        }

    if not isinstance(metadata, dict):
        metadata = {}

    trained_entries = [
        item for item in metadata.values()
        if isinstance(item, dict) and not item.get("error") and item.get("status") != "skipped"
    ]
    skipped_entries = [
        {"ingredient_id": ingredient_id, **item}
        for ingredient_id, item in metadata.items()
        if isinstance(item, dict) and item.get("status") == "skipped"
    ]
    failed_entries = [
        {"ingredient_id": ingredient_id, **item}
        for ingredient_id, item in metadata.items()
        if isinstance(item, dict) and item.get("error") and item.get("status") != "skipped"
    ]

    train_starts = [item.get("train_start") for item in trained_entries if item.get("train_start")]
    train_ends = [item.get("train_end") for item in trained_entries if item.get("train_end")]
    data_days = [
        int(item.get("data_days"))
        for item in trained_entries
        if isinstance(item.get("data_days"), int) or str(item.get("data_days", "")).isdigit()
    ]

    metrics = {
        "avg_mae": _average_metric(trained_entries, "mae"),
        "avg_rmse": _average_metric(trained_entries, "rmse"),
        "avg_mape": _average_metric(trained_entries, "mape"),
        "avg_smape": _average_metric(trained_entries, "smape"),
    }
    metrics = {key: value for key, value in metrics.items() if value is not None}

    return {
        "trained_ingredient_count": len(trained_entries),
        "skipped_ingredient_count": len(skipped_entries),
        "failed_ingredient_count": len(failed_entries),
        "requested_ingredient_count": len(metadata),
        "training_data_points": sum(data_days),
        "train_start_date": min(train_starts) if train_starts else None,
        "train_end_date": max(train_ends) if train_ends else None,
        "metrics": metrics,
        "skipped_ingredients": skipped_entries,
        "failed_ingredients": failed_entries,
    }


def retrain_inventory_store(store_id: str, force: bool = False, task_id: str | None = None) -> dict:
    """Retrain inventory models for one store across daily, weekly, monthly horizons.

    The response is shaped to be consistent with visitors/sales retrain while
    preserving inventory's per-horizon/per-ingredient nature.
    """
    horizons = [('D', 'daily'), ('W', 'weekly'), ('M', 'monthly')]
    total_horizons = len(horizons)
    if task_id:
        _update_task(
            task_id,
            status="running",
            total=total_horizons,
            processed=0,
            failed=0,
            progress=_task_progress(0, total_horizons, 0),
            current_horizon=None,
            message="Retrain inventory dimulai.",
        )
    horizon_results = []
    success_count = 0
    trained_at = datetime.now(timezone.utc).isoformat()

    for index, (freq, label) in enumerate(horizons, start=1):
        if task_id:
            _update_task(
                task_id,
                status="running",
                current_horizon=label,
                current_pair=f"{store_id} ({label})",
                message=f"Training inventory {label} sedang berjalan.",
                progress=_task_progress(index - 1, total_horizons, total_horizons - success_count - (total_horizons - index + 1)),
            )

        ok, message = _train_store_for_horizon(store_id, freq, task_id=task_id)
        summary = _summarize_inventory_horizon_metadata(store_id, label) if ok else {
            "trained_ingredient_count": 0,
            "skipped_ingredient_count": 0,
            "failed_ingredient_count": 0,
            "requested_ingredient_count": 0,
            "training_data_points": 0,
            "metrics": {},
            "skipped_ingredients": [],
            "failed_ingredients": [],
        }
        horizon_results.append({
            "horizon_label": label,
            "granularity": label,
            "status": "success" if ok else "failed",
            "message": message,
            "model_name": "Prophet",
            "trained_at": trained_at,
            **summary,
        })
        if ok:
            success_count += 1

        if task_id:
            processed_count = index
            failed_so_far = processed_count - success_count
            _update_task(
                task_id,
                status="running",
                processed=processed_count,
                failed=failed_so_far,
                current_horizon=label,
                current_pair=f"{store_id} ({label})",
                message=f"Training inventory {label} {'berhasil' if ok else 'gagal'}.",
                progress=_task_progress(processed_count, total_horizons, failed_so_far),
            )

    failed_count = total_horizons - success_count
    status = "success" if success_count == total_horizons else "partial_success" if success_count else "failed"

    successful_horizons = [item for item in horizon_results if item["status"] == "success"]
    horizon_mae = [
        item.get("metrics", {}).get("avg_mae")
        for item in successful_horizons
        if isinstance(item.get("metrics", {}).get("avg_mae"), (int, float))
    ]
    horizon_rmse = [
        item.get("metrics", {}).get("avg_rmse")
        for item in successful_horizons
        if isinstance(item.get("metrics", {}).get("avg_rmse"), (int, float))
    ]

    return {
        "module": "inventory",
        "store_id": store_id,
        "status": status,
        "message": f"Retrain inventory selesai: {success_count}/{total_horizons} horizon berhasil.",
        "force": bool(force),
        "trained_at": trained_at,
        "model_name": "Prophet",
        "training_mode": "per_horizon_per_ingredient",
        "training_scope": "store_all_ingredients_all_horizons",
        "training_data_points": sum(item.get("training_data_points") or 0 for item in horizon_results),
        "cv_mae": round(mean(horizon_mae), 6) if horizon_mae else None,
        "cv_rmse": round(mean(horizon_rmse), 6) if horizon_rmse else None,
        "feature_importance": {},
        "summary": {
            "requested_horizon_count": total_horizons,
            "successful_horizon_count": success_count,
            "failed_horizon_count": failed_count,
            "requested_ingredient_count": sum(item.get("requested_ingredient_count") or 0 for item in horizon_results),
            "trained_ingredient_count": sum(item.get("trained_ingredient_count") or 0 for item in horizon_results),
            "skipped_ingredient_count": sum(item.get("skipped_ingredient_count") or 0 for item in horizon_results),
            "failed_ingredient_count": sum(item.get("failed_ingredient_count") or 0 for item in horizon_results),
        },
        "horizons": horizon_results,
    }



def _run_inventory_retrain_task(task_id: str, store_id: str, force: bool = False):
    """Background worker for long-running inventory retrain jobs."""
    try:
        _update_task(
            task_id,
            status="running",
            started_at=_utc_now_iso(),
            message="Inventory retrain job sedang berjalan.",
        )
        result = retrain_inventory_store(store_id=store_id, force=force, task_id=task_id)
        final_status = result.get("status") or "success"
        if final_status not in ("success", "partial_success", "failed"):
            final_status = "success"
        _update_task(
            task_id,
            status=final_status,
            finished_at=_utc_now_iso(),
            current_horizon=None,
            current_pair=None,
            message=result.get("message") or "Inventory retrain selesai.",
            result=result,
            progress=_task_progress(
                result.get("summary", {}).get("requested_horizon_count", 3),
                result.get("summary", {}).get("requested_horizon_count", 3),
                result.get("summary", {}).get("failed_horizon_count", 0),
            ),
        )
    except Exception as exc:
        traceback.print_exc()
        _update_task(
            task_id,
            status="failed",
            finished_at=_utc_now_iso(),
            message="Inventory retrain gagal.",
            error=str(exc),
        )


def start_inventory_retrain_task(store_id: str, force: bool = False) -> tuple[str, dict, bool]:
    """Start one async inventory retrain job per store.

    Returns (task_id, task_snapshot, created). If the same store already has a
    queued/running job, created is False and the existing task is returned.
    """
    now = _utc_now_iso()
    with lock:
        for existing_task_id, existing_task in training_tasks.items():
            if not isinstance(existing_task, dict):
                continue
            if existing_task.get("job_type") != "inventory_retrain":
                continue
            if str(existing_task.get("store_id")) != str(store_id):
                continue
            if existing_task.get("status") in ("queued", "running"):
                return existing_task_id, _public_task(existing_task_id, existing_task), False

        task_id = str(uuid.uuid4())
        task = {
            "task_id": task_id,
            "job_type": "inventory_retrain",
            "forecast_type": "inventory",
            "store_id": store_id,
            "force": bool(force),
            "status": "queued",
            "total": 3,
            "processed": 0,
            "failed": 0,
            "progress": _task_progress(0, 3, 0),
            "current_horizon": None,
            "current_pair": None,
            "message": "Inventory retrain job masuk antrean.",
            "created_at": now,
            "updated_at": now,
            "started_at": None,
            "finished_at": None,
        }
        training_tasks[task_id] = task
        task_snapshot = _public_task(task_id, task)

    thread = threading.Thread(
        target=_run_inventory_retrain_task,
        args=(task_id, store_id, bool(force)),
        daemon=True,
    )
    thread.start()
    return task_id, task_snapshot, True
