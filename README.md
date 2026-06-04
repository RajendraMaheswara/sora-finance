# feat: Modul Forecasting Stok Barang dengan Prophet

## PROGRESS

### 21 Mei 2026
- Integrasi forecast-service (Python/Flask) ke backend Go via API
- Training model Prophet per pasangan (store, ingredient)
- Data historis diambil dari endpoint `GET /api/ingredient-stock-histories`
- Agregasi harian `SUM(reduced)` dengan pengisian 0 untuk hari kosong
- Support fitur weekend, hari libur nasional (holidays Indonesia)
- Endpoint forecast: `POST /api/inventory/forecast` (mingguan/bulanan)
- Auto-training scheduler tiap Minggu jam 2 pagi
- Model disimpan sebagai `.pkl` di `models/inventory/`

### 25 Mei 2026
- Format response disamakan dengan modul visitor/sales:  
  `success`, `data` (metrics, forecast_summary, prediction_analysis, model_confidence, daily_forecast)
- Confidence score dihitung dari MAPE (100 - MAPE), dengan level HIGH/MEDIUM/LOW
- Training dijalankan secara **asinkron** melalui endpoint `/api/inventory/train/start`
- Monitoring progress training via `/api/inventory/train/status/<task_id>`
- Metrik evaluasi (MAE, RMSE, MAPE) disimpan otomatis dalam file JSON setelah training
- Backward compatibility: endpoint `/api/inventory/train` tetap bisa dipakai (langsung async)
- **Uji coba endpoint forecast berhasil** mengembalikan struktur lengkap (daily_forecast, summary, analysis, confidence)
- Response sudah sesuai untuk konsumsi dashboard; field `metrics` dan `confidence` akan terisi setelah retrain dengan kode terbaru

### 29 Mei 2026
- **Prediksi tidak lagi negatif/nol** – beralih ke `growth='linear'` dengan clip manual
- **Data historis tidak lagi dipanjangkan buatan** – pengisian nol hanya sampai tanggal transaksi terakhir
- **Parameter training adaptif** – cross‑validation & yearly seasonality menyesuaikan panjang data (aman untuk toko baru 3 bulan hingga toko lama bertahun‑tahun)
- **Dukungan frekuensi harian (`D`)**, mingguan (`W`), dan bulanan (`M`) dengan agregasi otomatis  
  - `freq='D'` → `daily_forecast` (array harian)  
  - `freq='W'` → `weekly_forecast` (array total per minggu)  
  - `freq='M'` → `monthly_forecast` (array total per bulan)
- **R² dan explained variance** kini dihitung dari data latih dan disimpan di metrik
- **Metrik sMAPE** ditambahkan sebagai fallback saat MAPE tidak tersedia
- **Training paralel** dengan `ThreadPoolExecutor` (jumlah worker bisa diatur di `.env`)
- **`end_date` dinamis** – default hari ini, tidak lagi statis 2026-12-31
- Berbagai perbaikan bug: timezone UTC, `NoneType` pada model, validasi input

### 4 Juni 2026
- **Penyimpanan hasil forecast ke database** – tiga tabel terisi otomatis setelah training:
  - `forecast_predictions` → untuk dashboard (ringan, cepat)
  - `forecast_runs` → tracking setiap sesi training
  - `forecast_results` → detail prediksi per tanggal, siap evaluasi (masih dalam penyelarasan tipe data)
- **Payload disamakan** dengan modul visitor/sales:
  - `horizon_label` deskriptif (`"daily"`/`"weekly"`/`"monthly"`)
  - `metrics`, `summary`, `data_quality` dikirim sebagai **string JSON**
  - `model_version` = `"1.0.0"` (statis, mudah dilacak)
  - `started_at` & `finished_at` terisi format `YYYY-MM-DD HH:MM:SS+00`
- **Backend Go** menyediakan endpoint baru:
  - `POST /api/forecast-predictions`
  - `POST /api/forecast-runs`
  - `POST /api/forecast-results` (masih di-debug untuk tipe data)
