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
- Model disimpan sebagai `.joblib` di `models/inventory/`

### 25 Mei 2026
- Format response disamakan dengan modul visitor/sales:  
  `success`, `data` (metrics, forecast_summary, prediction_analysis, model_confidence, daily_forecast)
- Confidence score dihitung dari MAPE (100 - MAPE), dengan level HIGH/MEDIUM/LOW
- Training inventory store dijalankan secara **asinkron** melalui endpoint `POST /api/forecast/inventory/retrain`
- Monitoring progress training via `GET /api/forecast/inventory/retrain/status/<task_id>`
- Metrik evaluasi (MAE, RMSE, MAPE) disimpan otomatis dalam file JSON setelah training
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
  - `forecast_runs/forecast_results` → untuk dashboard (ringan, cepat)
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

### 24 Juni 2026
- **Fix 400 Error Backend** – Tipe data `confidence_level` dipastikan bertipe integer (`int`) saat dikirim ke Golang, menyelesaikan masalah gagal simpan (`HTTP 400`) di tabel `forecast_results`.
- **Evaluasi Cross-Validation** – Metrik R² dan Explained Variance sekarang dihitung murni menggunakan data *out-of-sample* (Cross-Validation), bukan *in-sample*, sehingga lebih akurat.
- **Blended Confidence Score** – Perhitungan *confidence* kini menggabungkan sMAPE dan *bias penalty* sebagai komponen utama. R² dan Explained Variance hanya diikutsertakan jika nilainya bermakna (≥ 0.10), mengikuti *Cohen's guideline* untuk *effect size* minimal — sehingga data intermittent demand yang secara natural memiliki R² rendah tidak menghukum skor secara tidak adil.
- **Domain-Specific Thresholding** – Ambang batas (threshold) untuk *confidence level* disesuaikan dengan karakteristik riil (banyak *noise*) dari *intermittent demand*: `HIGH` (>= 60), `MEDIUM` (>= 40), `LOW` (< 40), sesuai dengan *best practice* dan jurnal logistik/supply chain.
- **Pembersihan Artifact** – File `.pkl` yang sudah kedaluwarsa telah dihapus dari repositori. Sistem sepenuhnya efisien dengan `.joblib`.
- **Autentikasi Internal** – Pemanggilan API dari Python ke backend Go kini mengikutsertakan *headers* `Config.backend_headers()` secara konsisten.
- **Dukungan Custom Start Date** – Menambahkan parameter opsional `start_date` pada *request body* untuk memungkinkan kalkulasi prediksi stok terhitung dari hari di masa depan, bukan hanya dari akhir histori (sangat membantu simulasi skenario).
- **Audit & Debiasing Data (Fase 0)** – Implementasi deteksi *stockout* tersembunyi (zero streak > 3 hari → NaN) dan deteksi outlier ekstrem (z-score > 3.5 → NaN) secara otomatis sebelum training. Prophet mengabaikan NaN secara native, sehingga model tidak lagi belajar dari nol palsu atau spike anomali.
- **Bias Detection (Fase 2)** – Menghitung `bias_ratio` (rasio total forecast / total actual) dari data *cross-validation*. Disimpan di metrik JSON sebagai `bias_ratio` agar bisa diaudit. Ideal: 0.95–1.05.
- **Honest Confidence Score** – Metrik R² dan EV kini murni menggunakan nilai CV (bukan `max(cv, train)` yang bisa menyembunyikan performa buruk). Confidence score juga memperhitungkan *bias penalty* — model yang bias sistematis akan mendapat skor lebih rendah.
- **Data Quality Tracking** – Metrik JSON diperkaya dengan `zero_ratio`, `outliers_nullified`, dan `stockout_days_nullified` untuk transparansi kualitas data yang digunakan training.

### 28 Juni 2026 (Universal Forecast)
- **Implementasi Aturan "Period Complete" (Data Truncation)**: Data historis otomatis dipotong ke akhir minggu/bulan lengkap yang terdekat untuk menghindari bias training di penghujung data. (Sesuai instruksi PM: data parsial/belum lengkap di akhir periode otomatis tidak diikutsertakan).
- **Pembersihan Endpoint Legacy**: Modul inventory kini murni mengandalkan tabel `forecast_runs` dan `forecast_results`.
- **Start Date Cerdas**: Apabila `start_date` dikosongi, modul otomatis menggunakan patokan **tanggal hari ini**, di mana prediksi *Weekly* otomatis bergeser ke hari Senin berikutnya, dan *Monthly* bergeser ke awal bulan (tanggal 1) terdekat.
- **Background Scheduler Inventory (Cron Job)**: Modul Inventory kini tergabung secara Universal bersama modul lain (visitors & sales) di dalam `app.py`. Memanfaatkan endpoint internal untuk melooping prediksi ke seluruh item bahan baku.
- **Konfigurasi Environment Baru**: Menambahkan kontrol `.env` untuk `FORECAST_MODE=scheduler`, `FORECAST_AFTER_CLOSE_SCHEDULER_MINUTES`, dan `FORECAST_24H_RUN_SCHEDULER_MINUTES`.

