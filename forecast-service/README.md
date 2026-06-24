# Forecast Service Full Guide - Sora Finance

## Hal yang perlu diluruskan lebih dulu

`forecast-service` saat ini adalah service Python Flask yang menjalankan forecast untuk tiga domain: `visitors`, `sales`, dan `inventory`.

Guide ini memakai kontrak route standar yang sama untuk tiga modul utama:

```text
POST /api/forecast/{module}/preview
POST /api/forecast/{module}/save
POST /api/forecast/{module}/run
```

Dengan `{module}`:

```text
visitors
sales
inventory
```

Kontrak standar per modul:

```text
POST /api/forecast/visitors/preview
POST /api/forecast/visitors/save
POST /api/forecast/visitors/run

POST /api/forecast/sales/preview
POST /api/forecast/sales/save
POST /api/forecast/sales/run

POST /api/forecast/inventory/preview
POST /api/forecast/inventory/save
POST /api/forecast/inventory/run
```

Body standar untuk `visitors`, `sales`, dan `inventory` dibuat seragam:

```json
{
 "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
 "horizon_label": "daily",
 "horizon_count": 30
}
```

Untuk inventory, body standar perlu tambahan `ingredient_id` jika forecast hanya untuk satu bahan:

```json
{
 "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
 "ingredient_id": "uuid-ingredient",
 "horizon_label": "weekly",
 "horizon_count": 1
}
```

Jika `ingredient_id` tidak dikirim, inventory menjalankan forecast untuk semua ingredient aktif pada store tersebut.

`app.py` menjalankan Flask dengan `port=5000` secara hardcoded. Nilai `SERVICE_PORT` di `.env.example` tidak dipakai oleh `app.py` saat ini.

## 1. Fungsi forecast-service

`forecast-service` adalah service terpisah dari backend Go. Tugasnya:

1. Mengambil data historis dari backend/internal API Go atau fallback direct database pada beberapa modul.
2. Melakukan preprocessing data historis.
3. Melatih model machine learning.
4. Menyimpan artifact model ke folder `models/`.
5. Menghasilkan forecast harian, mingguan, atau bulanan.
6. Menyimpan hasil forecast ke database/backend sesuai modul.

Arsitektur sederhananya:

```text
Frontend/Postman
 |
 v
forecast-service Flask :5000
 |
 | ambil data historis
 v
backend Go :8080 / internal forecast API
 |
 v
PostgreSQL/Supabase

forecast-service juga menyimpan model lokal:
forecast-service/models/{visitors,sales,inventory}/...
```

## 2. Struktur folder utama

```text
forecast-service/
├── app.py
├── config.py
├── requirements.txt
├── test_db.py
├── README.md
├── .env.example
├── models/
│ ├── visitors/
│ ├── sales/
│ └── inventory/
└── modules/
 ├── visitors/
 │ ├── forecaster.py
 │ ├── trainer.py
 │ └── README.md
 ├── sales/
 │ ├── forecaster.py
 │ └── trainer.py
 └── inventory/
 ├── forecaster.py
 └── trainer.py
```

Penjelasan:

- `app.py`: entry point Flask dan definisi semua route HTTP.
- `config.py`: pembacaan `.env`, path model, URL backend, DB config, service key header.
- `requirements.txt`: dependency Python.
- `modules/visitors`: forecast pengunjung.
- `modules/sales`: forecast omzet/penjualan.
- `modules/inventory`: forecast penggunaan stok bahan.
- `models/`: artifact model hasil training.

## 3. Dependency dan model yang dipakai

Visitors memakai `RandomForestRegressor` dari scikit-learn.

Sales memakai `RandomForestRegressor` dari scikit-learn.

Inventory memakai `Prophet`.

Dependency penting:

```text
flask
pandas
numpy
scikit-learn
joblib
requests
httpx
psycopg2-binary
APScheduler
prophet
cmdstanpy
holidays
python-dotenv
```

## 4. Environment `.env`

Buat file:

```text
forecast-service/.env
```

Contoh minimal untuk development lokal:

```env
GOLANG_API_BASE_URL=http://localhost:8080/internal/forecast
BACKEND_API_URL=http://localhost:8080/internal/forecast
INTERNAL_SERVICE_KEY=isi_key_yang_sama_dengan_backend
BACKEND_REQUEST_TIMEOUT_SECONDS=30

DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=postgres
DB_SSLMODE=disable

FORECAST_HORIZON_DAYS=30
RETRAIN_INTERVAL_DAYS=7
TRAINING_MAX_WORKERS=2
```