- **Auto‑save setelah training** – setiap pasangan yang selesai dilatih langsung menyimpan hasil ke ketiga tabel
- **Endpoint manual** – `POST /api/inventory/save-all-forecasts` untuk trigger simpan tanpa training ulang
- Bug fix: `model_version` terlalu panjang (varchar overflow), timezone UTC, field `null` di database

## KENDALA / KEKURANGAN

### 21 Mei 2026
- Hasil prediksi bisa negatif karena banyak data nol (intermittent) ✅ **teratasi**
- Belum menggunakan batasan nilai minimal (floor=0) pada Prophet ✅ **teratasi**
- Belum tuning parameter untuk data jarang ✅ **teratasi dengan grid adaptif**
- Training masih dilakukan satu per satu ✅ **teratasi dengan paralelisasi**
- Belum ada endpoint untuk evaluasi akurasi model ✅ **metrik kini tersimpan & dikembalikan**
- Filter tanggal di API masih manual (belum difilter di server)
- Opsi 'libur toko' masih placeholder (default 0)

### 25 Mei 2026
- Model yang dilatih sebelum revisi kode (21 Mei) tidak memiliki file metrics ✅ **teratasi**
- Nilai negatif pada predicted_usage masih muncul ✅ **teratasi dengan clip**
- Confidence sangat bergantung pada MAPE; pada data noise tinggi, confidence bisa rendah (wajar – sudah dijelaskan di response)
- Metrik R² dan explained variance belum dihitung ✅ **teratasi**
- Belum ada fitur auto‑clean model usang / tidak terpakai
- Progress training disimpan di memori (hilang jika service restart)

### 29 Mei 2026
- Confidence tetap dihitung dari MAPE (hanya pada hari bertransaksi) – perlu dipahami sebagai indikator akurasi pada hari sibuk, bukan probabilitas statistik
- Filter tanggal di server Go belum dimanfaatkan; semua data ditarik lalu difilter di Python (cukup untuk development, tapi tidak optimal untuk skala besar)
- Tidak ada autentikasi/otorisasi di endpoint (untuk production harus ditambahkan – saat ini hanya development)
- Job training masih dalam proses Flask, belum queue/worker terpisah
- Model disimpan di filesystem lokal (cukup untuk development, production perlu versioning & object storage)

### 4 Juni 2026
- `data_quality` masih minimal; bisa diperkaya dengan info outlier, missing dates, dsb.
- `model_version` statis `"1.0.0"` belum otomatis naik jika model diperbarui signifikan
- Belum ada mekanisme retry otomatis jika penyimpanan ke database gagal (saat ini hanya log error)

---

## STRUKTUR FOLDER

```
forecast-service/
├── app.py # Entry point Flask, routing, scheduler
├── config.py # Konfigurasi (API backend Go, model path)
├── .env # Environment variables (BACKEND_API_URL)
├── requirements.txt # Dependencies Python
├── modules/ # Logika forecasting per modul
│ ├── init.py
│ └── inventory/ # Modul stok barang
│ ├── init.py
│ ├── forecaster.py # Kelas InventoryForecaster (training, prediksi)
│ └── trainer.py # Fungsi untuk melatih semua pasangan (store, ingredient)
├── models/ # Tempat penyimpanan model hasil training (.pkl)
│ └── inventory/ # Khusus model stok barang
└── utils/ # (Dihapus, tidak digunakan)
```


---

## PERSYARATAN SISTEM & INSTALASI

### Untuk Semua Sistem Operasi
- **Python 3.12** (wajib - Prophet belum mendukung Python 3.13+ dengan baik)
- **pip** versi terbaru (jalankan `pip install --upgrade pip`)

