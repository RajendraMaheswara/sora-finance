# Backend — Dokumentasi Developer

Folder `backend/` adalah API utama Sora Finance. Backend bertanggung jawab untuk auth, store scoping, data master/transaksi, dashboard read, dan gateway write forecast internal.

> **Catatan audit:** kode backend v1.5 sudah memiliki route internal forecast dengan `ServiceKeyMiddleware`, validasi forecast service-layer, atomic save, migration hardening latest, dan Swagger forecast-only. Namun `go.mod` masih memakai `go 1.25.0`; pastikan versi ini tersedia di server atau turunkan ke versi Go yang benar-benar digunakan tim.

## 1. Stack

| Komponen | Teknologi |
|---|---|
| Language | Go |
| Router | `github.com/go-chi/chi/v5` |
| DB driver/pool | `github.com/jackc/pgx/v5/pgxpool` |
| DB | PostgreSQL/Supabase |
| Auth | JWT custom middleware |
| Rate limit login | `github.com/go-chi/httprate` |
| Swagger | `swaggo/http-swagger`, generated files di `docs/` |
| Optional token blacklist | Redis via `REDIS_URL` |

## 2. Struktur folder

```text
backend/
├── cmd/api/
│   ├── main.go              # Entry point server, load env, init DB, graceful shutdown
│   ├── dependencies.go      # Wiring repository-service-handler
│   └── routes.go            # Semua routing, middleware, CORS, Swagger, internal routes
├── docs/
│   ├── docs.go              # Generated Swagger docs
│   ├── swagger.json
│   └── swagger.yaml
├── internal/
│   ├── auth/                # JWT, role, store middleware, service key middleware
│   ├── handler/             # HTTP handler per resource
│   ├── models/              # Struct request/response/domain model
│   ├── repository/          # Query PostgreSQL dan transaction logic
│   └── service/             # Validasi dan business logic ringan
├── migrations/              # SQL migration untuk index/security/forecast core
├── pkg/db/
│   └── postgres.go          # pgxpool config
├── go.mod
└── go.sum
```

## 3. Entry point dan lifecycle

`cmd/api/main.go` melakukan:

1. Load `.env` via `godotenv.Load()`.
2. Membuat PostgreSQL pool dari `pkg/db/postgres.go`.
3. Inisialisasi semua dependency via `initDependencies(pool)`.
4. Setup router via `setupRouter(deps)`.
5. Menjalankan HTTP server dengan timeout.
6. Graceful shutdown saat `SIGINT`/`SIGTERM`.

Default port berasal dari `SERVER_PORT`, fallback ke `8080`.

## 4. Dependency wiring

`cmd/api/dependencies.go` membuat pola konsisten:

```text
Repository -> Service -> Handler
```

Contoh:

```text
ForecastRunRepository -> ForecastRunService -> ForecastRunHandler
ForecastResultRepository -> ForecastResultService -> ForecastResultHandler
ForecastRunRepository -> ForecastSaveService -> ForecastSaveHandler
```

Pola ini memudahkan developer baru mencari alur kode:

- Perubahan validasi request: cek `internal/service/*`.
- Perubahan response HTTP: cek `internal/handler/*`.
- Perubahan query/transaction: cek `internal/repository/*`.
- Perubahan struktur JSON: cek `internal/models/*`.

## 5. Middleware dan keamanan

### 5.1 CORS dan security headers

Di `routes.go`, backend menambahkan:

- CORS berdasarkan `ALLOWED_ORIGINS`.
- `X-Content-Type-Options: nosniff`.
- `X-Frame-Options: DENY`.
- `X-XSS-Protection: 1; mode=block`.
- `Strict-Transport-Security`.

Catatan: HSTS aman untuk production HTTPS. Untuk local HTTP tidak masalah, tetapi behavior browser bisa membingungkan saat development tertentu.

### 5.2 JWT middleware

Route public hanya login dan health. Route `/api/*` utama memakai:

```text
authpkg.Middleware(deps.JWTSecret)
authpkg.StoreMiddleware
```

JWT membawa claim user/store/role. `StoreMiddleware` memastikan data yang dibaca user mengikuti store scope, kecuali role system-admin yang diizinkan bypass.

### 5.3 Service key middleware

Route internal forecast memakai:

```go
authpkg.ServiceKeyMiddleware(os.Getenv("INTERNAL_SERVICE_KEY"))
authpkg.ForecastServiceClaimsMiddleware
```

Header yang diterima:

```http
X-Service-Key: <INTERNAL_SERVICE_KEY>
```

atau:

```http
Authorization: Bearer <INTERNAL_SERVICE_KEY>
```

