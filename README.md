# Sora Finance — Dokumentasi Developer Lanjutan

Dokumen ini dibuat untuk developer berikutnya yang akan melanjutkan project **Sora Finance**

## 1. Ringkasan project

Sora Finance adalah aplikasi POS/finance dan forecasting untuk toko/outlet. Project terdiri dari tiga service utama:

| Folder | Peran | Stack utama |
|---|---|---|
| `frontend/` | UI dashboard, login, list data master, histori transaksi, dan halaman forecast | Flutter/Dart |
| `backend/` | API utama, auth, store scoping, gateway database, internal write forecast | Go, `go-chi`, PostgreSQL/Supabase |
| `forecast-service/` | Service prediksi visitors, sales, inventory; retrain model; scheduler forecast | Python Flask, scikit-learn, Prophet, APScheduler |

Fokus bisnis utama project adalah membuat forecast untuk tiga modul:

1. **Visitors forecast**: prediksi jumlah pengunjung/transaksi.
2. **Sales forecast**: prediksi omzet/penjualan.
3. **Inventory forecast**: prediksi pemakaian bahan baku/ingredient.

Source of truth data forecast diarahkan ke dua tabel:

- `forecast_runs`: header/run forecast, metadata model, metrics, status, latest flag.
- `forecast_results`: detail prediksi per tanggal/periode dan per item jika ada.

## 2. Gambaran arsitektur

```mermaid
flowchart LR
    U[User / Admin Toko] --> FE[frontend Flutter]
    FE -->|JWT Bearer| BE[backend Go API]
    BE -->|PostgreSQL protocol| DB[(PostgreSQL / Supabase)]

    FS[forecast-service Python] -->|X-Service-Key / Bearer internal key| BEI[backend internal forecast routes]
    BEI --> BE
    FS -->|read operational data via internal routes| BEI
    FS -->|load/save model files| MF[(models/*.joblib + metadata json)]

    SCH[APScheduler optional] --> FS
```

Prinsip keamanan utamanya:

- Frontend memakai JWT user biasa.
- Frontend **tidak** membuat `forecast_runs` dan `forecast_results` (Jika diperlukan dapat membuat Button untuk Membuat Forecast untuk Frontend).
- Forecast-service memakai `INTERNAL_SERVICE_KEY` untuk route internal backend.
- Backend menjadi satu-satunya gateway write forecast ke database.

## 3. Alur sistem utama

### 3.1 Login dan akses data dashboard

```mermaid
sequenceDiagram
    participant User
    participant FE as Flutter frontend
    participant BE as Go backend
    participant DB as PostgreSQL/Supabase

    User->>FE: Input username/password
    FE->>BE: POST /api/auth/login
    BE->>DB: Validasi user
    DB-->>BE: User valid
    BE-->>FE: JWT token
    FE->>FE: Simpan token ke SharedPreferences
    FE->>BE: GET /api/... dengan Authorization: Bearer token
    BE->>BE: JWT middleware + StoreMiddleware
    BE->>DB: Query data sesuai store
    DB-->>BE: Data
    BE-->>FE: JSON response
```

### 3.2 Forecast preview

```mermaid
sequenceDiagram
    participant Dev as Developer/Postman/Scheduler
    participant FS as forecast-service
    participant BE as backend internal API
    participant DB as Database

    Dev->>FS: POST /api/forecast/{module}/preview + X-Service-Key
    FS->>BE: Ambil histori/store/operational hours + X-Service-Key
    BE->>DB: Query data historis
    DB-->>BE: Data historis
    BE-->>FS: JSON data
    FS->>FS: Load model + feature engineering + predict
    FS-->>Dev: Forecast response, tidak menyimpan DB
```

### 3.3 Forecast save

```mermaid
sequenceDiagram
    participant Dev as Scheduler/Postman
    participant FS as forecast-service
    participant BE as backend internal API
    participant DB as Database

    Dev->>FS: POST /api/forecast/{module}/save + X-Service-Key
    FS->>BE: Ambil histori/store/operational hours
    BE->>DB: Query data operasional
    DB-->>BE: Data historis
    BE-->>FS: Data
    FS->>FS: Generate forecast
    FS->>BE: POST /internal/forecast/save {run, results}
    BE->>BE: Validasi run + results
    BE->>DB: Transaction insert forecast_runs + forecast_results
    BE->>DB: Set latest hanya jika success dan results ada
    DB-->>BE: Commit berhasil
    BE-->>FS: run_id + count
    FS-->>Dev: save_result
```

## 4. Struktur repository tingkat atas

```text
sora-finance/
├── frontend/          # Flutter UI
├── backend/           # Go REST API + migrations + Swagger
└── forecast-service/  # Python ML forecasting service
```

Dokumentasi detail per folder tersedia di:

- [`frontend/README.md`](frontend/README.md)
- [`backend/README.md`](backend/README.md)
- [`forecast-service/README.md`](forecast-service/README.md)

## 5. Kontrak forecast standar

### 5.1 Request body standar

Untuk visitors dan sales:

```json
{
  "store_id": "<uuid-store>",
  "horizon_label": "daily",
  "horizon_count": 30
}
```

Untuk inventory single ingredient:

