# Modul Forecasting Stok Barang (Prophet)

Forecast service untuk prediksi pemakaian bahan baku F&B per pasangan store dan ingredient.
Service ini berbasis Python + Flask dan mengambil data historis dari backend Go.

## Daftar Bagian
- Ringkasan
- Bagian yang Sering Diganti
- Fitur Aktif
- Status dan Batasan Saat Ini
- Struktur Folder
- Persyaratan Sistem dan Instalasi
- Konfigurasi Environment
- Menjalankan Service
- Endpoint API
- Memahami Output
- Troubleshooting
- Catatan Production
- Changelog Ringkas

## Ringkasan
- Forecast mendukung frekuensi harian (`D`), mingguan (`W`), dan bulanan (`M`).
- Training berjalan async dan bisa dipantau per `task_id`.
- Model disimpan per pasangan store-ingredient pada folder `models/inventory/`.
- Confidence score dihitung dari metrik error (`100 - MAPE`, fallback `100 - sMAPE`).

## Bagian yang Sering Diganti
Gunakan bagian ini kalau ingin cepat update tanpa menyentuh seluruh README.

### 1) Environment (`.env`) - paling sering diganti
```env
BACKEND_API_URL=http://localhost:8080/api
TRAINING_MAX_WORKERS=4
```

### 2) Pair Contoh untuk Testing - sering diganti
```text
STORE_ID_SAMPLE=b4e2f559-9615-4263-84fe-9ee97780748f
INGREDIENT_ID_SAMPLE=b98b5042-30b5-4dc7-80ce-7dbb4797c4c7
```

### 3) Contoh Curl Forecast - sering diganti
```bash
curl -X POST http://localhost:5000/api/inventory/forecast \
  -H "Content-Type: application/json" \
  -d '{"store_id":"STORE_ID_SAMPLE","ingredient_id":"INGREDIENT_ID_SAMPLE","periods":4,"freq":"W"}'
```

### 4) Dependencies - update kalau versi package berubah
```text
flask==3.0.0
pandas==2.2.2
numpy==1.26.4
prophet==1.1.5
cmdstanpy==1.2.4
joblib==1.4.2
holidays==0.60
requests==2.32.3
APScheduler==3.10.4
scikit-learn==1.5.0
python-dotenv==1.0.1
```

## Fitur Aktif
- Prediksi non-negatif dengan clip manual (`growth='linear'`).
- Data harian diisi nol hanya sampai tanggal transaksi terakhir aktual.
- Training adaptif berdasarkan panjang data (short/medium/long).
- Regressor: weekend, hari libur nasional, placeholder store closed.
- Simpan metrik: MAE, RMSE, MAPE, sMAPE, R2, explained variance, data_days.
- Training paralel dengan `ThreadPoolExecutor` (`TRAINING_MAX_WORKERS`).
- Scheduler retrain mingguan (Minggu 02:00).

## Status dan Batasan Saat Ini
- Belum ada autentikasi/otorisasi endpoint (development only).
- Progress training disimpan di memori proses (hilang jika restart).
- Model disimpan di filesystem lokal (belum object storage/versioning).
- Filter data masih dilakukan di sisi Python setelah menarik data dari API.
- `is_store_closed` masih placeholder (`0`).

## Struktur Folder
```text
forecast-service/
├── app.py
├── config.py
├── .env
├── requirements.txt
├── modules/
│   └── inventory/
│       ├── forecaster.py
│       └── trainer.py
├── models/
│   └── inventory/
└── README.md
```

## Persyaratan Sistem dan Instalasi
### Semua OS
- Python 3.12
- pip terbaru

### Windows
```cmd
cd forecast-service
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Linux/Mac
```bash
cd forecast-service
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Catatan kompatibilitas:
- Gunakan `numpy==1.26.4` untuk kompatibilitas Prophet `1.1.5`.
- Backend Stan menggunakan `cmdstanpy`.

## Konfigurasi Environment
Buat file `.env` di `forecast-service/`:

```env
BACKEND_API_URL=http://localhost:8080/api
TRAINING_MAX_WORKERS=4
```

Penjelasan:
- `BACKEND_API_URL`: endpoint backend Go.
- `TRAINING_MAX_WORKERS`: jumlah pasangan yang dilatih paralel.

## Menjalankan Service
```bash
python app.py
```

Service berjalan di `http://localhost:5000`.

## Endpoint API
### 1) Start training (async)
```bash
curl -X POST http://localhost:5000/api/inventory/train/start
```

### 2) Cek status training
```bash
curl http://localhost:5000/api/inventory/train/status/<task_id>
```

### 3) Forecast
Contoh harian (7 hari):
```bash
curl -X POST http://localhost:5000/api/inventory/forecast \
  -H "Content-Type: application/json" \
  -d '{"store_id":"b4e2f559-9615-4263-84fe-9ee97780748f","ingredient_id":"b98b5042-30b5-4dc7-80ce-7dbb4797c4c7","periods":7,"freq":"D"}'
```

Contoh mingguan (4 minggu):
```bash
curl -X POST http://localhost:5000/api/inventory/forecast \
  -H "Content-Type: application/json" \
  -d '{"store_id":"b4e2f559-9615-4263-84fe-9ee97780748f","ingredient_id":"b98b5042-30b5-4dc7-80ce-7dbb4797c4c7","periods":4,"freq":"W"}'
```

Contoh bulanan (3 bulan):
```bash
curl -X POST http://localhost:5000/api/inventory/forecast \
  -H "Content-Type: application/json" \
  -d '{"store_id":"b4e2f559-9615-4263-84fe-9ee97780748f","ingredient_id":"b98b5042-30b5-4dc7-80ce-7dbb4797c4c7","periods":3,"freq":"M"}'
```

## Memahami Output
Field utama response:
- `metrics`: metrik evaluasi model.
- `forecast_summary`: total dan rata-rata periode prediksi.
- `prediction_analysis`: titik prediksi tertinggi/terendah.
- `model_confidence`: skor confidence berbasis MAPE/sMAPE.
- `daily_forecast` / `weekly_forecast` / `monthly_forecast`: array sesuai `freq`.

Aturan confidence:
- Jika `mape` ada: `confidence_score = 100 - mape`
- Jika `mape` tidak ada: `confidence_score = 100 - smape`
- Level: HIGH >= 85, MEDIUM >= 70, LOW < 70

## Troubleshooting
### Prophet gagal install di Windows
- Pastikan C++ Build Tools terpasang.
- Coba reinstall NumPy dan Prophet:

```cmd
pip uninstall numpy -y
pip install numpy==1.26.4
pip install prophet==1.1.5 --no-cache-dir
```

### Error umum
- `FileNotFoundError: Model not found`
  Jalankan training dulu.
- `ConnectionError saat forecast`
  Pastikan backend Go hidup dan `.env` benar.
- Port `5000` bentrok
  Ganti port di `app.py`.
- Prediksi banyak nol
  Hapus model lama di `models/inventory/*`, lalu retrain.

## Catatan Production
Sebelum dipakai di lingkungan production:
- Tambah autentikasi dan otorisasi endpoint.
- Jalankan Flask di WSGI server (Gunicorn/Waitress), bukan dev server.
- Pindahkan job training ke queue/worker terpisah.
- Gunakan penyimpanan model yang mendukung versioning (object storage).
- Tambah monitoring, logging terstruktur, dan alerting.

## Changelog Ringkas
### 21 Mei 2026
- Integrasi forecast-service dengan backend Go.
- Training Prophet per pasangan store-ingredient.

### 25 Mei 2026
- Response diseragamkan dengan modul lain.
- Training async + endpoint status.

### 29 Mei 2026
- Perbaikan prediksi non-negatif.
- Training adaptif + dukungan `D/W/M`.
- Tambahan metrik `smape`, `r2_score`, `explained_variance`.
- Parallel training dan `end_date` dinamis.