Contoh untuk Supabase:

```env
GOLANG_API_BASE_URL=http://localhost:8080/internal/forecast
BACKEND_API_URL=http://localhost:8080/internal/forecast
INTERNAL_SERVICE_KEY=isi_key_yang_sama_dengan_backend
BACKEND_REQUEST_TIMEOUT_SECONDS=30

DB_HOST=aws-xxx.pooler.supabase.com
DB_PORT=5432
DB_USER=postgres.xxx
DB_PASSWORD=password_supabase
DB_NAME=postgres
DB_SSLMODE=require

FORECAST_HORIZON_DAYS=30
RETRAIN_INTERVAL_DAYS=7
TRAINING_MAX_WORKERS=1
```

Catatan penting:

- `INTERNAL_SERVICE_KEY` dipakai oleh `Config.backend_headers()` sebagai header `X-Service-Key`.
- Backend Go internal route juga memakai `INTERNAL_SERVICE_KEY`. Nilainya harus sama di backend dan forecast-service.
- `SERVICE_PORT` di `.env.example` tidak dipakai oleh `app.py` saat ini karena port Flask hardcoded `5000`.

## 5. Cara menjalankan lokal

Masuk ke folder:

```powershell
cd forecast-service
```

Buat virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

Untuk Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependency:

```bash
pip install -r requirements.txt
```

Cek syntax:

```bash
python -m py_compile app.py config.py modules/visitors/forecaster.py modules/visitors/trainer.py modules/sales/forecaster.py modules/sales/trainer.py modules/inventory/forecaster.py modules/inventory/trainer.py
```

Jalankan:

```bash
python app.py
```

Service berjalan di:

```text
http://localhost:5000
```

Health check:

```http
GET http://localhost:5000/health
```

Response health check saat backend reachable:

```json
{
 "status": "healthy",
 "service": "sora-forecast-service",
 "version": "1.0.0",
 "golang_api_reachable": true,
 "loaded_models": ["..."],
 "timestamp": "..."
}
```

Jika backend tidak reachable, status menjadi `degraded`.

## 6. Integrasi dengan backend Go

Backend Go menyediakan route internal khusus forecast-service:

```text
GET /internal/health
GET /internal/forecast/stores
GET /internal/forecast/orders
GET /internal/forecast/visitors-daily-history
GET /internal/forecast/order-items
GET /internal/forecast/store-operational-hours
GET /internal/forecast/food-ingredients
GET /internal/forecast/ingredient-stock-histories
GET /internal/forecast/sales-daily-summaries
GET /internal/forecast/sales-monthly-summaries
POST /internal/forecast/forecast-predictions
POST /internal/forecast/forecast-runs
POST /internal/forecast/forecast-results
```

Backend internal route diproteksi oleh `X-Service-Key`.

Forecast-service mengirim header:

```http
X-Service-Key: <INTERNAL_SERVICE_KEY>
```

Jika muncul error 401/403 dari backend internal route, cek tiga hal:

1. `INTERNAL_SERVICE_KEY` di backend Go sudah diisi.
2. `INTERNAL_SERVICE_KEY` di forecast-service sama persis.
3. `BACKEND_API_URL` dan `GOLANG_API_BASE_URL` mengarah ke `/internal/forecast`, bukan `/api`, bila memakai internal route.

## 7. Tabel database yang dipakai

Tabel utama untuk hasil forecast baru:

```text
public.forecast_runs
public.forecast_results
```

`forecast_runs` menyimpan metadata satu kali run forecast:

- `store_id`
- `forecast_type`: `visitors`, `sales`, atau `inventory`
- `horizon_label`: `daily`, `weekly`, `monthly`
- `horizon_days`
- `granularity`
- `model_name`
- `model_version`
- `feature_version`
- `train_start_date`
- `train_end_date`
- `predict_start_date`
- `predict_end_date`
- `metrics`
- `summary`
- `data_quality`
- `status`
- `is_latest`
- `started_at`
- `finished_at`

`forecast_results` menyimpan baris prediksi per tanggal/periode:

