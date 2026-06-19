# Phase 3 — Internal Service Key untuk Forecast-Service

## Tujuan

Forecast-service tidak lagi perlu token login JWT dari backend. Komunikasi forecast-service Python ke backend Go memakai service key internal:

```http
X-Service-Key: <INTERNAL_SERVICE_KEY>
X-Store-ID: <store_id>
```

Endpoint internal backend tetap tidak terbuka bebas. Semua route internal forecast wajib membawa service key valid dan store scope valid.

## Backend Go

### Env backend

Tambahkan di `backend/.env`:

```env
INTERNAL_SERVICE_KEY=sora-forecast-internal-key-ganti-yang-panjang
```

Nilainya harus sama dengan `forecast-service/.env`.

### Route internal baru

```http
GET  /internal/health
GET  /internal/forecast/stores
GET  /internal/forecast/orders
GET  /internal/forecast/order-items
GET  /internal/forecast/food-ingredients
GET  /internal/forecast/ingredient-stock-histories
GET  /internal/forecast/sales-daily-summaries
GET  /internal/forecast/sales-monthly-summaries
GET  /internal/forecast/forecast-predictions
GET  /internal/forecast/forecast-results

POST /internal/forecast/forecast-predictions
POST /internal/forecast/forecast-runs
POST /internal/forecast/forecast-results
```

Semua route `/internal/forecast/*` wajib membawa:

```http
X-Service-Key: sora-forecast-internal-key-ganti-yang-panjang
X-Store-ID: uuid-store
```

atau `store_id` di query/body.

Alias lama `/internal/api/*` juga tetap disediakan agar tidak mematahkan draft Phase 3 sebelumnya.

## Forecast-Service Python

### Env forecast-service

Tambahkan di `forecast-service/.env`:

```env
BACKEND_API_URL=http://localhost:8080/internal/forecast
GOLANG_API_BASE_URL=http://localhost:8080/internal/forecast
INTERNAL_SERVICE_KEY=sora-forecast-internal-key-ganti-yang-panjang
BACKEND_AUTH_TOKEN=
FORECAST_MODE=manual
ENABLE_FORECAST_SCHEDULER=false
BACKEND_REQUEST_TIMEOUT_SECONDS=30
```

Dengan konfigurasi ini, forecast-service tidak membutuhkan token login user.

## Alur test Postman

1. Jalankan backend Go.
2. Jalankan forecast-service Python.
3. Test backend internal tanpa key:

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8080/internal/forecast/orders?store_id=b4e2f559-9615-4263-84fe-9ee97780748f"
```

Expected: `401 invalid service key`.

4. Test backend internal dengan key:

```powershell
$headers = @{
  "X-Service-Key" = "sora-forecast-internal-key-ganti-yang-panjang"
  "X-Store-ID" = "b4e2f559-9615-4263-84fe-9ee97780748f"
}

Invoke-RestMethod -Method Get -Uri "http://localhost:8080/internal/forecast/orders" -Headers $headers
```

Expected: return data store tersebut saja.

5. Test forecast-service preview:

```http
POST http://localhost:5000/api/forecast/sales/preview
```

```json
{
  "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
  "horizon_label": "weekly",
  "force": true
}
```

Forecast-service otomatis mengirim `X-Service-Key` dan `X-Store-ID` ke backend.

## Catatan penting

- `/api/*` backend tetap untuk frontend/user dan tetap memakai JWT.
- `/internal/forecast/*` backend hanya untuk forecast-service dan memakai `X-Service-Key`.
- Forecast-service tidak perlu login backend lagi.
- Preview tidak menyimpan database.
- Save dan run menyimpan ke database melalui endpoint internal backend.
- Semua request Python ke backend diberi timeout melalui `BACKEND_REQUEST_TIMEOUT_SECONDS`.
