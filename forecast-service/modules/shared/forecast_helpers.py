"""Shared standardization helpers for forecast-service modules.

This file intentionally contains only module-agnostic helpers so visitors,
sales, and inventory can keep their own forecasting logic while sharing
request validation, response metadata, date boundaries, and scheduler
idempotency checks.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger("forecast_helpers")

HORIZON_LABELS = {"daily", "weekly", "monthly"}
HORIZON_DEFAULT_COUNT = {"daily": 30, "weekly": 4, "monthly": 3}
HORIZON_MAX_COUNT = {"daily": 90, "weekly": 52, "monthly": 24}
HORIZON_LEGACY_KEYS = {
    "daily": "forecast_days",
    "weekly": "forecast_weeks",
    "monthly": "forecast_months",
}


def map_horizon_to_freq(horizon_label: str) -> str:
    mapping = {"daily": "D", "weekly": "W", "monthly": "M"}
    label = str(horizon_label or "").strip().lower()
    if label not in mapping:
        raise ValueError("horizon_label harus daily/weekly/monthly")
    return mapping[label]


def get_store_id(payload: Dict[str, Any]) -> Optional[str]:
    value = payload.get("store_id") or payload.get("m_store_id")
    return str(value) if value else None


def validate_uuid(value: Any, field_name: str) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except Exception as exc:
        raise ValueError(f"{field_name} harus UUID valid") from exc


def parse_start_date(payload: Dict[str, Any]) -> Optional[date]:
    value = payload.get("start_date")
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError as exc:
        raise ValueError("start_date harus format YYYY-MM-DD") from exc


def parse_horizon_label(payload: Dict[str, Any]) -> str:
    label = str(payload.get("horizon_label", "daily")).strip().lower()
    if label not in HORIZON_LABELS:
        raise ValueError("horizon_label harus salah satu dari: daily, weekly, monthly")
    return label


def parse_horizon_count(payload: Dict[str, Any], horizon_label: str) -> int:
    legacy_key = HORIZON_LEGACY_KEYS[horizon_label]
    raw_value = payload.get(
        "horizon_count",
        payload.get("periods", payload.get(legacy_key, HORIZON_DEFAULT_COUNT[horizon_label])),
    )
    try:
        count = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("horizon_count harus berupa angka") from exc
    if count < 1:
        raise ValueError("horizon_count minimal 1")
    max_count = HORIZON_MAX_COUNT[horizon_label]
    if count > max_count:
        raise ValueError(f"horizon_count {horizon_label} maksimal {max_count}")
    return count


def parse_standard_body(payload: Dict[str, Any], *, module: str, require_ingredient: bool = False) -> Dict[str, Any]:
    store_id = get_store_id(payload)
    if not store_id:
        raise ValueError("store_id wajib diisi")

    parsed: Dict[str, Any] = {
        "store_id": validate_uuid(store_id, "store_id"),
        "horizon_label": parse_horizon_label(payload),
    }
    parsed["horizon_count"] = parse_horizon_count(payload, parsed["horizon_label"])
    parsed["start_date"] = parse_start_date(payload)

    if require_ingredient:
        ingredient_id = payload.get("ingredient_id") or payload.get("m_food_ingredient_id")
        if not ingredient_id:
            raise ValueError("ingredient_id wajib diisi")
        parsed["ingredient_id"] = validate_uuid(ingredient_id, "ingredient_id")

    return parsed


def to_json_model(result: Any) -> Any:
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    if hasattr(result, "dict"):
        return result.dict()
    return result


def iso_date(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def standard_request_meta(module: str, payload: Dict[str, Any], extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    meta: Dict[str, Any] = {
        "module": module,
        "store_id": payload.get("store_id"),
        "horizon_label": payload.get("horizon_label"),
        "horizon_count": payload.get("horizon_count"),
        "start_date": iso_date(payload.get("start_date")),
        "start_date_mode": payload.get("start_date_mode") or ("manual" if payload.get("start_date") else "auto"),
    }
    if extra:
        meta.update({k: v for k, v in extra.items() if v is not None})
    return meta


def public_save_result(save_result: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not save_result:
        return None
    fields = (
        "status",
        "message",
        "run_id",
        "forecast_type",
        "horizon_label",
        "horizon_days",
        "predict_start_date",
        "predict_end_date",
        "saved_results",
        "backend_status",
    )
    public = {key: save_result.get(key) for key in fields if save_result.get(key) is not None}
    if "status" not in public:
        public["status"] = "saved"
    if "saved_results" not in public:
        public["saved_results"] = save_result.get("saved_results")
    return public


def standard_retrain_response(module: str, result: Any, request_meta: Dict[str, Any]) -> Dict[str, Any]:
    data = to_json_model(result)
    status = data.get("status", "success") if isinstance(data, dict) else "success"
    message = data.get("message") if isinstance(data, dict) else None
    return {
        "status": "success" if status in ("success", "completed", "DONE", "done") else status,
        "message": message or f"Retrain {module} berhasil.",
        "request": request_meta,
        "data": data,
    }


def add_predicted_value_aliases(response: Dict[str, Any], *, predicted_key: str) -> Dict[str, Any]:
    """Add `predicted_value` to every forecast item without removing module-specific fields."""
    for item in response.get("forecasts", []) or []:
        if isinstance(item, dict) and "predicted_value" not in item:
            item["predicted_value"] = item.get(predicted_key)
    return response


def next_monday_after(latest_complete_day: date) -> date:
    days_until_monday = (7 - latest_complete_day.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 1
    return latest_complete_day + timedelta(days=days_until_monday)


def first_day_next_month_after(latest_complete_day: date) -> date:
    if latest_complete_day.month == 12:
        return date(latest_complete_day.year + 1, 1, 1)
    return date(latest_complete_day.year, latest_complete_day.month + 1, 1)


def resolve_start_date_from_latest_complete(
    *,
    latest_complete_day: date,
    horizon_label: str,
    requested_start_date: Optional[date] = None,
) -> Dict[str, Any]:
    if requested_start_date:
        return {
            "start_date": requested_start_date,
            "start_date_mode": "manual",
            "start_date_source": "manual_body",
            "business_cutoff_rule": "manual_start_date",
            "latest_complete_day": latest_complete_day,
        }

    if horizon_label == "weekly":
        start_date = next_monday_after(latest_complete_day)
        source = "auto_weekly_complete_period"
        rule = "weekly_after_complete_operational_sunday_start_monday"
    elif horizon_label == "monthly":
        start_date = first_day_next_month_after(latest_complete_day)
        source = "auto_monthly_complete_period"
        rule = "monthly_after_complete_operational_month_start_first_day"
    else:
        start_date = latest_complete_day + timedelta(days=1)
        source = "auto_daily_complete_period"
        rule = "daily_after_close_or_24h_cutoff"

    return {
        "start_date": start_date,
        "start_date_mode": "auto",
        "start_date_source": source,
        "business_cutoff_rule": rule,
        "latest_complete_day": latest_complete_day,
    }


def _db_connect():
    try:
        import psycopg2
    except Exception as exc:  # pragma: no cover - depends on deployment package
        raise RuntimeError("psycopg2 tidak tersedia untuk scheduler idempotency") from exc

    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return psycopg2.connect(database_url, sslmode=os.getenv("DB_SSLMODE", "require"))

    return psycopg2.connect(
        host=os.getenv("DB_HOST", ""),
        port=os.getenv("DB_PORT", ""),
        user=os.getenv("DB_USER", ""),
        password=os.getenv("DB_PASSWORD", ""),
        dbname=os.getenv("DB_NAME", ""),
        sslmode=os.getenv("DB_SSLMODE", "disable"),
    )


def scheduler_run_exists(
    *,
    forecast_type: str,
    store_id: str,
    horizon_label: str,
    predict_start_date: Any,
    item_id: Optional[str] = None,
) -> bool:
    """Return True when a successful run already exists in DB for the same target.

    This keeps scheduler idempotency persistent across service restarts. The
    existing in-memory guard is still useful to avoid duplicate concurrent jobs
    in the same process before the DB insert finishes.
    """
    start = parse_start_date({"start_date": predict_start_date}) if not isinstance(predict_start_date, date) else predict_start_date
    if not start:
        return False

    try:
        with _db_connect() as conn:
            with conn.cursor() as cur:
                if item_id:
                    cur.execute(
                        """
                        SELECT 1
                        FROM public.forecast_runs fr
                        WHERE fr.store_id = %s::uuid
                          AND fr.forecast_type = %s
                          AND fr.horizon_label = %s
                          AND fr.status = 'success'
                          AND fr.predict_start_date = %s
                          AND EXISTS (
                              SELECT 1
                              FROM public.forecast_results res
                              WHERE res.run_id = fr.id
                                AND res.item_id = %s::uuid
                          )
                        LIMIT 1
                        """,
                        (store_id, forecast_type, horizon_label, start, item_id),
                    )
                else:
                    cur.execute(
                        """
                        SELECT 1
                        FROM public.forecast_runs fr
                        WHERE fr.store_id = %s::uuid
                          AND fr.forecast_type = %s
                          AND fr.horizon_label = %s
                          AND fr.status = 'success'
                          AND fr.predict_start_date = %s
                        LIMIT 1
                        """,
                        (store_id, forecast_type, horizon_label, start),
                    )
                return cur.fetchone() is not None
    except Exception as exc:
        # Do not block scheduler if DB check cannot be reached. Save path will
        # still go through backend validation/error handling.
        logger.warning(
            "Scheduler DB idempotency check skipped for %s/%s/%s/%s: %s",
            forecast_type,
            store_id,
            horizon_label,
            start,
            exc,
        )
        return False