## KENDALA / KEKURANGAN YANG TERSISA (UPDATE 28 JUNI 2026)

- **Filter Data Historis**: Filter tanggal di server Go belum dimanfaatkan secara optimal; semua data ditarik lalu difilter di Python. Cukup untuk skala menengah, namun kurang efisien jika ukuran data mencapai puluhan ribu baris per toko.
- **Background Worker**: Job training masih berjalan di *thread* dalam proses Flask (`ThreadPoolExecutor`), belum menggunakan antrean (Message Queue) atau *worker* terpisah seperti Celery atau RabbitMQ.
- **Model Storage**: Model `.joblib` masih disimpan di filesystem lokal. Untuk deployment di server *production* terskala, perlu integrasi ke *Object Storage* (S3 / GCS).
- **Data Quality**: Atribut `data_quality` JSON yang di-post ke backend Go masih minimalis; dapat diperkaya dengan info jumlah *outlier* yang terdeteksi.
- **Model Versioning**: `model_version` masih di-*hardcode* `"1.0.0"`.
- **Fail-safe Database**: Belum ada mekanisme *retry* otomatis jika REST API ke database Golang *timeout* saat menyimpan puluhan ribu hasil prediksi.

---

## STRUKTUR FOLDER

```
forecast-service/
├── app.py # Entry point Flask, routing, scheduler
├── config.py # Konfigurasi (API backend Go, model path)
├── .env # Environment variables (BACKEND_API_URL, dll)
├── requirements.txt # Dependencies Python
├── modules/ # Logika forecasting per modul
│ ├── init.py
│ └── inventory/ # Modul stok barang
│ ├── init.py
│ ├── forecaster.py # Kelas InventoryForecaster (training, prediksi)
│ └── trainer.py # Fungsi untuk melatih semua pasangan (store, ingredient)
├── models/ # Tempat penyimpanan model hasil training (.joblib)
│ └── inventory/ # Khusus model stok barang
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
venv\Scriptsctivate
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
BACKEND_API_URL=http://localhost:8080/internal/forecast
INTERNAL_SERVICE_KEY=secret_key_dari_backend_golang
TRAINING_MAX_WORKERS=4

# Universal Forecast Scheduler Settings
FORECAST_MODE=scheduler
FORECAST_AFTER_CLOSE_SCHEDULER_MINUTES=60
FORECAST_24H_RUN_SCHEDULER_MINUTES=60
SCHEDULER_RETRAIN=false
```

- `BACKEND_API_URL`: URL backend internal Go (wajib menunjuk ke `/internal/forecast`)
- `INTERNAL_SERVICE_KEY`: Key keamanan komunikasi antar service.
- `FORECAST_MODE`: Jika di set `scheduler`, service otomatis melacak toko tutup dan menjalankan forecast. Jika `manual`, scheduler dimatikan.

### 2. Jalankan Service

```bash
python app.py
```

Service tersedia di `http://localhost:5000`.

### 3. Training Model Inventory (Async)
Memulai retrain inventory untuk satu store secara background:

```bash
curl -X POST http://localhost:5000/api/forecast/inventory/retrain \
  -H "Content-Type: application/json" \
  -H "X-Service-Key: $INTERNAL_SERVICE_KEY" \
  -d '{"store_id":"<store_id>","force":true}'
```

Response awal mengembalikan `task_id` dengan status `queued` atau `running`.

Pantau progress:

```bash
curl http://localhost:5000/api/forecast/inventory/retrain/status/<task_id> \
  -H "X-Service-Key: $INTERNAL_SERVICE_KEY"
```

Status: `queued` -> `running` -> `success` / `partial_success` / `failed`.

### 4. Forecasting
Gunakan endpoint `POST /api/forecast/inventory/preview` (atau `/save` untuk generate sekaligus menyimpan ke DB) dengan body JSON.

