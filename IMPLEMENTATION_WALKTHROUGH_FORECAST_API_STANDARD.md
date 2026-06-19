# Implementation Walkthrough — Forecast API Standardization

## Tujuan

Menstandarkan route forecast-service untuk 3 modul forecast:

- sales
- visitors
- inventory

Route baru mengikuti kontrak final:

- `POST /api/forecast/sales/run`
- `POST /api/forecast/visitors/run`
- `POST /api/forecast/inventory/run`
- `POST /api/forecast/run-all`
- `POST /api/forecast/sales/retrain`
- `POST /api/forecast/visitors/retrain`
- `POST /api/forecast/inventory/retrain`
- `POST /api/forecast/retrain-all`

Route lama tetap dipertahankan sebagai legacy wrapper agar pengujian sebelumnya tidak langsung rusak.

## File yang Diubah

- `forecast-service/app.py`
- `forecast-service/config.py`
- `forecast-service/.env.example`

## Perubahan Utama

### 1. Scheduler tidak otomatis aktif di development

Ditambahkan env:

```env
FORECAST_MODE=manual
ENABLE_FORECAST_SCHEDULER=false
FORECAST_RUN_AFTER_CLOSE_MINUTES=60
FORECAST_24H_RUN_TIME=02:00
BACKEND_REQUEST_TIMEOUT_SECONDS=30
```

Saat `FORECAST_MODE=manual`, scheduler tidak start otomatis. Ini cocok untuk testing dengan Postman atau frontend.

Scheduler baru aktif jika:

```env
FORECAST_MODE=scheduler
ENABLE_FORECAST_SCHEDULER=true
```

### 2. Body request distandarkan

Semua route baru menerima:

```json
{
  "store_id": "uuid-store",
  "horizon_label": "weekly",
  "force": true
}
```

Untuk inventory bisa menambahkan:

```json
{
  "ingredient_id": "uuid-ingredient"
}
```

`m_store_id` masih diterima sebagai fallback legacy, tetapi standar final tetap `store_id`.

### 3. Weekly dan monthly tetap daily granularity

- `weekly` menghasilkan 7 row harian.
- `monthly` menghasilkan 28/29/30/31 row harian, sesuai jumlah hari pada bulan target.

### 4. Run all

`POST /api/forecast/run-all` menjalankan modul yang dipilih:

```json
{
  "store_id": "uuid-store",
  "horizon_label": "weekly",
  "modules": ["sales", "visitors", "inventory"],
  "force": true
}
```

Jika `modules` tidak dikirim, default-nya menjalankan semua modul.

### 5. Retrain all

`POST /api/forecast/retrain-all` menjalankan retrain modul yang dipilih. Sales dan inventory berjalan async memakai `task_id`; visitors masih berjalan langsung karena function retrain visitors existing sudah async/sync-safe melalui `asyncio.run`.

## Catatan Implementasi

- Route `sales/run` memakai model global sales existing dan memaksa output menjadi daily rows sesuai kontrak baru.
- Route `visitors/run` memakai `visitors_forecast_service.forecast()` agar weekly/monthly tetap daily rows.
- Route `inventory/run` memakai `InventoryForecaster.predict(periods=horizon_days, freq="D")` agar output tetap harian.
- Jika `ingredient_id` kosong pada inventory, service mencari model inventory existing berdasarkan file model `model_store{store_id}_ingr{ingredient_id}.pkl`.

## Legacy Routes

Route lama tetap ada:

- `/api/forecast/penjualan-harian`
- `/api/forecast/penjualan-mingguan`
- `/api/forecast/penjualan-bulanan`
- `/api/inventory/forecast`
- `/api/forecast/visitors/daily`
- `/api/forecast/visitors/predict-weekly`
- `/api/forecast/visitors/predict-monthly`

Tambahan legacy wrapper baru:

- `/api/forecast/visitors/weekly`
- `/api/forecast/visitors/monthly`

## Testing

Jalankan:

```powershell
cd forecast-service
python -m py_compile app.py config.py modules/sales/forecaster.py modules/inventory/forecaster.py modules/inventory/trainer.py modules/visitors/forecaster.py modules/visitors/trainer.py
python app.py
```

Test endpoint:

```http
POST http://localhost:5000/api/forecast/sales/run
POST http://localhost:5000/api/forecast/visitors/run
POST http://localhost:5000/api/forecast/inventory/run
POST http://localhost:5000/api/forecast/run-all
```

Body:

```json
{
  "store_id": "uuid-store",
  "horizon_label": "weekly",
  "force": true
}
```

Inventory satu bahan:

```json
{
  "store_id": "uuid-store",
  "ingredient_id": "uuid-ingredient",
  "horizon_label": "weekly",
  "force": true
}
```
