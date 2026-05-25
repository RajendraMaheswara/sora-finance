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
  `success, data (metrics, forecast_summary, prediction_analysis, model_confidence, daily_forecast)`
- Confidence score dihitung dari MAPE (100 - MAPE), dengan level HIGH/MEDIUM/LOW
- Training dijalankan secara asinkron melalui endpoint `/api/inventory/train/start`
- Monitoring progress training via `/api/inventory/train/status/<task_id>`
- Metrik evaluasi (MAE, RMSE, MAPE) disimpan otomatis dalam file JSON setelah training
- Backward compatibility: endpoint `/api/inventory/train` tetap bisa dipakai (langsung async)
- Uji coba endpoint forecast berhasil mengembalikan struktur lengkap (daily_forecast, summary, analysis, confidence)
- Response sudah sesuai untuk konsumsi dashboard; field metrics dan confidence akan terisi setelah retrain dengan kode terbaru

## KENDALA / KEKURANGAN

### 21 Mei 2026
- Hasil prediksi bisa negatif karena banyak data nol (intermittent)
- Belum menggunakan batasan nilai minimal (floor=0) pada Prophet
- Belum tuning parameter untuk data jarang (intermittent demand)
- Training masih dilakukan satu per satu (belum paralel)
- Belum ada endpoint untuk evaluasi akurasi model (cross-val metrics)
- Filter tanggal di API masih manual (belum difilter di server)
- Opsi 'libur toko' masih placeholder (default 0)

### 25 Mei 2026
- Model yang dilatih sebelum revisi kode (21 Mei) tidak memiliki file metrics, sehingga metrics menjadi null dan confidence menjadi UNKNOWN – solusi: retrain dengan kode terbaru
- Nilai negatif pada predicted_usage masih muncul, perlu penanganan di dashboard (floor ke 0) atau perbaikan model di iterasi berikutnya
- Confidence sangat bergantung pada MAPE; pada data noise tinggi, confidence bisa rendah (wajar)
- Metrik R² dan explained variance belum dihitung (masih null)
- Belum ada fitur auto‑clean model usang / tidak terpakai
- Progress training disimpan di memori (hilang jika service restart)

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

## PANDUAN MENJALANKAN SERVICE

### Prasyarat
- **Python 3.12** (wajib, karena Prophet membutuhkan versi ini)
- Terminal di dalam folder `forecast-service`
- File model `.pkl` yang sudah terlatih (ada di `models/inventory/`)  
  *Jika belum ada, lakukan training sekali dengan endpoint async di bawah.*

### 1. Setup Virtual Environment (sekali saja)
```bash
cd forecast-service
python3.12 -m venv venv
source venv/bin/activate          # Linux/Mac
# venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

### 2. Konfigurasi .env
Pastikan file .env berisi:
```
BACKEND_API_URL=http://localhost:8080/api
```
(Sesuaikan jika backend Go berjalan di host/port berbeda)

### 3. Jalankan Service
```
python app.py
```
Service tersedia di http://localhost:5000.

### 4. Training Model (Async)
Untuk memulai training semua pasangan toko-bahan secara asynchronous:
```
curl -X POST http://localhost:5000/api/inventory/train/start
```
Response:
```
{
  "task_id": "uuid-string",
  "message": "Training dimulai. Pantau progress di /api/inventory/train/status/<task_id>"
}
```
Pantau progress:
```
curl http://localhost:5000/api/inventory/train/status/<task_id>
```
Status akan berubah: STARTING → RUNNING → DONE (atau ERROR).

Alternatif (backward compatible):
```
curl -X POST http://localhost:5000/api/inventory/train
```
(Fungsi sama, langsung async dengan task_id baru)

### 5. Forecasting
Gunakan endpoint POST /api/inventory/forecast dengan body JSON.

Contoh request mingguan (1 minggu ke depan):
```
curl -X POST http://localhost:5000/api/inventory/forecast \
  -H "Content-Type: application/json" \
  -d '{"store_id":"b4e2f559-9615-4263-84fe-9ee97780748f","ingredient_id":"b98b5042-30b5-4dc7-80ce-7dbb4797c4c7","periods":1,"freq":"W"}'
```
Contoh request bulanan (1 bulan ke depan):
```
curl -X POST http://localhost:5000/api/inventory/forecast \
  -H "Content-Type: application/json" \
  -d '{"store_id":"b4e2f559-9615-4263-84fe-9ee97780748f","ingredient_id":"b98b5042-30b5-4dc7-80ce-7dbb4797c4c7","periods":1,"freq":"M"}'
```

### 6. Memahami Output
Response mengikuti format yang seragam dengan modul visitor/sales:
```
{
  "success": true,
  "message": "Forecast W untuk 1 periode ke depan",
  "data": {
    "store_id": "...",
    "ingredient_id": "...",
    "metrics": {
      "mae": 1.23,
      "rmse": 1.68,
      "mape": 12.5,
      "r2_score": null,
      "explained_variance": null
    },
    "forecast_summary": {
      "total_predicted_usage_next_7_days": 8.5,
      "average_daily_usage_next_7_days": 1.21
    },
    "prediction_analysis": {
      "highest_prediction_day": "2027-01-05",
      "highest_prediction_value": 2.4,
      "lowest_prediction_day": "2027-01-01",
      "lowest_prediction_value": 0.1
    },
    "model_confidence": {
      "confidence_score": 87.5,
      "confidence_level": "HIGH"
    },
    "daily_forecast": [
      {
        "date": "2027-01-01",
        "predicted_usage": 0.5,
        "lower_bound": 0.0,
        "upper_bound": 1.2
      },
      ...
    ]
  }
}
```

- metrics: metrik evaluasi model dari cross‑validation (jika tersedia)
- forecast_summary: total dan rata‑rata pemakaian selama periode yang diminta
- prediction_analysis: hari dengan prediksi tertinggi/terendah
- model_confidence: skor kepercayaan berdasarkan 100 - MAPE; level HIGH (≥85), MEDIUM (≥70), LOW (<70)
- daily_forecast: array prediksi harian lengkap (7 atau 30 hari sesuai freq)

### 7. Mengganti Bahan/Toko
Ganti store_id dan ingredient_id dengan pasangan yang ada di models/inventory/ (lihat nama file).
periods bisa diisi jumlah minggu/bulan ke depan. freq diisi W (mingguan) atau M (bulanan).

### CATATAN PENTING
- Training ulang hanya diperlukan jika data historis bertambah. Scheduler otomatis berjalan tiap Minggu pukul 02:00.
- Semua data diambil dari API backend Go. Pastikan endpoint GET /api/ingredient-stock-histories dapat diakses.
- Untuk production, gunakan WSGI server seperti gunicorn atau waitress, jangan mengandalkan server development Flask.
- Progress training disimpan di memori – jika service restart, task lama tidak bisa dilacak.

## TROUBLESHOOTING CEPAT

- **ModuleNotFoundError: No module named 'prophet'**  
  Jalankan `pip install -r requirements.txt`

- **FileNotFoundError: Model not found...**  
  Training dulu: `curl -X POST http://localhost:5000/api/inventory/train/start`

- **ConnectionError saat forecast**  
  Pastikan backend Go berjalan dan file `.env` sudah benar

- **Port 5000 sudah dipakai**  
  Ganti port di `app.py` (baris terakhir `app.run(port=5000)`)

- **Training tidak kunjung selesai**  
  Cek log Flask, mungkin ada error koneksi ke backend Go. Pastikan data tersedia.
