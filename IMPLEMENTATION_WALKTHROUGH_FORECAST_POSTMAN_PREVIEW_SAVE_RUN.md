# Implementation Walkthrough - Forecast Postman Preview/Save/Run

## Tujuan
Forecast-service dipakai internal melalui Postman, bukan frontend. Karena itu alur dibuat eksplisit:

1. `preview` = hitung forecast dan return hasil, belum simpan database.
2. `save` = simpan payload hasil preview ke database backend Go.
3. `run` = hitung forecast lalu langsung simpan database, untuk scheduler/production nanti.

## File yang diubah

- `forecast-service/app.py`
- `forecast-service/config.py`
- `forecast-service/.env.example`

## Route final

### Preview tanpa simpan DB

- `POST /api/forecast/sales/preview`
- `POST /api/forecast/visitors/preview`
- `POST /api/forecast/inventory/preview`
- `POST /api/forecast/preview-all`

### Save hasil preview ke DB

- `POST /api/forecast/sales/save`
- `POST /api/forecast/visitors/save`
- `POST /api/forecast/inventory/save`
- `POST /api/forecast/save-all`

### Run + save langsung

- `POST /api/forecast/sales/run`
- `POST /api/forecast/visitors/run`
- `POST /api/forecast/inventory/run`
- `POST /api/forecast/run-all`

### Retrain tetap tersedia

- `POST /api/forecast/sales/retrain`
- `POST /api/forecast/visitors/retrain`
- `POST /api/forecast/inventory/retrain`
- `POST /api/forecast/retrain-all`

## Catatan penting untuk Postman

Save/run ke backend Go membutuhkan JWT jika endpoint backend masih dilindungi auth.
Token bisa dikirim dengan salah satu cara:

1. Body request:

```json
{
  "backend_token": "ISI_TOKEN_ADMIN_ATAU_OWNER",
  "store_id": "uuid-store",
  "horizon_label": "weekly",
  "force": true
}
```

2. Atau `.env` forecast-service:

```env
BACKEND_AUTH_TOKEN=ISI_TOKEN_ADMIN_ATAU_OWNER
```

Untuk `preview`, token backend tidak diperlukan karena tidak post ke database.

## Contoh preview

```http
POST http://localhost:5000/api/forecast/sales/preview
```

```json
{
  "store_id": "uuid-store",
  "horizon_label": "weekly",
  "force": true
}
```

## Contoh save dari hasil preview

```http
POST http://localhost:5000/api/forecast/sales/save
```

```json
{
  "backend_token": "ISI_TOKEN_ADMIN_ATAU_OWNER",
  "forecast": {
    "store_id": "uuid-store",
    "module": "sales",
    "horizon_label": "weekly",
    "horizon_days": 7,
    "granularity": "daily",
    "predict_start_date": "2026-06-19",
    "predict_end_date": "2026-06-25",
    "results": [
      {
        "target_date": "2026-06-19",
        "predicted_value": 1800000,
        "lower_bound": 1500000,
        "upper_bound": 2100000
      }
    ]
  }
}
```

## Contoh run + save langsung

```http
POST http://localhost:5000/api/forecast/run-all
```

```json
{
  "backend_token": "ISI_TOKEN_ADMIN_ATAU_OWNER",
  "store_id": "uuid-store",
  "horizon_label": "weekly",
  "force": true
}
```

## Env development

```env
FORECAST_MODE=manual
ENABLE_FORECAST_SCHEDULER=false
BACKEND_API_URL=http://localhost:8080/api
BACKEND_AUTH_TOKEN=
BACKEND_REQUEST_TIMEOUT_SECONDS=30
```

## Verifikasi syntax

Perubahan sudah dicek dengan:

```bash
python -m py_compile app.py config.py modules/sales/forecaster.py modules/inventory/forecaster.py modules/inventory/trainer.py modules/visitors/forecaster.py modules/visitors/trainer.py
```