- `run_id`
- `target_date`
- `predicted_value`
- `lower_bound`
- `upper_bound`
- `confidence_level`
- `actual_value`
- `item_id`
- `item_type`

## 8. Konsep `preview`, `save`, dan `run`

Konsep standar:

```text
preview = hitung forecast, tidak simpan database
save = simpan hasil forecast ke database
run = hitung forecast lalu langsung simpan database
```

Kontrak route standar:

```text
POST /api/forecast/{module}/preview
POST /api/forecast/{module}/save
POST /api/forecast/{module}/run
```

### Penjelasan Route

- `preview`: hitung forecast, tidak simpan.
- `save`: hitung forecast dari body standar, lalu simpan.
- `run`: hitung forecast dari body standar, lalu simpan.


## 9. Horizon forecast

Horizon standar:

```text
daily = horizon_count hari
weekly = horizon_count minggu
monthly = horizon_count bulan
```

Body standar untuk visitors, sales, dan inventory:

```json
{
 "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
 "horizon_label": "daily",
 "horizon_count": 30
}
```

Weekly:

```json
{
 "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
 "horizon_label": "weekly",
 "horizon_count": 1
}
```

Monthly:

```json
{
 "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
 "horizon_label": "monthly",
 "horizon_count": 1
}
```

Optional `start_date`:

```json
{
 "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
 "horizon_label": "daily",
 "horizon_count": 30,
 "start_date": "2026-07-02"
}
```

Inventory single ingredient memakai body standar plus `ingredient_id`:

```json
{
 "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
 "ingredient_id": "uuid-ingredient",
 "horizon_label": "daily",
 "horizon_count": 30,
 "start_date": "2026-07-02"
}
```

Aturan `start_date`:

- Daily: jika kosong, mulai dari tanggal server hari ini.
- Weekly: jika kosong, mulai dari tanggal hari ini dan menghasilkan agregasi 7 hari berurutan.
- Monthly: jika kosong, mulai dari bulan penuh berikutnya; jika `start_date` dikirim, bulan pertama mengikuti bulan `start_date`.

Aturan inventory:

- Jika `ingredient_id` dikirim, forecast hanya untuk ingredient tersebut.
- Jika `ingredient_id` tidak dikirim, forecast untuk semua ingredient aktif pada store.
- Untuk `daily`, hasil disimpan per tanggal.
- Untuk `weekly`, hasil bisa disimpan pada tanggal awal periode minggu.
- Untuk `monthly`, hasil bisa disimpan pada tanggal awal bulan.

## 10. Modul Visitors

### 10.1 Fungsi

Visitors forecast memprediksi pengunjung fisik outlet.

Target visitors tidak sekadar jumlah transaksi. Kode memakai rule `items_capped`:

```text
order online = 0 visitor fisik
order fisik qty 0–3 item = 1 visitor
order fisik qty 4–5 item = 2 visitors
order fisik qty 6–8 item = 3 visitors
order fisik qty >8 item = 4 visitors
```

Order yang valid:

- `deleted_at` kosong.
- `cancelled_at` kosong.
- `m_order_status_id` bukan 3.
- `m_order_status_id = 2` atau `m_order_payment_status_id = 200`.

Order online dihitung 0 visitors fisik, karena dianggap bukan pengunjung outlet.

### 10.2 Data source visitors

Urutan data source:

1. Forecast-service memanggil backend:

```text
GET {GOLANG_API_BASE_URL}/visitors-daily-history?store_id=...
GET {GOLANG_API_BASE_URL}/store-operational-hours?store_id=...
```

2. Jika `visitors-daily-history` tidak tersedia, fallback ke:

```text
GET {GOLANG_API_BASE_URL}/orders?store_id=...
GET {GOLANG_API_BASE_URL}/order-items?store_id=...
```

3. Jika `store-operational-hours` gagal, kode fallback default toko dianggap buka 24 jam.

Fetch visitors historis sengaja diarahkan ke backend/internal API agar tidak menambah session Supabase pooler untuk retrain/preview.

### 10.3 Feature engineering visitors

Fitur utama:

- `day_of_week`
- `day_of_month`
- `month`
- `quarter`
- `week_of_year`
- `is_weekend`
- `is_month_start`
- `is_month_end`
- `sin_dow`, `cos_dow`
- `sin_month`, `cos_month`
- lag visitors: `lag_1`, `lag_2`, `lag_3`, `lag_7`, `lag_14`, `lag_21`, `lag_28`
- rolling window: `rolling_mean_7`, `rolling_std_7`, `rolling_max_7`, `rolling_min_7`, dan window 14/28
- `expanding_mean`
- fitur operasional: `is_store_open`, `open_duration_hours`, `is_24_hours`
- lag/rolling channel: online/dine-in/takeaway ratio bila tersedia

Data tanggal yang bolong dilengkapi menjadi full daily range, dan nilai numerik kosong diisi 0.

Baris awal akan hilang setelah feature engineering karena butuh lag maksimal 28 hari. Karena itu minimal data historis adalah 30 hari, tetapi semakin panjang data semakin bagus.

### 10.4 Training visitors

Endpoint:

```http
POST http://localhost:5000/api/forecast/visitors/retrain
```

Body:

```json
{
 "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
 "force": true
}
```

Response berisi:

- `store_id`
- `status`
- `message`
- `training_data_points`
- `cv_mae`
- `cv_rmse`
- `trained_at`
- `feature_importance`

Training menghasilkan artifact:

```text
models/visitors/visitors_daily_model_store_<store_id>.joblib
models/visitors/visitors_daily_scaler_store_<store_id>.joblib
models/visitors/visitors_daily_features_store_<store_id>.json
models/visitors/visitors_daily_metadata_store_<store_id>.json
```

Jika model belum ada atau feature version lama, forecast visitors akan auto-retrain.

### 10.5 List model visitors

```http
GET http://localhost:5000/api/forecast/visitors/models
```

Response:

```json
{
 "status": "success",
 "trained_store_count": 2,
 "store_ids": ["..."]
}
```

### 10.6 Preview visitors

```http
POST http://localhost:5000/api/forecast/visitors/preview
```

Daily 30 hari:

```json
{
 "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
 "horizon_label": "daily",
 "horizon_count": 30
}
```

Weekly 1 minggu:

```json
{
 "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
 "horizon_label": "weekly",
 "horizon_count": 1
}
```

Monthly 1 bulan:

```json
{
 "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
 "horizon_label": "monthly",
 "horizon_count": 1
}
```

Dengan start date:

```json
{
 "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
 "horizon_label": "weekly",
 "horizon_count": 1,
 "start_date": "2026-07-02"
}
```

Response preview visitors:

```json
{
 "status": "success",
 "message": "Forecast visitors berhasil dibuat tanpa disimpan.",
 "request": {
 "store_id": "...",
 "horizon_label": "daily",
 "horizon_count": 30
 },
 "data": {
 "store_id": "...",
 "generated_at": "...",
 "forecast_horizon_days": 30,
 "forecasts": [
 {
 "date": "2026-07-02",
 "predicted_visitors": 123,
 "predicted_transactions": 123,
 "lower_bound": 100,
 "upper_bound": 150,
 "day_of_week": "Kamis",
 "is_weekend": false
 }
 ],
 "model_metadata": {
 "trained_at": "...",
 "training_data_points": 154,
 "feature_importance": {},
 "cv_mae": 10.0,
 "cv_rmse": 12.0,
 "horizon_method": "direct_daily_random_forest_model",
 "metric_horizon": "daily",
 "metrics": {}
 },
 "status": "success",
 "message": "..."
 }
}
```

### 10.7 Save visitors

```http
POST http://localhost:5000/api/forecast/visitors/save
```

Body sama seperti preview:

```json
{
 "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
 "horizon_label": "daily",
 "horizon_count": 30,
 "start_date": "2026-07-02"
}
```

Save visitors akan:

1. Generate forecast.
2. Set `is_latest=false` untuk run visitors lama dengan store dan horizon yang sama.
3. Insert satu row ke `forecast_runs`.
4. Insert banyak row ke `forecast_results`.

Response:

```json
{
 "status": "success",
 "message": "Forecast visitors berhasil disimpan ke database.",
 "request": {...},
 "save_result": {
 "run_id": 123,
 "saved_results": 30,
 "horizon_label": "daily",
 "horizon_days": 30,
 "metrics": {...},
 "summary": {...}
 },
 "data": {...}
}
```

### 10.8 Run visitors

