# Sora Forecast Service

Dokumen ini mengikuti standar terbaru setelah endpoint `/run` dihapus. Sekarang alur forecast hanya memakai:

- `POST /api/forecast/{module}/preview` untuk generate forecast tanpa simpan DB.
- `POST /api/forecast/{module}/save` untuk generate forecast lalu simpan ke backend/database.
- `POST /api/forecast/{module}/retrain` untuk retrain model.

Module yang didukung: `visitors`, `sales`, dan `inventory`.

## Auth

Endpoint forecast-service menerima internal service key lewat salah satu header berikut:

```http
X-Service-Key: <INTERNAL_SERVICE_KEY>
```

atau:

```http
Authorization: Bearer <INTERNAL_SERVICE_KEY>
```

Saat forecast-service menyimpan hasil ke backend Go, service otomatis mengambil `INTERNAL_SERVICE_KEY` dari `.env` dan mengirim `X-Service-Key`. Client/Postman tidak perlu mengirim token backend/JWT ke body request.

## Environment

Gunakan `.env.example` sebagai template. File `.env` asli tidak boleh ikut commit/zip.

```env
BACKEND_API_URL=http://localhost:8080/internal/forecast
GOLANG_API_BASE_URL=http://localhost:8080/internal/forecast
GOLANG_INTERNAL_API_BASE_URL=http://localhost:8080/internal/forecast
INTERNAL_SERVICE_KEY=change-me
BACKEND_REQUEST_TIMEOUT_SECONDS=30
FORECAST_MODE=manual
FORECAST_SCHEDULER_TIMEZONE=Asia/Jakarta
FORECAST_SCHEDULER_CHECK_INTERVAL_MINUTES=15
SCHEDULER_RETRAIN=true
```

## Standard body

### Visitors dan sales

```json
{
  "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
  "horizon_label": "daily",
  "horizon_count": 30
}
```

### Inventory

Single ingredient:

```json
{
  "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
  "ingredient_id": "b98b5042-30b5-4dc7-80ce-7dbb4797c4c7",
  "horizon_label": "weekly",
  "horizon_count": 4
}
```

Semua ingredient dalam store:

```json
{
  "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
  "horizon_label": "daily",
  "horizon_count": 30
}
```

Untuk `/api/forecast/inventory/save` tanpa `ingredient_id`, default behavior adalah partial-tolerant: ingredient yang berhasil tetap disimpan, sedangkan ingredient yang ada di master tetapi belum punya histori/model forecast dilaporkan sebagai `warnings`/`skipped_ingredients`, bukan fatal error. `errors` hanya untuk kegagalan runtime yang benar-benar gagal. Kirim `"allow_partial": false` jika ingin mode strict all-or-nothing.

`start_date` opsional dan harus format `YYYY-MM-DD`. Jika tidak dikirim, service akan memakai start date otomatis berdasarkan complete operational period.

## Limit horizon_count

| horizon_label | Maksimal horizon_count |
|---|---:|
| daily | 90 |
| weekly | 52 |
| monthly | 24 |

Limit ini berlaku untuk visitors, sales, dan inventory.

## Endpoint aktif

| Modul | Preview | Save generate + save | Retrain | Status retrain |
|---|---|---|---|---|
| Visitors | `POST /api/forecast/visitors/preview` | `POST /api/forecast/visitors/save` | `POST /api/forecast/visitors/retrain` | - |
| Sales | `POST /api/forecast/sales/preview` | `POST /api/forecast/sales/save` | `POST /api/forecast/sales/retrain` | - |
| Inventory | `POST /api/forecast/inventory/preview` | `POST /api/forecast/inventory/save` | `POST /api/forecast/inventory/retrain` | `GET /api/forecast/inventory/retrain/status/{task_id}` |

Endpoint `/api/forecast/{module}/run` sudah dihapus. Gunakan `/save` untuk kebutuhan generate + save.

## Response standar preview

```json
{
  "status": "success",
  "message": "Preview forecast sales daily berhasil.",
  "request": {
    "module": "sales",
    "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
    "horizon_label": "daily",
    "horizon_count": 30,
    "start_date": null,
    "start_date_mode": "auto"
  },
  "data": {
    "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
    "forecast_start_date": "2026-07-06",
    "forecast_end_date": "2026-08-04",
    "forecasts": []
  }
}
```

Sales forecast item sekarang tetap punya field spesifik `predicted_omzet`, dan juga alias standar `predicted_value`.

## Response standar save

```json
{
  "status": "success",
  "message": "Forecast sales daily berhasil dijalankan dan disimpan ke database.",
  "request": {
    "module": "sales",
    "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
    "horizon_label": "daily",
    "horizon_count": 30,
    "start_date": null,
    "start_date_mode": "auto"
  },
  "save_result": {
    "status": "saved",
    "message": "Forecast sales daily berhasil disimpan ke backend.",
    "run_id": 123,
    "forecast_type": "sales",
    "horizon_label": "daily",
    "horizon_days": 30,
    "predict_start_date": "2026-07-06",
    "predict_end_date": "2026-08-04",
    "saved_results": 30,
    "backend_status": "success"
  },
  "data": {}
}
```

`save_result` visitors, sales, dan inventory sekarang memakai field publik yang sama.

## Retrain

Semua modul memakai wrapper response yang sama:

```json
{
  "status": "success",
  "message": "Retrain visitors berhasil.",
  "request": {
    "module": "visitors",
    "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
    "force": true
  },
  "data": {}
}
```

### Contoh retrain inventory async

Inventory retrain bisa berjalan beberapa menit per store, jadi endpoint ini mengembalikan `task_id` langsung dengan HTTP `202`.

```bash
curl -X POST http://localhost:5000/api/forecast/inventory/retrain \
  -H "Content-Type: application/json" \
  -H "X-Service-Key: $INTERNAL_SERVICE_KEY" \
  -d '{"store_id":"b4e2f559-9615-4263-84fe-9ee97780748f","force":true}'
```

Contoh response awal:

```json
{
  "status": "queued",
  "message": "Inventory retrain job started.",
  "task_id": "0d2731f1-4b85-4e0e-98a5-5a3a8fdf6d11",
  "request": {
    "module": "inventory",
    "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
    "force": true
  },
  "data": {
    "status": "queued",
    "progress": {"total": 3, "processed": 0, "failed": 0, "percentage": 0}
  }
}
```

Cek status:

```bash
curl http://localhost:5000/api/forecast/inventory/retrain/status/0d2731f1-4b85-4e0e-98a5-5a3a8fdf6d11 \
  -H "X-Service-Key: $INTERNAL_SERVICE_KEY"
```

## Scheduler

Scheduler tetap berjalan per modul saat `FORECAST_MODE=scheduler`. Idempotency sekarang memakai dua lapis:

1. In-memory guard untuk mencegah job ganda dalam proses yang sama.
2. DB check ke `public.forecast_runs` dan `public.forecast_results` agar job yang sama tidak diulang setelah service restart.

## Test otomatis

Gunakan script:

```bash
python scripts/test_forecast_standard_endpoints.py \
  --base-url http://localhost:5000 \
  --service-key "$INTERNAL_SERVICE_KEY" \
  --store-id b4e2f559-9615-4263-84fe-9ee97780748f \
  --ingredient-id b98b5042-30b5-4dc7-80ce-7dbb4797c4c7
```

Script mengetes `daily`, `weekly`, dan `monthly` untuk preview + save semua modul, sekaligus memastikan `/run` sudah tidak tersedia.

## Swagger/OpenAPI

Spesifikasi endpoint forecast-service ada di `forecast-service/swagger.yaml`.