### Untuk Windows (fokus utama tim)
1. **Download & Install Python 3.12** dari [python.org](https://www.python.org/downloads/).
Centang opsi *"Add Python to PATH"* saat instalasi.
2. Buka **Command Prompt** atau **PowerShell**, lalu buat virtual environment:

```cmd
cd forecast-service
python -m venv venv
venv\Scripts\activate
```

Install dependensi:

```cmd
pip install -r requirements.txt
```

Jika ada error terkait `cmdstanpy` atau `Prophet`, lihat bagian Troubleshooting di bawah.

### Untuk Linux/Mac

```bash
cd forecast-service
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### ISI `requirements.txt`

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

Catatan: Versi NumPy harus `1.26.4` karena Prophet `1.1.5` tidak kompatibel dengan NumPy `2.x`.
Backend Stan menggunakan `cmdstanpy` (bukan `pystan`) untuk stabilitas di Windows.

## PANDUAN MENJALANKAN SERVICE

### 1. Konfigurasi `.env`
Buat file `.env` di folder `forecast-service` (jika belum ada):

```text
BACKEND_API_URL=http://localhost:8080/api
TRAINING_MAX_WORKERS=4
```

- `BACKEND_API_URL`: URL backend Go (sesuaikan host/port)
- `TRAINING_MAX_WORKERS`: jumlah pasangan yang dilatih bersamaan (default 4, cocok untuk laptop)

### 2. Jalankan Service

```bash
python app.py
```

Service tersedia di `http://localhost:5000`.

### 3. Training Model (Async)
Memulai training semua pasangan toko-bahan secara background:

```bash
curl -X POST http://localhost:5000/api/inventory/train/start
```

Response:

```json
{
  "task_id": "uuid-string",
  "message": "Training dimulai. Pantau progress di /api/inventory/train/status/<task_id>"
}
```

Pantau progress:

```bash
curl http://localhost:5000/api/inventory/train/status/<task_id>
```

Status: STARTING -> RUNNING -> DONE (atau ERROR).

### 4. Forecasting
Gunakan endpoint `POST /api/inventory/forecast` dengan body JSON.

Contoh harian (7 hari ke depan):

```bash
curl -X POST http://localhost:5000/api/inventory/forecast \
  -H "Content-Type: application/json" \
  -d '{"store_id":"b4e2f559-9615-4263-84fe-9ee97780748f","ingredient_id":"b98b5042-30b5-4dc7-80ce-7dbb4797c4c7","periods":7,"freq":"D"}'
```

Contoh mingguan (4 minggu ke depan):

```bash
curl -X POST http://localhost:5000/api/inventory/forecast \
  -H "Content-Type: application/json" \
  -d '{"store_id":"b4e2f559-9615-4263-84fe-9ee97780748f","ingredient_id":"b98b5042-30b5-4dc7-80ce-7dbb4797c4c7","periods":4,"freq":"W"}'
```

Contoh bulanan (3 bulan ke depan):

```bash
curl -X POST http://localhost:5000/api/inventory/forecast \
  -H "Content-Type: application/json" \
  -d '{"store_id":"b4e2f559-9615-4263-84fe-9ee97780748f","ingredient_id":"b98b5042-30b5-4dc7-80ce-7dbb4797c4c7","periods":3,"freq":"M"}'
```

### 5. Memahami Output
Response mengikuti format yang seragam dengan modul visitor/sales:

```json
{
  "success": true,
  "message": "Forecast W untuk 4 periode ke depan",
  "data": {
    "store_id": "...",
    "ingredient_id": "...",
    "metrics": {
      "mae": 2.94,
      "rmse": 3.57,
      "mape": 0.25,
      "smape": 0.29,
      "r2_score": 0.5453,
      "explained_variance": 0.5453,
      "data_days": 182,
      "cv_initial": "109 days"
    },
    "forecast_summary": {
      "total_predicted_usage_next_28_days": 290.5,
      "average_daily_usage_next_28_days": 10.38
    },
    "prediction_analysis": {
      "highest_prediction_day": "2020-07-28",
      "highest_prediction_value": 11.44,
      "lowest_prediction_day": "2020-07-04",
      "lowest_prediction_value": 9.4
    },
    "model_confidence": {
      "confidence_score": 99.75,
      "confidence_level": "HIGH"
    },
    "weekly_forecast": [
      {
        "week_start": "2020-07-01",
        "week_end": "2020-07-07",
        "predicted_usage": 68.97,
        "lower_bound": 51.38,
        "upper_bound": 88.84,
        "average_daily_usage": 9.85
      },
      "..."
    ]
  }
}
```

- `metrics`: metrik evaluasi model dari cross-validation dan data latih
- `forecast_summary`: total dan rata-rata pemakaian selama periode yang diminta
- `prediction_analysis`: hari dengan prediksi tertinggi/terendah
- `model_confidence`: `confidence_score = 100 - MAPE` (jika MAPE tidak ada, pakai sMAPE); level: HIGH >= 85, MEDIUM >= 70, LOW < 70
- `daily_forecast` / `weekly_forecast` / `monthly_forecast`: array prediksi sesuai `freq`

### 6. Menyimpan Hasil Forecast ke Database
Setelah training, hasil forecast otomatis tersimpan ke database.
Namun, jika ingin menyimpan ulang tanpa training, gunakan endpoint berikut:

**Simpan ulang semua model yang sudah ada:**
```
curl -X POST http://localhost:5000/api/inventory/save-all-existing
```

**Simpan ulang satu pasangan saja:**
```
curl -X POST http://localhost:5000/api/inventory/save-all-forecasts \
  -H "Content-Type: application/json" \
  -d '{"store_id":"b4e2f559-...","ingredient_id":"b98b5042-...","periods":4,"freq":"W"}'
```
Data akan masuk ke tabel forecast_predictions (dashboard) dan forecast_runs (tracking).


## TROUBLESHOOTING CEPAT

### Masalah Instalasi Prophet di Windows

**Error: `cmdstanpy not found`**
Install dulu compiler C++: download Microsoft C++ Build Tools, pilih workload "Desktop development with C++", lalu install.

**Error: `numpy incompatible`**
Pastikan `numpy==1.26.4` terinstall. Jika masih error, jalankan:

```cmd
pip uninstall numpy -y
pip install numpy==1.26.4
pip install prophet==1.1.5 --no-cache-dir
```

**Error: `prophet gagal build`**
Gunakan file wheel pre-compiled (jika tersedia) atau coba instalasi dengan conda:

```cmd
conda install -c conda-forge prophet
```

**Error: `ModuleNotFoundError: No module named 'prophet'`**
Pastikan virtual environment aktif (`venv\Scripts\activate`), lalu jalankan `pip install -r requirements.txt`.

### Masalah Umum (Semua OS)

**FileNotFoundError: Model not found...**
Training dulu: `curl -X POST http://localhost:5000/api/inventory/train/start`

**ConnectionError saat forecast**
Pastikan backend Go berjalan dan file `.env` sudah benar.

**Port 5000 sudah dipakai**
Ganti port di `app.py` (baris terakhir `app.run(port=5000)`).

**Training tidak kunjung selesai**
Cek log Flask, mungkin ada error koneksi ke backend Go. Pastikan data tersedia.

**Prediksi banyak yang nol**
Hapus model lama (`models/inventory/*`), lalu training ulang. Pastikan menggunakan kode terbaru.

## CATATAN PENTING

- Training ulang hanya diperlukan jika data historis bertambah. Scheduler otomatis berjalan tiap Minggu pukul 02:00.
- Semua data diambil dari API backend Go. Pastikan endpoint `GET /api/ingredient-stock-histories` dapat diakses.
- Untuk production, gunakan WSGI server seperti gunicorn atau waitress, jangan mengandalkan server development Flask.
- Progress training disimpan di memori: jika service restart, task lama tidak bisa dilacak.
- Confidence dihitung berdasarkan error pada hari dengan transaksi saja (karena MAPE/sMAPE tidak bisa dihitung saat aktual = 0). Untuk hari tanpa pemakaian, model mungkin overestimate.