```json
{
  "store_id": "<uuid-store>",
  "ingredient_id": "<uuid-ingredient>",
  "horizon_label": "weekly",
  "horizon_count": 4
}
```

Untuk inventory semua ingredient di satu store:

```json
{
  "store_id": "<uuid-store>",
  "horizon_label": "daily",
  "horizon_count": 30
}
```

Makna `horizon_count`:

| `horizon_label` | Makna `horizon_count` |
|---|---|
| `daily` | jumlah hari |
| `weekly` | jumlah minggu |
| `monthly` | jumlah bulan |

`start_date` opsional. Bila tidak dikirim, forecast-service memakai start date otomatis berdasarkan complete operational period.

### 5.2 Endpoint forecast-service aktif

| Modul | Preview | Save | Retrain |
|---|---|---|---|
| Visitors | `POST /api/forecast/visitors/preview` | `POST /api/forecast/visitors/save` | `POST /api/forecast/visitors/retrain` |
| Sales | `POST /api/forecast/sales/preview` | `POST /api/forecast/sales/save` | `POST /api/forecast/sales/retrain` |
| Inventory | `POST /api/forecast/inventory/preview` | `POST /api/forecast/inventory/save` | `POST /api/forecast/inventory/retrain` |

Inventory retrain bersifat asynchronous dan memiliki status endpoint:

```text
GET /api/forecast/inventory/retrain/status/{task_id}
```

### 5.3 Backend internal forecast routes aktual

Di kode backend, route internal berada di prefix:

```text
/internal/forecast
```

Route penting:

```text
POST /internal/forecast/save
POST /internal/forecast/forecast-runs
POST /internal/forecast/forecast-results
GET  /internal/forecast/visitors-daily-history
GET  /internal/forecast/stores
GET  /internal/forecast/orders
GET  /internal/forecast/order-items
GET  /internal/forecast/food-ingredients
GET  /internal/forecast/ingredient-stock-histories
GET  /internal/forecast/sales-daily-summaries
GET  /internal/forecast/sales-monthly-summaries
GET  /internal/forecast/store-operational-hours
```

Route internal dilindungi `ServiceKeyMiddleware` dan menerima header:

```http
X-Service-Key: <INTERNAL_SERVICE_KEY>
```

atau:

```http
Authorization: Bearer <INTERNAL_SERVICE_KEY>
```

## 6. Database forecast

### 6.1 `forecast_runs`

Mewakili satu proses forecast. Kolom utama:

- `store_id`
- `forecast_type`: `visitors`, `sales`, `inventory`
- `horizon_label`: `daily`, `weekly`, `monthly`
- `horizon_days`
- `granularity`
- `model_name`, `model_version`, `feature_version`
- `train_start_date`, `train_end_date`
- `predict_start_date`, `predict_end_date`
- `metrics`, `summary`, `data_quality`
- `status`: `success`, `failed`, `running`
- `is_latest`
- `started_at`, `finished_at`, `created_at`

Aturan integritas:

- `is_latest=true` hanya untuk `status='success'`.
- Run success tidak boleh menjadi latest jika tidak punya `forecast_results`.
- Satu store + forecast_type + horizon_label hanya boleh punya satu latest.

### 6.2 `forecast_results`

Mewakili detail prediksi dari sebuah run:

- `run_id`
- `target_date`
- `predicted_value`
- `lower_bound`, `upper_bound`
- `confidence_level`
- `actual_value`
- `item_id`
- `item_type`

Untuk inventory:

- `item_id = ingredient_id`
- `item_type = ingredient`

Untuk sales:

- `item_type = sales`
- `item_id` kosong/null.

Untuk visitors:

- `item_type = visitors` atau kosong sesuai hasil lama.
- `item_id` kosong/null.

## 7. Cara menjalankan lokal

### 7.1 Backend

```bash
cd backend
cp .env.example .env
# edit DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME, JWT_SECRET, INTERNAL_SERVICE_KEY
go mod download
go run ./cmd/api
```

Health check:

```bash
curl http://localhost:8080/health
```

Swagger bila `ENABLE_SWAGGER=true`:

```text
http://localhost:8080/swagger/index.html
```

### 7.2 Forecast-service

```bash
cd forecast-service
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Health check:

```bash
curl http://localhost:5000/health
```

### 7.3 Frontend

```bash
cd frontend
flutter clean
flutter pub get
flutter run -d chrome --web-port=3000 
```

Build web release:

```bash
flutter build web --release
```

Output build berada di:

```text
frontend/build/web
```

## 8. Glosarium singkat

| Istilah | Arti |
|---|---|
| Preview | Generate forecast tanpa simpan DB |
| Save | Generate forecast lalu simpan ke DB |
| Retrain | Latih ulang model berdasarkan histori terbaru |
| Horizon label | Granularitas forecast: daily, weekly, monthly |
| Horizon count | Jumlah periode forecast |
| Horizon days | Jumlah hari yang disimpan backend untuk periode forecast |
| Complete period | Periode bisnis yang sudah selesai sehingga aman dipakai sebagai acuan forecast |
| Latest run | Run forecast sukses terbaru yang dipakai dashboard |
| Internal service key | Secret antar-service forecast-service ↔ backend |
