# 🔮 Sora Forecast Service

Microservice Python untuk **prediksi jumlah pengunjung restoran** menggunakan Random Forest.
Terintegrasi dengan backend Golang Sora Finance API.

---

## 📁 Struktur Project

```
forecast-service/
│
├── app/
│   ├── api/
│   │   ├── forecast_router.py       # Endpoint /forecast/predict & /forecast/retrain
│   │   └── health_router.py         # Endpoint /health & /
│   │
│   ├── services/
│   │   ├── golang_client.py         # Async HTTP client ke Golang API
│   │   └── forecast_service.py      # Business logic: orchestrate semua layer
│   │
│   ├── models/
│   │   └── schemas.py               # Pydantic request/response schemas
│   │
│   ├── preprocessing/
│   │   └── feature_engineering.py   # Feature engineering pipeline
│   │
│   ├── training/
│   │   └── trainer.py               # Training & loading Random Forest model
│   │
│   └── utils/
│       ├── config.py                # Settings dari environment variables
│       └── logger.py                # Rotating file + console logger
│
├── saved_models/                    # Model .joblib tersimpan di sini
├── logs/                            # Log files
│
├── golang_integration_example/
│   ├── forecast_client.go           # Go client untuk memanggil Python service
│   └── forecast_handler.go          # Go HTTP handler (chi router)
│
├── train_manual.py                  # Script training mandiri (offline)
├── main.py                          # Entry point FastAPI
├── requirements.txt
└── .env
```

---

## ⚙️ Setup & Instalasi

### 1. Clone dan Install Dependencies

```bash
cd forecast-service
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Konfigurasi Environment

Edit `.env`:
```env
GOLANG_API_BASE_URL=http://localhost:8080/api
SERVICE_HOST=0.0.0.0
SERVICE_PORT=5000
SERVICE_ENV=development
MODEL_DIR=saved_models
FORECAST_HORIZON_DAYS=30
RETRAIN_INTERVAL_DAYS=7
LOG_LEVEL=INFO

# DB config (bisa diambil dari backend/.env)
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=sora_finance
DB_SSLMODE=disable
```

### 3. Jalankan Service

```bash
python main.py
# atau dengan uvicorn langsung:
uvicorn main:app --host 0.0.0.0 --port 5000 --reload
```

### 4. Training Awal (Opsional — bisa via API)

```bash
# Menggunakan data dari Golang API
python train_manual.py --store_id <UUID_STORE_ANDA>