`ForecastServiceClaimsMiddleware` menyuntik claim sistem agar forecast-service bisa membaca data internal tanpa login user biasa. Ini bukan admin UI; ini hanya identitas service-to-service.

## 6. Route utama

### 6.1 Health dan Swagger

```text
GET /health
GET /swagger/*              # aktif jika ENABLE_SWAGGER=true atau non-production
```

### 6.2 Auth

```text
POST /api/auth/login         # rate limited 5 req/min/IP
GET  /api/auth/me            # JWT required
POST /api/auth/logout        # JWT required
```

### 6.3 Public/authenticated read routes

Route berikut berada di group JWT + StoreMiddleware:

```text
GET /api/stores
GET /api/users
GET /api/customers
GET /api/food-ingredients
GET /api/menus
GET /api/orders
GET /api/order-items
GET /api/ingredient-stock-histories
GET /api/sales-daily-summaries
GET /api/sales-monthly-summaries
GET /api/finance-daily-summaries
GET /api/finance-monthly-summaries
GET /api/forecast-results
GET /api/forecast-runs/{id}
GET /api/forecast/latest
GET /api/forecast/visitors/latest
```

Catatan: banyak handler master/detail hanya menyediakan read endpoint di route public. Write operasional POS tidak menjadi fokus dokumentasi ini.

### 6.4 Internal forecast routes

Prefix aktual:

```text
/internal/forecast
```

Route penting:

```text
GET  /internal/health
GET  /internal/forecast/stores
GET  /internal/forecast/orders
GET  /internal/forecast/order-items
GET  /internal/forecast/store-operational-hours
GET  /internal/forecast/food-ingredients
GET  /internal/forecast/ingredient-stock-histories
GET  /internal/forecast/sales-daily-summaries
GET  /internal/forecast/sales-monthly-summaries
GET  /internal/forecast/visitors-daily-history
POST /internal/forecast/save
POST /internal/forecast/forecast-runs
POST /internal/forecast/forecast-results
```

Rekomendasi untuk developer berikutnya: prioritaskan `POST /internal/forecast/save` untuk save run + results secara atomik. Route dua langkah `forecast-runs` lalu `forecast-results` masih ada untuk kompatibilitas, tetapi lebih rawan jika panggilan kedua gagal.

## 7. Modul forecast backend

### 7.1 Model

File terkait:

```text
internal/models/forecast_run.go
internal/models/forecast_result.go
internal/models/forecast_save.go
internal/models/forecast_latest.go
```

Tipe request utama:

```go
type ForecastSaveInput struct {
    Run     ForecastRunInput      `json:"run"`
    Results []ForecastResultInput `json:"results"`
}
```

### 7.2 Service validation

File utama:

```text
internal/service/forecast_validation.go
internal/service/forecast_run_service.go
internal/service/forecast_result_service.go
internal/service/forecast_save_service.go
```

Validasi yang dilakukan:

- `store_id` harus UUID.
- `forecast_type` hanya `visitors`, `sales`, `inventory`.
- `horizon_label` hanya `daily`, `weekly`, `monthly`.
- `horizon_days` harus `1..366`.
- `granularity` hanya `daily`, `weekly`, `monthly`.
- `model_name` dan `model_version` wajib.
- `train_start_date <= train_end_date`.
- `predict_start_date <= predict_end_date`.
- `metrics`, `summary`, `data_quality` harus valid JSON.
- `status` hanya `success`, `failed`, `running`.
- `results` tidak boleh kosong untuk atomic save.
- `target_date` harus valid date.
- `predicted_value` harus angka finite dan tidak negatif/NaN.

### 7.3 Repository transaction

File utama:

```text
internal/repository/forecast_run_repository.go
internal/repository/forecast_result_repository.go
```

Aturan penting:

- `ForecastRunRepository.Create()` tidak langsung membuat `is_latest=true`.
- `SaveWithResults()` melakukan transaction: insert run, insert results, finalize latest, commit.
- `finalizeLatestForecastRunTx()` hanya menandai latest jika status `success` dan result count > 0.
- Run lama untuk store/type/horizon yang sama diubah menjadi `is_latest=false`.
- `GetLatestForecast()` hanya mengambil run `status='success'`, `is_latest=true`, dan punya results.

## 8. Migration

Folder:

```text
backend/migrations/
```

Migration penting:

| File | Tujuan |
|---|---|
| `20260618_security_hardening_indexes.sql` | Index umum untuk query data master, order, sales, finance, forecast |
| `20260625_forecast_core_p1_indexes.sql` | Index latest lookup dan result lookup |
| `20260625_forecast_runs_results_core.sql` | Deprecate/drop `forecast_predictions`, unique latest, index forecast |
| `20260707_forecast_latest_requires_results.sql` | Pastikan latest tidak orphan tanpa results |
| `20260707_forecast_write_security_latest_success.sql` | Constraint latest hanya success dan revoke write anon/authenticated |