```http
POST http://localhost:5000/api/forecast/visitors/run
```

Body sama seperti preview/save.

Implementasi visitors `/run` saat ini sama-sama generate forecast lalu save ke database.

### 10.9 Legacy visitors endpoints

Masih tersedia:

```http
POST /api/forecast/visitors/daily
POST /api/forecast/visitors/predict-weekly
POST /api/forecast/visitors/predict-monthly
```

Daily body:

```json
{
 "store_id": "...",
 "forecast_days": 30,
 "start_date": "2026-07-02"
}
```

Weekly body:

```json
{
 "store_id": "...",
 "forecast_weeks": 4,
 "start_date": "2026-07-02"
}
```

Monthly body:

```json
{
 "store_id": "...",
 "forecast_months": 3,
 "start_date": "2026-07-01"
}
```

Rekomendasi: pakai route standar `preview/save/run`, bukan legacy, untuk frontend/scheduler baru.

### 10.10 Metrics visitors

Visitors menghitung horizon-aware metrics berbasis out-of-sample daily predictions dari `TimeSeriesSplit`.

Daily metrics:

- `daily_mae`
- `daily_rmse`
- `daily_mae_percentage`
- `daily_error_ratio`
- `daily_reliability`

Weekly metrics:

- dihitung dari agregasi prediksi daily OOS ke minggu penuh.
- minggu parsial tidak dihitung.

Monthly metrics:

- dihitung dari agregasi prediksi daily OOS ke bulan penuh.
- bulan parsial tidak dihitung.

Reliability rule:

```text
error_ratio <= 0.10 = high
error_ratio <= 0.20 = medium
error_ratio <= 0.30 = low_medium
> 0.30 = low
```

## 11. Modul Sales

### 11.1 Fungsi

Sales forecast memprediksi omzet/penjualan.

Model: Random Forest.

Target: `omzet`.

Data source:

1. Backend Go:
 - `sales-daily-summaries`
 - `sales-monthly-summaries`
 - `orders`
2. Jika backend tidak mengembalikan data, ada fallback direct DB pada sales.

### 11.2 Retrain sales

```http
POST http://localhost:5000/api/forecast/sales/retrain
```

Body:

```json
{
 "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
 "force": true
}
```

Minimal data sales daily untuk retrain adalah 30 hari.

Artifact sales:

```text
models/sales/sales_daily_model_store_<store_id>.joblib
models/sales/sales_daily_scaler_store_<store_id>.joblib
models/sales/sales_daily_features_store_<store_id>.json
models/sales/sales_daily_metadata_store_<store_id>.json
```

Untuk weekly/monthly, artifact mengikuti granularity:

```text
models/sales/sales_weekly_model_store_<store_id>.joblib
models/sales/sales_monthly_model_store_<store_id>.joblib
```

### 11.3 Preview sales

```http
POST http://localhost:5000/api/forecast/sales/preview
```

Body:

```json
{
 "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
 "horizon_label": "daily",
 "horizon_count": 30,
 "start_date": "2026-07-02"
}
```

`horizon_label` menerima:

```text
daily
weekly
monthly
```

### 11.4 Save sales

```http
POST http://localhost:5000/api/forecast/sales/save
```

Sales `/save` tidak menerima body standar langsung. Body wajib berisi `forecast`.

Alur:

1. Jalankan `/api/forecast/sales/preview`.
2. Ambil response forecast.
3. Kirim ke `/api/forecast/sales/save`.

Body:

```json
{
 "backend_token": "optional_jwt_jika_tidak_pakai_internal_service_key",
 "forecast": {
 "store_id": "...",
 "generated_at": "...",
 "forecast_horizon_days": 30,
 "forecasts": [],
 "model_metadata": {},
 "request_meta": {
 "module": "sales",
 "horizon_label": "daily",
 "horizon_count": 30,
 "mode": "preview",
 "saved_to_database": false
 }
 }
}
```

Save sales mencoba menyimpan ke:

1. `forecast-predictions`
2. `forecast-runs`
3. `forecast-results`

Jika `forecast_predictions` sudah dihapus tetapi endpoint backend masih dipanggil, save sales berisiko gagal pada step pertama.

### 11.5 Run sales

```http
POST http://localhost:5000/api/forecast/sales/run
```

Body:

```json
{
 "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
 "horizon_label": "daily",
 "horizon_count": 30,
 "start_date": "2026-07-02",
 "backend_token": "optional"
}
```

Sales `/run` menghitung forecast lalu menyimpan ke backend.

## 12. Modul Inventory

### 12.1 Fungsi

Inventory forecast memprediksi penggunaan stok bahan per ingredient.

Model: Prophet.

Target: `reduced` dari `ingredient-stock-histories`, diaggregasi harian per `store_id` dan `ingredient_id`.

Inventory memakai fitur:

- weekend
- hari libur nasional Indonesia
- placeholder `is_store_closed=0`

### 12.2 Kontrak route standar inventory

Route inventory distandarkan menjadi:

```http
POST http://localhost:5000/api/forecast/inventory/preview
POST http://localhost:5000/api/forecast/inventory/save
POST http://localhost:5000/api/forecast/inventory/run
```

Makna route:

```text
preview = generate forecast inventory tanpa simpan database
save = generate forecast inventory lalu simpan database
run = generate forecast inventory lalu simpan database
```

Agar konsisten dengan visitors, `save` dan `run` inventory memakai body standar. Keduanya menghitung forecast dari request body, bukan menerima payload forecast hasil preview.

### 12.3 Body standar inventory

Daily 30 hari untuk satu ingredient:

```json
{
 "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
 "ingredient_id": "uuid-ingredient",
 "horizon_label": "daily",
 "horizon_count": 30
}
```

Weekly 1 minggu untuk satu ingredient:

```json
{
 "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
 "ingredient_id": "uuid-ingredient",
 "horizon_label": "weekly",
 "horizon_count": 1
}
```

Monthly 1 bulan untuk satu ingredient:

```json
{
 "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
 "ingredient_id": "uuid-ingredient",
 "horizon_label": "monthly",
 "horizon_count": 1
}
```

Dengan `start_date`:

```json
{
 "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
 "ingredient_id": "uuid-ingredient",
 "horizon_label": "weekly",
 "horizon_count": 1,
 "start_date": "2026-07-02"
}
```

Forecast semua ingredient pada satu store:

```json
{
 "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
 "horizon_label": "daily",
 "horizon_count": 30,
 "start_date": "2026-07-02"
}
```

Aturan field:

- `store_id` wajib.
- `ingredient_id` optional.
- Jika `ingredient_id` dikirim, forecast hanya untuk satu bahan.
- Jika `ingredient_id` tidak dikirim, forecast untuk semua bahan aktif pada store.
- `horizon_label` wajib dan hanya boleh `daily`, `weekly`, atau `monthly`.
- `horizon_count` wajib dan harus integer positif.
- `start_date` optional dengan format `YYYY-MM-DD`.

### 12.4 Training inventory semua pasangan store/ingredient

Training tetap dapat memakai route lama karena training bukan bagian dari kontrak `preview/save/run`:

```http
POST http://localhost:5000/api/inventory/train/start
```

Response:

```json
{
 "task_id": "uuid",
 "message": "Training dimulai. Pantau progress di /api/inventory/train/status/<task_id>"
}
```

Cek status:

```http
GET http://localhost:5000/api/inventory/train/status/<task_id>
```

Response status:

```json
{
 "status": "RUNNING",
 "total": 10,
 "processed": 3,
 "current_pair": "store_id / ingredient_id",
 "message": ""
}
```

Route training lama:

```http
POST /api/inventory/train
```

`training_tasks` disimpan di memory Python. Jika service restart, status task hilang.

### 12.5 Preview inventory

```http
POST http://localhost:5000/api/forecast/inventory/preview
```

Body satu ingredient:

```json
{
 "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
 "ingredient_id": "uuid-ingredient",
 "horizon_label": "daily",
 "horizon_count": 30,
 "start_date": "2026-07-02"
}
```

Response preview inventory:

```json
{
 "status": "success",
 "message": "Forecast inventory berhasil dibuat tanpa disimpan.",
 "request": {
 "store_id": "...",
 "ingredient_id": "...",
 "horizon_label": "daily",
 "horizon_count": 30
 },
 "data": {
 "store_id": "...",
 "ingredient_id": "...",
 "generated_at": "...",
 "forecast_horizon_days": 30,
 "forecasts": [
 {
 "date": "2026-07-02",
 "predicted_usage": 12.5,
 "lower_bound": 9.5,
 "upper_bound": 15.5,
 "unit": "kg"
 }
 ],
 "model_metadata": {
 "model_name": "prophet",
 "metrics": {}
 }
 }
}
```