Parameter opsional `start_date` (format "YYYY-MM-DD") dapat ditambahkan jika Anda ingin memulai prediksi dari tanggal tertentu. Jika dikosongkan, prediksi akan mengambil patokan **hari ini** dan otomatis bergeser maju jika tipe peramalan adalah mingguan/bulanan (memulai hari Senin depan atau tanggal 1 bulan depan).

Contoh harian single ingredient (7 hari ke depan):

```bash
curl -X POST http://localhost:5000/api/forecast/inventory/preview   -H "Content-Type: application/json"   -H "X-Service-Key: <INTERNAL_SERVICE_KEY>"   -d '{
    "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
    "ingredient_id": "b98b5042-30b5-4dc7-80ce-7dbb4797c4c7",
    "horizon_label": "daily",
    "horizon_count": 7,
    "start_date": "2026-07-01"
  }'
```

Contoh harian semua ingredient dalam store, tanpa `ingredient_id`:

```bash
curl -X POST http://localhost:5000/api/forecast/inventory/save   -H "Content-Type: application/json"   -H "X-Service-Key: <INTERNAL_SERVICE_KEY>"   -d '{
    "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
    "horizon_label": "daily",
    "horizon_count": 30
  }'
```

Untuk `/save` tanpa `ingredient_id`, default-nya partial-tolerant. Jika sebagian ingredient ada di master tetapi belum punya histori stok, ingredient tersebut dilaporkan sebagai `warnings`/`skipped_ingredients`. Ingredient yang berhasil tetap disimpan sebagai satu `forecast_run`. Field `errors` hanya untuk kegagalan runtime yang benar-benar gagal. Gunakan `"allow_partial": false` jika ingin mode strict all-or-nothing.

Contoh mingguan (4 minggu ke depan):

```bash
curl -X POST http://localhost:5000/api/forecast/inventory/preview   -H "Content-Type: application/json"   -H "X-Service-Key: <INTERNAL_SERVICE_KEY>"   -d '{
    "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
    "ingredient_id": "b98b5042-30b5-4dc7-80ce-7dbb4797c4c7",
    "horizon_label": "weekly",
    "horizon_count": 4
  }'
```

Contoh bulanan (3 bulan ke depan):

```bash
curl -X POST http://localhost:5000/api/forecast/inventory/preview   -H "Content-Type: application/json"   -H "X-Service-Key: <INTERNAL_SERVICE_KEY>"   -d '{
    "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
    "ingredient_id": "b98b5042-30b5-4dc7-80ce-7dbb4797c4c7",
    "horizon_label": "monthly",
    "horizon_count": 3
  }'
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
      "confidence_score": 77.05,
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
- `model_confidence`: `confidence_score` dihitung dari komponen sMAPE (100 − sMAPE%) dan *bias penalty*; R² dan EV hanya masuk perhitungan jika ≥ 0.10 (bermakna). Level: `HIGH` (≥ 60), `MEDIUM` (≥ 40), `LOW` (< 40).
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
curl -X POST http://localhost:5000/api/inventory/save-all-forecasts   -H "Content-Type: application/json"   -H "X-Service-Key: <INTERNAL_SERVICE_KEY>"   -d '{"store_id":"b4e2f559-...","ingredient_id":"b98b5042-...","periods":4,"freq":"W"}'
```
Data akan masuk ke tabel forecast_runs dan forecast_results.


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
Pastikan virtual environment aktif (`venv\Scriptsctivate`), lalu jalankan `pip install -r requirements.txt`.

### Masalah Umum (Semua OS)

**FileNotFoundError: Model not found...**
Training dulu: `curl -X POST http://localhost:5000/api/forecast/inventory/retrain -H "X-Service-Key: $INTERNAL_SERVICE_KEY" -H "Content-Type: application/json" -d '{"store_id":"<store_id>","force":true}'`

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
- Progress training disimpan di memori: jika service restart, task lama tidak bisa dilacak dari endpoint status.
- Data otomatis dibersihkan sebelum training: *stockout* tersembunyi (zero streak > 3 hari) dan outlier ekstrem (z-score > 3.5) diganti NaN agar model tidak belajar dari data palsu.
- Confidence dihitung menggunakan metode komposit berbasis sMAPE dan *bias penalty* dari data *out-of-sample Cross-Validation*. R²/EV hanya diikutsertakan jika informatif (≥ 0.10), mengikuti *Cohen's guideline* untuk *effect size* minimal (Cohen, 1988; Hyndman & Koehler, 2006).
