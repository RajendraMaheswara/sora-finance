# Forecast Service — Dokumentasi Developer

Folder `forecast-service/` adalah microservice Python untuk generate forecast, retrain model, dan menjalankan scheduler otomatis untuk modul visitors, sales, dan inventory.

## 1. Peran dalam sistem

Forecast-service bertugas:

1. Membaca data historis dari backend internal API.
2. Melakukan feature engineering dan prediksi.
3. Menyimpan hasil forecast ke backend internal API.
4. Menyimpan/memuat model dari filesystem `models/`.
5. Menjalankan scheduler opsional untuk semua store.
6. Menyediakan endpoint preview, save, dan retrain per modul.

Forecast-service **bukan** sumber kebenaran database. Database write tetap lewat backend Go.

## 2. Stack

| Komponen | Teknologi |
|---|---|
| Web framework | Flask 3 |
| ML visitors/sales | scikit-learn Random Forest |
| ML inventory | Prophet + cmdstanpy |
| Data processing | pandas, numpy |
| Model persistence | joblib + JSON metadata |
| Scheduler | APScheduler |
| HTTP client | requests + async client internal module |
| Env | python-dotenv |
| Optional DB idempotency check | psycopg2 |

## 3. Struktur folder

```text
forecast-service/
├── app.py                              # Flask app, route forecast, scheduler orchestration
├── config.py                           # Env config, model paths, backend URL, service key
├── requirements.txt                    # Dependency Python
├── swagger.yaml                        # Dokumentasi API forecast-service
├── scripts/
│   └── test_forecast_standard_endpoints.py
├── modules/
│   ├── shared/
│   │   └── forecast_helpers.py         # Helper request standard, horizon, start date, scheduler idempotency
│   ├── visitors/
│   │   ├── forecaster.py               # Visitors prediction, save, scheduler jobs, backend client
│   │   └── trainer.py                  # Visitors training/loading
│   ├── sales/
│   │   ├── forecaster.py               # Sales prediction, save, scheduler jobs, backend client
│   │   └── trainer.py                  # Sales training/loading
│   └── inventory/
│       ├── forecaster.py               # Inventory Prophet forecaster per store/ingredient/horizon
│       └── trainer.py                  # Inventory retrain async task per store
└── models/
    ├── visitors/                       # visitors model/metadata/scaler/features
    ├── sales/                          # sales model/metadata/scaler/features
    └── inventory/                      # inventory model/metadata/scaler/features
```

## 4. Entry point

Jalankan service dari root `forecast-service`:

```bash
python app.py
```

`app.py` melakukan:

1. Membuat Flask app.
2. Menerapkan `before_request` untuk validasi internal service key pada `/api/forecast/*`.
3. Register route visitors/sales/inventory.
4. Menginisialisasi scheduler jika `FORECAST_MODE=scheduler`.
5. Menjalankan service di port yang ditentukan environment.

## 5. Authentication antar-service

Semua endpoint dengan prefix `/api/forecast/` memerlukan service key jika `INTERNAL_SERVICE_KEY` diset.

Header yang diterima:

```http
X-Service-Key: <INTERNAL_SERVICE_KEY>
```

atau:

```http
Authorization: Bearer <INTERNAL_SERVICE_KEY>
```

Health check `/health` tidak memakai service key.

## 6. Endpoint aktif

### 6.1 Health

```text
GET /health
```

Response memberi status service, reachability backend Go, daftar model visitors loaded, dan timestamp.

### 6.2 Visitors

```text
GET  /api/forecast/visitors/models
POST /api/forecast/visitors/preview
POST /api/forecast/visitors/save
POST /api/forecast/visitors/retrain
```

Visitors memakai Random Forest/scikit-learn dengan feature engineering time-series seperti lag, rolling window, day-of-week/weekend, dan metadata metrics.

### 6.3 Sales

```text
POST /api/forecast/sales/preview
POST /api/forecast/sales/save
POST /api/forecast/sales/retrain
```

Sales memprediksi omzet. Output item tetap mempertahankan field domain seperti `predicted_omzet`, lalu menambahkan alias standar `predicted_value`.

### 6.4 Inventory

```text
POST /api/forecast/inventory/preview
POST /api/forecast/inventory/save
POST /api/forecast/inventory/retrain
GET  /api/forecast/inventory/retrain/status/{task_id}
```

Inventory memakai Prophet per store/ingredient/horizon. Jika `ingredient_id` tidak dikirim, service akan mencoba semua ingredient di store tersebut.

Default `/save` inventory all-store bersifat partial tolerant:

- Ingredient yang punya model/histori berhasil disimpan.
- Ingredient yang belum punya histori/model dilaporkan sebagai `warnings`/`skipped_ingredients`.
- Runtime failure dilaporkan sebagai `errors`.
- Kirim `allow_partial=false` untuk strict all-or-nothing.

## 7. Request body standar

### Visitors/Sales

```json
{
  "store_id": "<uuid-store>",
  "horizon_label": "daily",
  "horizon_count": 30
}
```

### Inventory single ingredient

```json
{
  "store_id": "<uuid-store>",
  "ingredient_id": "<uuid-ingredient>",
  "horizon_label": "weekly",
  "horizon_count": 4
}
```

### Inventory all ingredient

```json
{
  "store_id": "<uuid-store>",
  "horizon_label": "daily",
  "horizon_count": 30
}
```

### Optional start date

```json
{
  "store_id": "<uuid-store>",
  "horizon_label": "daily",
  "horizon_count": 30,
  "start_date": "2026-07-08"
}
```