Response preview semua ingredient:

```json
{
 "status": "success",
 "message": "Forecast inventory semua ingredient berhasil dibuat tanpa disimpan.",
 "request": {
 "store_id": "...",
 "horizon_label": "daily",
 "horizon_count": 30
 },
 "data": {
 "store_id": "...",
 "ingredient_count": 10,
 "results": [
 {
 "ingredient_id": "...",
 "ingredient_name": "Tepung",
 "forecasts": []
 }
 ]
 }
}
```

### 12.7 Save inventory

```http
POST http://localhost:5000/api/forecast/inventory/save
```

Body sama seperti preview:

```json
{
 "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
 "ingredient_id": "uuid-ingredient",
 "horizon_label": "daily",
 "horizon_count": 30,
 "start_date": "2026-07-02"
}
```

Save inventory sebaiknya:

1. Generate forecast inventory.
2. Set `is_latest=false` untuk run inventory lama dengan store, ingredient, dan horizon yang sama.
3. Insert satu row ke `forecast_runs`.
4. Insert banyak row ke `forecast_results`.
5. Isi `forecast_results.item_id = ingredient_id`.
6. Isi `forecast_results.item_type = 'ingredient'`.

Response save inventory yang disarankan:

```json
{
 "status": "success",
 "message": "Forecast inventory berhasil disimpan ke database.",
 "request": {
 "store_id": "...",
 "ingredient_id": "...",
 "horizon_label": "daily",
 "horizon_count": 30
 },
 "save_result": {
 "run_id": 123,
 "saved_results": 30,
 "horizon_label": "daily",
 "horizon_days": 30
 },
 "data": {}
}
```

### 12.8 Run inventory

```http
POST http://localhost:5000/api/forecast/inventory/run
```

Body sama seperti preview/save.

Secara kontrak, `/run` inventory adalah shortcut untuk generate forecast dan langsung simpan. Untuk konsistensi dengan visitors, response `/run` boleh sama dengan `/save`, tetapi message sebaiknya berbeda.

### 12.9 Artifact inventory

```text
models/inventory/model_store<store_id>_ingr<ingredient_id>.pkl
models/inventory/metrics_model_store<store_id>_ingr<ingredient_id>.json
```

### 12.10 Model belum ada

Jika model belum ada:

```json
{
 "status": "error",
 "message": "Model inventory belum di-training untuk store_id dan ingredient_id ini."
}
```

Alternatif yang lebih otomatis:

- Jika model belum ada dan data historis cukup, service auto-train model untuk ingredient tersebut.
- Jika data historis tidak cukup, response error harus menjelaskan jumlah data yang tersedia dan minimal data yang dibutuhkan.

## 13. Scheduler

Di `app.py`, scheduler dibuat saat service start.

Job yang ada:

1. Inventory training tiap Minggu pukul 02:00.
2. Visitors retrain interval berdasarkan `Config.VISITORS_RETRAIN_INTERVAL_DAYS`, default 7 hari.

Scheduler aktif tanpa membaca `ENABLE_FORECAST_SCHEDULER`.

Risiko:

- Pada server kecil, scheduler bisa memulai training berat tanpa sengaja.
- Inventory training semua ingredient bisa berat karena Prophet.
- Jika backend/database belum siap, scheduler akan menghasilkan error log.

Rekomendasi production:

- Tambahkan guard env sebelum `scheduler.start()`.
- Untuk server 2 GB, matikan inventory auto-training dulu.
- Jalankan retrain visitors/sales secara terjadwal dari systemd timer/cron jika ingin lebih terkontrol.

Contoh konsep patch:

```python
if os.getenv("ENABLE_FORECAST_SCHEDULER", "false").lower() == "true":
 scheduler.start()
 atexit.register(lambda: scheduler.shutdown())
```



## 14. Urutan testing Postman yang disarankan

### 14.1 Cek backend internal dulu

```http
GET http://localhost:8080/internal/health
X-Service-Key: <key>
```

### 14.2 Cek forecast-service

```http
GET http://localhost:5000/health
```

