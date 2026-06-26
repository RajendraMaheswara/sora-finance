# Forecast Service API Guide

README ini berisi panduan lengkap route `forecast-service` untuk kebutuhan testing via Postman. Forecast-service ini dipakai sebagai service Python untuk menjalankan forecast penjualan, pengunjung, dan inventory. Pada tahap development, forecast **tidak perlu dibuat di frontend** dan cukup dijalankan dari Postman.

## 1. Konsep Utama

Forecast-service memakai 3 mode eksekusi API:

| Mode | Fungsi | Simpan ke Database? | Cocok untuk |
|---|---|---:|---|
| `preview` | Menghitung forecast dan mengembalikan hasil di response | Tidak | Testing model via Postman |
| `save` | Menyimpan hasil forecast dari preview ke backend/database | Ya | Setelah hasil preview dicek |
| `run` | Menghitung forecast lalu langsung menyimpan ke backend/database | Ya | Scheduler / automation nanti |

Alur yang disarankan saat development:

```text
1. Jalankan /preview dulu.
2. Cek hasil forecast di response Postman.
3. Jika hasil sudah masuk akal, baru jalankan /save.
4. Jika sudah stabil, /run atau /run-all bisa dipakai untuk otomatisasi/scheduler.
```

## 2. Modul Forecast

Forecast-service memiliki 3 modul utama:

| Module | Keterangan |
|---|---|
| `sales` | Forecast penjualan/omzet |
| `visitors` | Forecast pengunjung/transaksi/customer count |
| `inventory` | Forecast kebutuhan stok bahan |

Route final memakai pola:

```text
/api/forecast/{module}/{action}
```

Contoh:

```text
/api/forecast/sales/preview
/api/forecast/visitors/run
/api/forecast/inventory/retrain
```

## 3. Horizon Forecast

Forecast menggunakan `horizon_label`:

| horizon_label | Arti | Output |
|---|---|---|
| `weekly` | Prediksi 7 hari ke depan | Daily rows, 7 data tanggal |
| `monthly` | Prediksi 1 bulan ke depan | Daily rows, 28/29/30/31 data tanggal |

Catatan penting:

```text
weekly dan monthly tetap menghasilkan data harian, bukan 1 total angka.
```

Contoh weekly:

```text
2026-06-22
2026-06-23
2026-06-24
2026-06-25
2026-06-26
2026-06-27
2026-06-28
```

## 4. Environment Configuration

Buat atau sesuaikan file:

```text
forecast-service/.env
```

Contoh development:

```env
FORECAST_MODE=manual
ENABLE_FORECAST_SCHEDULER=false
FORECAST_RUN_AFTER_CLOSE_MINUTES=60
FORECAST_24H_RUN_TIME=02:00

BACKEND_API_URL=http://localhost:8080/api
GOLANG_API_BASE_URL=http://localhost:8080/api
BACKEND_REQUEST_TIMEOUT_SECONDS=30

# Optional. Bisa dikosongkan saat hanya memakai /preview.
# Dibutuhkan jika memakai /save atau /run karena backend Go memakai JWT.
BACKEND_AUTH_TOKEN=
```

Jika ingin menyimpan hasil forecast ke database tanpa mengirim token di setiap body Postman, isi:

```env
BACKEND_AUTH_TOKEN=isi_token_admin_atau_owner_dari_backend_go
```

Untuk production/scheduler nanti:

```env
FORECAST_MODE=scheduler
ENABLE_FORECAST_SCHEDULER=true
FORECAST_RUN_AFTER_CLOSE_MINUTES=60
FORECAST_24H_RUN_TIME=02:00
```

## 5. Menjalankan Forecast Service

Masuk ke folder `forecast-service`:

```powershell
cd "C:\Program Files (x64)\Kuliah\Semester 4\PT Sora Abadi\Implementation\produk berhasil\main_proto\sora-finance\forecast-service"
```

Install dependency jika belum:

```powershell
pip install -r requirements.txt
```

Cek syntax Python:

```powershell
python -m py_compile app.py config.py modules/sales/forecaster.py modules/inventory/forecaster.py modules/inventory/trainer.py modules/visitors/forecaster.py modules/visitors/trainer.py
```

Jalankan service:

```powershell
python app.py
```

Default service berjalan di:

```text
http://localhost:5000
```

## 6. Health Check

### GET `/health`

Untuk cek apakah service hidup.

```http
GET http://localhost:5000/health
```

Contoh response:

```json
{
  "status": "ok"
}
```

## 7. Standar Request Body

### Body dasar

```json
{
  "store_id": "uuid-store",
  "horizon_label": "weekly",
  "force": true
}
```

### Body inventory semua bahan

```json
{
  "store_id": "uuid-store",
  "horizon_label": "weekly",
  "force": true
}
```

### Body inventory satu bahan

```json
{
  "store_id": "uuid-store",
  "ingredient_id": "uuid-ingredient",
  "horizon_label": "weekly",
  "force": true
}
```

Field:

| Field | Wajib | Keterangan |
|---|---:|---|
| `store_id` | Ya | ID store yang akan diproses |
| `horizon_label` | Ya untuk preview/run | `weekly` atau `monthly` |
| `force` | Tidak | `true` untuk paksa proses ulang |
| `modules` | Tidak | Khusus `preview-all`, `run-all`, `retrain-all` |
| `ingredient_id` | Tidak | Khusus inventory; jika kosong berarti semua bahan |
| `backend_token` | Tidak | Token JWT backend Go untuk `/save` dan `/run` |

Catatan: gunakan `store_id`, bukan `m_store_id`, untuk kontrak API baru. `m_store_id` hanya nama kolom database.

## 8. Preview Forecast

Preview digunakan untuk testing karena **belum menyimpan hasil ke database**.

### POST `/api/forecast/sales/preview`

```http
POST http://localhost:5000/api/forecast/sales/preview
```

Body:

```json
{
  "store_id": "7acfd0aa-254e-4c71-9f86-fc2b5213d7f5",
  "horizon_label": "weekly",
  "force": true
}
```

### POST `/api/forecast/visitors/preview`

```http
POST http://localhost:5000/api/forecast/visitors/preview
```

Body:

```json
{
  "store_id": "7acfd0aa-254e-4c71-9f86-fc2b5213d7f5",
  "horizon_label": "weekly",
  "force": true
}
```

### POST `/api/forecast/inventory/preview`

Untuk semua bahan:

```http
POST http://localhost:5000/api/forecast/inventory/preview
```

Body:

```json
{
  "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
  "horizon_label": "weekly",
  "force": true
}
```

Untuk satu bahan:

```json
{
  "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
  "ingredient_id": "b98b5042-30b5-4dc7-80ce-7dbb4797c4c7",
  "horizon_label": "weekly",
  "force": true
}
```

### POST `/api/forecast/preview-all`

Menjalankan preview untuk beberapa/semua modul dalam sekali request.

```http
POST http://localhost:5000/api/forecast/preview-all
```

Body semua modul:

```json
{
  "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
  "horizon_label": "weekly",
  "force": true
}
```

Body modul tertentu:

```json
{
  "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
  "horizon_label": "weekly",
  "modules": ["sales", "visitors"],
  "force": true
}
```

Jika `modules` tidak dikirim, default menjalankan:

```json
["sales", "visitors", "inventory"]
```

Contoh response preview:

```json
{
  "success": true,
  "message": "Forecast preview generated. Belum tersimpan ke database.",
  "data": {
    "store_id": "uuid-store",
    "module": "sales",
    "horizon_label": "weekly",
    "horizon_days": 7,
    "granularity": "daily",
    "predict_start_date": "2026-06-22",
    "predict_end_date": "2026-06-28",
    "saved_to_database": false,
    "results": [
      {
        "target_date": "2026-06-22",
        "predicted_value": 1800000,
        "lower_bound": 1500000,
        "upper_bound": 2100000
      }
    ]
  }
}
```

## 9. Save Forecast ke Database

Save digunakan untuk menyimpan hasil preview ke backend/database.

### Catatan token backend

Karena backend Go memakai JWT, request save perlu token. Token bisa dikirim dengan salah satu cara:

Cara 1, kirim di body:

```json
{
  "backend_token": "ISI_TOKEN_ADMIN_ATAU_OWNER"
}
```

Cara 2, isi di `.env` forecast-service:

```env
BACKEND_AUTH_TOKEN=ISI_TOKEN_ADMIN_ATAU_OWNER
```

### POST `/api/forecast/sales/save`

```http
POST http://localhost:5000/api/forecast/sales/save
```

Body:

```json
{
  "backend_token": "ISI_TOKEN_ADMIN_ATAU_OWNER",
  "forecast": {
    "store_id": "uuid-store",
    "module": "sales",
    "horizon_label": "weekly",
    "horizon_days": 7,
    "granularity": "daily",
    "predict_start_date": "2026-06-22",
    "predict_end_date": "2026-06-28",
    "results": [
      {
        "target_date": "2026-06-22",
        "predicted_value": 1800000,
        "lower_bound": 1500000,
        "upper_bound": 2100000
      }
    ]
  }
}
```

### POST `/api/forecast/visitors/save`

```http
POST http://localhost:5000/api/forecast/visitors/save
```

Body sama seperti sales, tetapi `module` bernilai `visitors`.

### POST `/api/forecast/inventory/save`

```http
POST http://localhost:5000/api/forecast/inventory/save
```

Untuk inventory, setiap result boleh memiliki `item_id` dan `item_type`:

```json
{
  "backend_token": "ISI_TOKEN_ADMIN_ATAU_OWNER",
  "forecast": {
    "store_id": "uuid-store",
    "module": "inventory",
    "horizon_label": "weekly",
    "horizon_days": 7,
    "granularity": "daily",
    "predict_start_date": "2026-06-22",
    "predict_end_date": "2026-06-28",
    "results": [
      {
        "target_date": "2026-06-22",
        "item_id": "uuid-ingredient",
        "item_type": "ingredient",
        "predicted_value": 12.5,
        "lower_bound": 10.0,
        "upper_bound": 15.0
      }
    ]
  }
}
```

### POST `/api/forecast/save-all`

Untuk menyimpan hasil dari `preview-all`.

```http
POST http://localhost:5000/api/forecast/save-all
```

Body:

```json
{
  "backend_token": "ISI_TOKEN_ADMIN_ATAU_OWNER",
  "forecasts": {
    "sales": {
      "store_id": "uuid-store",
      "module": "sales",
      "horizon_label": "weekly",
      "horizon_days": 7,
      "granularity": "daily",
      "predict_start_date": "2026-06-22",
      "predict_end_date": "2026-06-28",
      "results": []
    },
    "visitors": {
      "store_id": "uuid-store",
      "module": "visitors",
      "horizon_label": "weekly",
      "horizon_days": 7,
      "granularity": "daily",
      "predict_start_date": "2026-06-22",
      "predict_end_date": "2026-06-28",
      "results": []
    }
  }
}
```

## 10. Run Forecast dan Langsung Save

Gunakan route ini hanya jika hasil forecast sudah dipercaya, karena hasilnya langsung dikirim ke backend/database.

### POST `/api/forecast/sales/run`

```http
POST http://localhost:5000/api/forecast/sales/run
```

Body:

```json
{
  "backend_token": "ISI_TOKEN_ADMIN_ATAU_OWNER",
  "store_id": "uuid-store",
  "horizon_label": "weekly",
  "force": true
}
```

### POST `/api/forecast/visitors/run`

```http
POST http://localhost:5000/api/forecast/visitors/run
```

Body:

```json
{
  "backend_token": "ISI_TOKEN_ADMIN_ATAU_OWNER",
  "store_id": "uuid-store",
  "horizon_label": "weekly",
  "force": true
}
```

### POST `/api/forecast/inventory/run`

```http
POST http://localhost:5000/api/forecast/inventory/run
```

Body semua bahan:

```json
{
  "backend_token": "ISI_TOKEN_ADMIN_ATAU_OWNER",
  "store_id": "uuid-store",
  "horizon_label": "weekly",
  "force": true
}
```

Body satu bahan:

```json
{
  "backend_token": "ISI_TOKEN_ADMIN_ATAU_OWNER",
  "store_id": "uuid-store",
  "ingredient_id": "uuid-ingredient",
  "horizon_label": "weekly",
  "force": true
}
```

### POST `/api/forecast/run-all`

```http
POST http://localhost:5000/api/forecast/run-all
```

Body:

```json
{
  "backend_token": "ISI_TOKEN_ADMIN_ATAU_OWNER",
  "store_id": "uuid-store",
  "horizon_label": "weekly",
  "modules": ["sales", "visitors", "inventory"],
  "force": true
}
```

## 11. Retrain Model

Retrain digunakan untuk melatih ulang model. Retrain tidak sama dengan run forecast.

```text
run forecast = membuat prediksi memakai model yang sudah ada
retrain      = melatih ulang model dari data historis
```

### POST `/api/forecast/sales/retrain`

```http
POST http://localhost:5000/api/forecast/sales/retrain
```

Body:

```json
{
  "store_id": "uuid-store",
  "force": true
}
```