Catatan deployment: migration di repo berupa SQL manual. Developer berikutnya perlu memastikan urutan eksekusi migration terdokumentasi di deployment checklist.

## 9. Swagger

File generated:

```text
backend/docs/swagger.json
backend/docs/swagger.yaml
backend/docs/docs.go
```

Paths yang terlihat pada Swagger v1.5:

```text
GET  /api/forecast-results
GET  /api/forecast-results/{id}
GET  /api/forecast-runs/{id}
GET  /api/forecast/latest
GET  /api/forecast/visitors/latest
GET  /internal/forecast/forecast-results
POST /internal/forecast/forecast-results
GET  /internal/forecast/forecast-results/{id}
POST /internal/forecast/forecast-runs
GET  /internal/forecast/forecast-runs/{id}
POST /internal/forecast/save
GET  /internal/forecast/visitors-daily-history
```

Swagger sudah cukup fokus forecast. Tetap pastikan setiap perubahan route internal/public diikuti regenerate docs.

## 10. Environment

Gunakan `.env.example` sebagai template:

```env
APP_ENV=development
SERVER_PORT=8080
DB_HOST=localhost
DB_PORT=5432
DB_USER=sora_app
DB_PASSWORD=change-me
DB_NAME=postgres
DB_SSLMODE=disable
JWT_SECRET=change-me-use-at-least-32-random-characters
REDIS_URL=
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
ENABLE_SWAGGER=true
ENABLE_TEST_ROUTES=false
INTERNAL_SERVICE_KEY=change-me
```

Jangan commit `.env` asli. Zip v1.5 berisi `.env`; itu harus dibersihkan di repo final.

## 11. Cara menjalankan

```bash
cd backend
cp .env.example .env
# edit .env
go mod download
go run ./cmd/api
```

Build binary Linux:

```bash
cd backend
GOOS=linux GOARCH=amd64 go build -o api ./cmd/api
```

Run test:

```bash
cd backend
go test ./...
```

Health check:

```bash
curl http://localhost:8080/health
```

## 12. Checklist sebelum merge backend

- `go test ./...` pass.
- `go.mod` memakai versi Go yang tersedia di CI/server.
- `.env` tidak ikut commit.
- `api.exe` atau binary build tidak ikut commit.
- Migration sudah dijalankan di database target.
- Swagger regenerate jika route/handler forecast berubah.
- `POST /internal/forecast/save` sukses dengan key valid.
- Request invalid menghasilkan 400, bukan 500.
- Latest forecast tidak orphan.
- Public route tidak punya POST write forecast.
- CORS production tidak wildcard.

## 13. Saran pengembangan backend

### Wajib dekat ini

1. **Rapikan Go version.** `go 1.25.0` berisiko di server Proxmox jika toolchain belum tersedia.
2. **Tambahkan migration runner/prosedur.** Saat ini migration SQL manual; developer baru bisa lupa menjalankan file tertentu.
3. **Tambahkan query filter/pagination.** `GET /api/forecast-results` dibatasi 500 row dan frontend filtering client-side; untuk data tumbuh, buat query berdasarkan `forecast_type`, `horizon_label`, `store_id`, `item_type`, `limit`, `offset`.
4. **Audit error response.** Beberapa route non-forecast mungkin masih mengembalikan error generik atau detail internal. Standarkan format error.
5. **Pisahkan route internal dari public di Nginx.** Idealnya `/internal/*` hanya bisa diakses dari localhost/private network.

### Setelah MVP

1. Tambah observability: request ID, structured log, slow query log.
2. Tambah integration test dengan test database.
3. Tambah role/permission granular untuk resource selain forecast.
4. Tambah health check DB/Redis detail untuk deployment.
5. Tambah graceful migration/rollback strategy.
6. Tambah audit log untuk forecast save/retrain.

## 14. Known risks

| Risiko | Dampak | Mitigasi |
|---|---|---|
| `.env` ikut zip/repo | Secret bocor | Commit `.env.example` saja, rotate secret jika sudah tersebar |
| `go.mod` terlalu baru | Build gagal di server | Pin ke versi Go yang dipakai server |
| Route internal terekspos public | Data integrity forecast rusak | Network restrict + service key + Nginx rule |
| Save dua langkah run/results gagal di tengah | Latest kosong atau run orphan | Gunakan `/internal/forecast/save` atomik |
| Query forecast-results terlalu umum | Frontend lambat saat data besar | Tambah filter/pagination/latest endpoint |
| Migration tidak dijalankan | Constraint/index/security tidak aktif | Deployment checklist + migration runner |