### 14.3 Visitors retrain

```http
POST http://localhost:5000/api/forecast/visitors/retrain
Content-Type: application/json

{
 "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
 "force": true
}
```

### 14.4 Visitors preview

```http
POST http://localhost:5000/api/forecast/visitors/preview
Content-Type: application/json

{
 "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
 "horizon_label": "daily",
 "horizon_count": 30,
 "start_date": "2026-07-02"
}
```

### 14.5 Visitors save

```http
POST http://localhost:5000/api/forecast/visitors/save
Content-Type: application/json

{
 "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
 "horizon_label": "daily",
 "horizon_count": 30,
 "start_date": "2026-07-02"
}
```

### 14.6 Inventory preview

```http
POST http://localhost:5000/api/forecast/inventory/preview
Content-Type: application/json

{
 "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
 "ingredient_id": "uuid-ingredient",
 "horizon_label": "daily",
 "horizon_count": 30,
 "start_date": "2026-07-02"
}
```

### 14.7 Inventory save

```http
POST http://localhost:5000/api/forecast/inventory/save
Content-Type: application/json

{
 "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
 "ingredient_id": "uuid-ingredient",
 "horizon_label": "daily",
 "horizon_count": 30,
 "start_date": "2026-07-02"
}
```

### 14.8 Inventory run semua ingredient

```http
POST http://localhost:5000/api/forecast/inventory/run
Content-Type: application/json

{
 "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
 "horizon_label": "weekly",
 "horizon_count": 1,
 "start_date": "2026-07-02"
}
```

### 14.9 Cek database

```sql
SELECT *
FROM forecast_runs
WHERE store_id = 'b4e2f559-9615-4263-84fe-9ee97780748f'
 AND forecast_type = 'visitors'
ORDER BY created_at DESC;
```

```sql
SELECT r.*
FROM forecast_results r
JOIN forecast_runs fr ON fr.id = r.run_id
WHERE fr.store_id = 'b4e2f559-9615-4263-84fe-9ee97780748f'
 AND fr.forecast_type = 'visitors'
ORDER BY r.target_date ASC;
```

Cek inventory:

```sql
SELECT *
FROM forecast_runs
WHERE store_id = 'b4e2f559-9615-4263-84fe-9ee97780748f'
 AND forecast_type = 'inventory'
ORDER BY created_at DESC;
```

```sql
SELECT r.*
FROM forecast_results r
JOIN forecast_runs fr ON fr.id = r.run_id
WHERE fr.store_id = 'b4e2f559-9615-4263-84fe-9ee97780748f'
 AND fr.forecast_type = 'inventory'
 AND r.item_type = 'ingredient'
ORDER BY r.target_date ASC;
```

## 15. Troubleshooting

### 15.1 `Tidak ada data historis untuk store ...`

Penyebab umum:

- `store_id` salah.
- Backend internal route tidak mengembalikan data.
- Header `X-Service-Key` salah sehingga request internal gagal.
- Tidak ada order valid sesuai rule visitors.
- Data historis kurang dari 30 hari.

Cek:

```http
GET http://localhost:8080/internal/forecast/visitors-daily-history?store_id=<store_id>
X-Service-Key: <key>
```

### 15.2 `Model untuk store ... tidak ditemukan`

Solusi:

```http
POST /api/forecast/visitors/retrain
```

Atau biarkan auto-retrain saat forecast, selama data historis cukup.

### 15.3 `Data historis terlalu sedikit`

Visitors dan sales butuh minimal 30 hari historis untuk daily model.

Karena feature engineering visitors memakai `lag_28`, data 30 hari hanya menghasilkan sedikit training point. Lebih baik punya 90+ hari data.

### 15.4 Health `degraded`

Artinya forecast-service hidup, tetapi backend Go tidak reachable.

Cek:

- Backend Go sudah run di port 8080.
- URL `GOLANG_API_BASE_URL` benar.
- Internal service key benar.
- Backend route `/internal/forecast/stores` bisa diakses.

### 15.5 Save visitors gagal koneksi DB

Visitors save memakai direct PostgreSQL. Cek:

```env
DB_HOST=
DB_PORT=
DB_USER=
DB_PASSWORD=
DB_NAME=
DB_SSLMODE=
```

Untuk Supabase biasanya `DB_SSLMODE=require`.