# Testing offline dengan data dummy
python train_manual.py --store_id test-store-001 --use_dummy
```

---

## 📡 API Endpoints

### `POST /api/forecast/predict`
Prediksi jumlah pengunjung untuk N hari ke depan.

**Request:**
```json
{
  "store_id": "550e8400-e29b-41d4-a716-446655440000",
  "forecast_days": 30,
  "start_date": "2025-06-01"
}
```

**Response:**
```json
{
  "store_id": "550e8400-e29b-41d4-a716-446655440000",
  "generated_at": "2025-05-20T08:00:00",
  "forecast_horizon_days": 30,
  "forecasts": [
    {
      "date": "2025-06-01",
      "predicted_visitors": 112,
      "predicted_transactions": 112,
      "lower_bound": 89,
      "upper_bound": 135,
      "day_of_week": "Minggu",
      "is_weekend": true
    },
    {
      "date": "2025-06-02",
      "predicted_visitors": 78,
      "predicted_transactions": 78,
      "lower_bound": 61,
      "upper_bound": 95,
      "day_of_week": "Senin",
      "is_weekend": false
    }
  ],
  "model_metadata": {
    "trained_at": "2025-05-19T22:00:00",
    "training_data_points": 337,
    "cv_mae": 8.4,
    "cv_rmse": 11.2,
    "feature_importance": {
      "lag_7": 0.18,
      "rolling_mean_7": 0.15,
      "lag_1": 0.12,
      "is_weekend": 0.11,
      "sin_dow": 0.09
    }
  },
  "status": "success",
  "message": "Berhasil memprediksi 30 hari ke depan"
}
```

---

### `POST /api/forecast/retrain`
Train ulang model dengan data historis terbaru dari Golang API.

**Request:**
```json
{
  "store_id": "550e8400-e29b-41d4-a716-446655440000",
  "force": true
}
```

---

### `POST /api/forecast/predict-weekly`
Prediksi jumlah pengunjung **mingguan** untuk N minggu ke depan.

**Request:**
```json
{
  "store_id": "550e8400-e29b-41d4-a716-446655440000",
  "forecast_weeks": 8,
  "start_date": "2025-06-02"
}
```

**Response (ringkas):**
```json
{
  "store_id": "550e8400-e29b-41d4-a716-446655440000",
  "forecast_horizon_weeks": 8,
  "forecasts": [
    {
      "period_start": "2025-06-02",
      "period_end": "2025-06-08",
      "predicted_visitors": 820,
      "lower_bound": 760,
      "upper_bound": 900,
      "week_of_year": 23,
      "year": 2025
    }
  ]
}
```

---

### `POST /api/forecast/predict-monthly`
Prediksi jumlah pengunjung **bulanan** untuk N bulan ke depan.

**Request:**
```json
{
  "store_id": "550e8400-e29b-41d4-a716-446655440000",
  "forecast_months": 6,
  "start_date": "2025-06-01"
}
```

**Response (ringkas):**
```json
{
  "store_id": "550e8400-e29b-41d4-a716-446655440000",
  "forecast_horizon_months": 6,
  "forecasts": [
    {
      "period_start": "2025-06-01",
      "period_end": "2025-06-30",
      "predicted_visitors": 3400,
      "lower_bound": 3100,
      "upper_bound": 3700,
      "month": 6,
      "year": 2025
    }
  ]
}
```

**Response:**
```json
{
  "store_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "success",
  "message": "Model berhasil dilatih dengan 337 data points",
  "training_data_points": 337,
  "cv_mae": 8.4,
  "cv_rmse": 11.2,
  "trained_at": "2025-05-20T08:05:12",
  "feature_importance": {
    "lag_7": 0.18,
    "rolling_mean_7": 0.15,
    "is_weekend": 0.11
  }
}
```

---

### `GET /api/forecast/models`
Daftar store yang sudah memiliki model tersimpan.

```json
{
  "status": "success",
  "trained_store_count": 3,
  "store_ids": [
    "550e8400-e29b-41d4-a716-446655440000",
    "661f9511-f30c-52e5-b827-557766551111"
  ]
}
```

---

### `GET /health`
Status kesehatan service.

```json
{
  "status": "healthy",
  "service": "sora-forecast-service",
  "version": "1.0.0",
  "golang_api_reachable": true,
  "loaded_models": ["550e8400-..."],
  "timestamp": "2025-05-20T08:00:00"
}
```

---

## 🔧 Integrasi dengan Golang

### Tambahkan environment variable di Golang

```env
PYTHON_FORECAST_URL=http://127.0.0.1:5000
```

### Daftarkan route di `main.go`

```go
import forecastclient "sora-finance-api/internal/forecastclient"

// Di dalam main():
forecastHandler := forecastclient.NewForecastHandler()
forecastHandler.RegisterRoutes(r)
```

### Panggil dari service Golang manapun

```go
client := forecastclient.NewForecastClient()

// Prediksi 30 hari ke depan
result, err := client.GetForecast(ctx, storeID, 30)
if err != nil {
    log.Printf("Forecast error: %v", err)
    return
}

for _, day := range result.Forecasts {
    fmt.Printf("%s (%s): ~%d pengunjung [%d–%d]\n",
        day.Date, day.DayOfWeek,
        day.PredictedVisitors,
        day.LowerBound, day.UpperBound,
    )
}