`start_date` harus format `YYYY-MM-DD`. Bila kosong, service memilih start date otomatis.

## 8. Horizon dan start date

Validasi standar berada di:

```text
modules/shared/forecast_helpers.py
```

Limit `horizon_count`:

| Horizon | Maksimum |
|---|---:|
| `daily` | 90 |
| `weekly` | 52 |
| `monthly` | 24 |

Start date otomatis:

| Horizon | Aturan start date otomatis |
|---|---|
| daily | hari setelah latest complete operational day |
| weekly | Senin setelah minggu operasional lengkap |
| monthly | tanggal 1 bulan setelah bulan operasional lengkap |

Field metadata yang membantu debugging:

- `start_date_mode`: `auto` atau `manual`
- `start_date_source`
- `business_cutoff_rule`
- `latest_complete_day` / `last_actual_date`

## 9. Response envelope standar

Preview:

```json
{
  "status": "success",
  "message": "Preview forecast sales daily berhasil.",
  "request": {
    "module": "sales",
    "store_id": "<uuid-store>",
    "horizon_label": "daily",
    "horizon_count": 30,
    "start_date": null,
    "start_date_mode": "auto"
  },
  "data": {
    "store_id": "<uuid-store>",
    "forecast_start_date": "2026-07-08",
    "forecast_end_date": "2026-08-06",
    "forecasts": []
  }
}
```

Save:

```json
{
  "status": "success",
  "message": "Forecast sales daily berhasil dijalankan dan disimpan ke database.",
  "request": {},
  "save_result": {
    "status": "saved",
    "run_id": 123,
    "forecast_type": "sales",
    "horizon_label": "daily",
    "horizon_days": 30,
    "predict_start_date": "2026-07-08",
    "predict_end_date": "2026-08-06",
    "saved_results": 30,
    "backend_status": "success"
  },
  "data": {}
}
```

Retrain:

```json
{
  "status": "success",
  "message": "Retrain visitors berhasil.",
  "request": {
    "module": "visitors",
    "store_id": "<uuid-store>",
    "force": true
  },
  "data": {}
}
```

## 10. Save ke backend

Save ideal menggunakan backend internal route:

```text
POST {BACKEND_API_URL}/save
```

Dengan `BACKEND_API_URL=http://localhost:8080/internal/forecast`, URL final adalah:

```text
POST http://localhost:8080/internal/forecast/save
```

Payload:

```json
{
  "run": {
    "store_id": "<uuid-store>",
    "forecast_type": "sales",
    "horizon_label": "daily",
    "horizon_days": 30,
    "granularity": "daily",
    "model_name": "random forest individual",
    "model_version": "sales-rf-v2-aggregated",
    "feature_version": "v2",
    "train_start_date": "2026-01-01",
    "train_end_date": "2026-07-07",
    "predict_start_date": "2026-07-08",
    "predict_end_date": "2026-08-06",
    "metrics": "{}",
    "summary": "{}",
    "data_quality": "{}",
    "status": "success"
  },
  "results": [
    {
      "target_date": "2026-07-08",
      "predicted_value": 1000000,
      "lower_bound": 800000,
      "upper_bound": 1200000,
      "confidence_level": 80,
      "item_type": "sales"
    }
  ]
}
```

Catatan teknis: beberapa save path lama di modul sales/inventory masih terlihat menggunakan dua langkah `/forecast-runs` lalu `/forecast-results`. Untuk konsistensi dan atomicity, developer berikutnya sebaiknya memigrasikan semua modul ke `/save` atomik.

## 11. Scheduler

Aktif jika:

```env
FORECAST_MODE=scheduler
```

Scheduler menjalankan tiga job interval:

- `visitors_auto_forecast_check`
- `sales_auto_forecast_check`
- `inventory_auto_forecast_check`

Scheduler menggunakan:

1. **In-memory guard** untuk mencegah job ganda dalam proses yang sama.
2. **DB idempotency check** via `scheduler_run_exists()` agar job tidak diulang setelah service restart.

DB idempotency check membaca `forecast_runs` dan `forecast_results` langsung via `psycopg2`; karena itu env DB perlu valid jika scheduler aktif.

## 12. Model storage

Folder model:

```text
models/visitors/
models/sales/
models/inventory/
```

Tipe file yang ditemukan:

- `.joblib`: model/scaler.
- `.json`: metadata, feature list, metrics.

Untuk MVP, filesystem lokal cukup. Untuk production serius:

- gunakan volume persistent,
- jangan commit model besar ke repo,
- pertimbangkan object storage,
- tambahkan model version registry minimal.

## 13. Cara menjalankan lokal

```bash
cd forecast-service
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Health check:

```bash
curl http://localhost:5000/health
```

Contoh visitors preview:

```bash
curl -X POST http://localhost:5000/api/forecast/visitors/preview \
  -H "Content-Type: application/json" \
  -H "X-Service-Key: $INTERNAL_SERVICE_KEY" \
  -d '{"store_id":"<uuid-store>","horizon_label":"daily","horizon_count":30}'
```

Contoh inventory retrain:

```bash
curl -X POST http://localhost:5000/api/forecast/inventory/retrain \
  -H "Content-Type: application/json" \
  -H "X-Service-Key: $INTERNAL_SERVICE_KEY" \
  -d '{"store_id":"<uuid-store>","force":true}'
```

Cek retrain inventory:

```bash
curl http://localhost:5000/api/forecast/inventory/retrain/status/<task_id> \
  -H "X-Service-Key: $INTERNAL_SERVICE_KEY"
```