Catatan: model sales saat ini masih dicatat sebagai model global; `store_id` dipakai untuk kontrak API dan akan bisa dipakai untuk pengembangan store-specific model.

### POST `/api/forecast/visitors/retrain`

```http
POST http://localhost:5000/api/forecast/visitors/retrain
```

Body:

```json
{
  "store_id": "uuid-store",
  "force": true
}
```

### POST `/api/forecast/inventory/retrain`

```http
POST http://localhost:5000/api/forecast/inventory/retrain
```

Body semua bahan:

```json
{
  "store_id": "uuid-store",
  "force": true
}
```

Body satu bahan:

```json
{
  "store_id": "uuid-store",
  "ingredient_id": "uuid-ingredient",
  "force": true
}
```

### POST `/api/forecast/retrain-all`

```http
POST http://localhost:5000/api/forecast/retrain-all
```

Body semua modul:

```json
{
  "store_id": "uuid-store",
  "force": true
}
```

Body modul tertentu:

```json
{
  "store_id": "uuid-store",
  "modules": ["sales", "visitors", "inventory"],
  "force": true
}
```

## 12. Training Task Status

Beberapa training berjalan background dan mengembalikan `task_id`. Gunakan endpoint status berikut.

### GET `/api/forecast/train/status/<task_id>`

Untuk cek training sales legacy/background.

```http
GET http://localhost:5000/api/forecast/train/status/<task_id>
```

### GET `/api/inventory/train/status/<task_id>`

Untuk cek training inventory.

```http
GET http://localhost:5000/api/inventory/train/status/<task_id>
```

## 13. Legacy Routes

Route berikut masih disediakan untuk kompatibilitas testing lama. Untuk pengembangan baru, gunakan route standar di atas.

### Visitors legacy

```text
GET  /api/forecast/visitors/models
POST /api/forecast/visitors/retrain
POST /api/forecast/visitors/daily
POST /api/forecast/visitors/weekly
POST /api/forecast/visitors/monthly
POST /api/forecast/visitors/predict-weekly
POST /api/forecast/visitors/predict-monthly
```

Contoh visitors weekly legacy:

```http
POST http://localhost:5000/api/forecast/visitors/weekly
```

Body:

```json
{
  "store_id": "uuid-store"
}
```

### Sales legacy

```text
POST /api/forecast/penjualan-harian
POST /api/forecast/penjualan-mingguan
POST /api/forecast/penjualan-bulanan
POST /api/forecast/sales
POST /api/forecast/
POST /api/forecast/train/status/<task_id>
```

Legacy body lama masih bisa memakai `m_store_id`, tetapi standar baru tetap `store_id`.

### Inventory legacy

```text
POST /api/inventory/forecast
POST /api/inventory/train/start
POST /api/inventory/train/status/<task_id>
POST /api/inventory/train
POST /api/inventory/save-all-forecasts
POST /api/inventory/save-all-existing
```

Contoh legacy inventory:

```http
POST http://localhost:5000/api/inventory/forecast
```

Body:

```json
{
  "store_id": "uuid-store",
  "ingredient_id": "uuid-ingredient",
  "periods": 4,
  "freq": "W"
}
```

Catatan: route legacy inventory masih memakai konsep `periods` dan `freq`. Untuk standar baru, gunakan `horizon_label`.

## 14. Rekomendasi Urutan Testing di Postman

### A. Cek service

```http
GET http://localhost:5000/health
```

### B. Retrain model jika belum ada model

Visitors:

```http
POST http://localhost:5000/api/forecast/visitors/retrain
```

Sales:

```http
POST http://localhost:5000/api/forecast/sales/retrain
```

Inventory:

```http
POST http://localhost:5000/api/forecast/inventory/retrain
```

### C. Previtrain/startew forecast

```http
POST http://localhost:5000/api/forecast/sales/preview
POST http://localhost:5000/api/forecast/visitors/preview
POST http://localhost:5000/api/forecast/inventory/preview
```

### D. Save jika hasil sudah benar

```http
POST http://localhost:5000/api/forecast/sales/save
```

### E. Run langsung hanya jika sudah yakin

```http
POST http://localhost:5000/api/forecast/run-all
```

## 15. Scheduler Plan

Scheduler belum wajib dipakai saat development. Untuk testing Postman, gunakan:

```env
FORECAST_MODE=manual
ENABLE_FORECAST_SCHEDULER=false
```

Nanti saat automation sudah siap:

```env
FORECAST_MODE=scheduler
ENABLE_FORECAST_SCHEDULER=true
FORECAST_RUN_AFTER_CLOSE_MINUTES=60
FORECAST_24H_RUN_TIME=02:00
```

Aturan scheduler yang direncanakan:

```text
1. Sistem cek jam tutup masing-masing store.
2. Forecast jalan setelah toko tutup + buffer 1 jam.
3. Jika toko 24 jam, forecast jalan jam 02:00.
4. Akhir minggu menjalankan weekly forecast untuk 7 hari ke depan.
5. Akhir bulan menjalankan monthly forecast untuk 1 bulan ke depan.
6. Scheduler memakai /api/forecast/run-all agar hasil langsung tersimpan.
```

## 16. Troubleshooting

### A. Forecast preview error karena model tidak ditemukan

Solusi:

```text
Jalankan retrain dulu untuk modul tersebut.
```

Contoh:

```http
POST http://localhost:5000/api/forecast/visitors/retrain
```

### B. Save/run gagal 401 dari backend

Penyebab:

```text
Token backend tidak dikirim atau sudah expired.
```

Solusi:

```text
Login ulang ke backend Go, ambil token baru, lalu kirim sebagai backend_token atau isi BACKEND_AUTH_TOKEN di .env.
```

### C. Preview tidak masuk database

Itu memang benar. Preview hanya untuk testing.

Gunakan `/save` atau `/run` jika ingin menyimpan ke database.

### D. Jangan pakai m_store_id di route baru

Route baru memakai:

```json
{
  "store_id": "uuid-store"
}
```

Bukan:

```json
{
  "m_store_id": "uuid-store"
}
```

### E. Service Flask debug mode

Untuk development boleh memakai debug. Untuk production nanti, jangan jalankan Flask bawaan dengan `debug=True`; gunakan WSGI server seperti Gunicorn/Waitress atau jalankan di container yang sesuai.

## 17. Ringkasan Route Final

```text
GET  /health

POST /api/forecast/sales/preview
POST /api/forecast/visitors/preview
POST /api/forecast/inventory/preview
POST /api/forecast/preview-all

POST /api/forecast/sales/save
POST /api/forecast/visitors/save
POST /api/forecast/inventory/save
POST /api/forecast/save-all

POST /api/forecast/sales/run
POST /api/forecast/visitors/run
POST /api/forecast/inventory/run
POST /api/forecast/run-all

POST /api/forecast/sales/retrain
POST /api/forecast/visitors/retrain
POST /api/forecast/inventory/retrain
POST /api/forecast/retrain-all
```

## 18. Kesimpulan Workflow

Untuk development Postman:

```text
preview -> cek hasil -> save jika hasil benar
```

Untuk scheduler nanti:

```text
run-all -> forecast semua modul -> langsung save ke backend/database
```

Route baru yang wajib diprioritaskan:

```text
/api/forecast/{module}/preview
/api/forecast/{module}/save
/api/forecast/{module}/run
/api/forecast/run-all
```


## Update: Backend Internal Service Key

Forecast-service sekarang tidak perlu token login JWT untuk mengambil data historis atau menyimpan hasil forecast. Gunakan service key internal.

Env yang disarankan:

```env
BACKEND_API_URL=http://localhost:8080/internal/forecast
GOLANG_API_BASE_URL=http://localhost:8080/internal/forecast
INTERNAL_SERVICE_KEY=sora-forecast-internal-key-ganti-yang-panjang
BACKEND_AUTH_TOKEN=
FORECAST_MODE=manual
ENABLE_FORECAST_SCHEDULER=false
BACKEND_REQUEST_TIMEOUT_SECONDS=30
```

`INTERNAL_SERVICE_KEY` harus sama dengan env backend Go. Forecast-service otomatis mengirim header `X-Service-Key` dan `X-Store-ID` ketika memanggil backend internal.

Untuk testing Postman tetap gunakan route forecast-service:

```http
POST /api/forecast/sales/preview
POST /api/forecast/visitors/preview
POST /api/forecast/inventory/preview
POST /api/forecast/preview-all

POST /api/forecast/sales/save
POST /api/forecast/visitors/save
POST /api/forecast/inventory/save
POST /api/forecast/save-all

POST /api/forecast/sales/run
POST /api/forecast/visitors/run
POST /api/forecast/inventory/run
POST /api/forecast/run-all
```

Preview tidak menyimpan database. Save menyimpan hasil preview. Run menghitung forecast dan langsung menyimpan ke backend/database.