// Retrain model
retrainResult, err := client.RetrainModel(ctx, storeID, false)
```

---

## 🧠 Feature Engineering

Model menggunakan **29 fitur** yang dibangun dari data historis harian:

| Kategori | Fitur | Keterangan |
|---|---|---|
| **Kalender** | `day_of_week`, `day_of_month`, `month`, `quarter`, `week_of_year` | Posisi waktu |
| **Flag** | `is_weekend`, `is_month_start`, `is_month_end` | Hari khusus |
| **Siklik** | `sin_dow`, `cos_dow`, `sin_month`, `cos_month` | Encoding periodik |
| **Lag** | `lag_1` s/d `lag_28` | Nilai historis 1–28 hari lalu |
| **Rolling** | `rolling_mean/std/max/min_7/14/28` | Statistik jendela geser |
| **Expanding** | `expanding_mean` | Rata-rata keseluruhan historis |
| **Omzet** | `omzet_per_visitor`, `lag_omzet_7`, `rolling_omzet_7` | Jika data omzet tersedia |

---

## 🔄 Alur Sistem Lengkap

```
Flutter App
    │ GET /api/forecast/predict/{storeId}?days=30
    ▼
Golang API (port 8080)
    │ POST http://127.0.0.1:5000/api/forecast/predict
    ▼
Python Forecast Service (port 5000)
    │
    ├─► Cek model tersedia?
    │       Tidak → Auto-retrain dulu
    │
    ├─► Fetch data historis dari Golang API
    │   ├── GET /api/sales-daily-summaries?store_id=...
    │   ├── GET /api/sales-monthly-summaries?store_id=...
    │   └── GET /api/orders?store_id=...   (fallback)
    │
    ├─► Feature Engineering
    │   (lag features, rolling stats, kalender, siklik)
    │
    ├─► Random Forest Prediction
    │   (iteratif per hari, confidence interval dari distribusi pohon)
    │
    └─► Return JSON → Golang → Flutter
```

---

## 🚀 Production Deployment

### Dengan Gunicorn (rekomendasi production)

```bash
pip install gunicorn
gunicorn main:app \
    -w 2 \
    -k uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:5000 \
    --timeout 120 \
    --access-logfile logs/access.log \
    --error-logfile logs/error.log
```

### Dengan Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p saved_models logs
EXPOSE 5000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
```

```bash
docker build -t sora-forecast .
docker run -d \
  -p 5000:5000 \
  -e GOLANG_API_BASE_URL=http://golang-api:8080/api \
  -v $(pwd)/saved_models:/app/saved_models \
  -v $(pwd)/logs:/app/logs \
  --name sora-forecast \
  sora-forecast
```

### Systemd Service (Linux)

```ini
[Unit]
Description=Sora Forecast Service
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/opt/sora-forecast
Environment="PATH=/opt/sora-forecast/venv/bin"
ExecStart=/opt/sora-forecast/venv/bin/uvicorn main:app --host 0.0.0.0 --port 5000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

## 📊 Interpretasi Hasil

- **`predicted_visitors`**: Estimasi jumlah pengunjung pada hari tersebut
- **`lower_bound` / `upper_bound`**: Range 80% confidence interval — kemungkinan besar jumlah pengunjung berada di antara nilai ini
- **`cv_mae`**: Rata-rata error prediksi dalam satuan pengunjung (lebih kecil = lebih akurat)
- **`feature_importance`**: Fitur mana yang paling berpengaruh terhadap prediksi

> **Contoh interpretasi:** Jika `predicted_visitors=100`, `lower_bound=80`, `upper_bound=120`, dan `cv_mae=8.4` — maka model memperkirakan akan ada sekitar 100 pengunjung, dengan error rata-rata ±8 pengunjung.

---

## ⚠️ Minimum Data Requirement

| Kondisi | Minimum |
|---|---|
| Training awal bisa dilakukan | 30 hari data |
| Lag features lengkap (lag_28) | 29+ hari data |
| Hasil forecast akurat | 90+ hari data (disarankan 180+) |

Model akan otomatis menolak dengan pesan error yang jelas jika data historis tidak mencukupi.
