# Modul Sales (Forecasting)

Modul `sales` di `forecast-service` bertanggung jawab untuk menghasilkan prediksi omzet penjualan (Sales / Revenue) di masa depan untuk masing-masing *store*. Modul ini beroperasi menggunakan model *Machine Learning* yang memproses data historis (penjualan harian, penjualan bulanan, pesanan, dan jam operasional) dan mengekstraksi metrik pola transaksi untuk menghasilkan _forecast_.

## Logika & Alur Modul Sales

1. **Pengumpulan Data Historis (Data Fetching)**: 
   API internal atau klien Golang menarik seluruh data dari backend utama untuk sebuah *store*, termasuk riwayat pesanan (*orders*), ringkasan penjualan, serta jadwal operasional toko (*operational hours*).
2. **Preprocessing**: 
   Data direkapitulasi menjadi frame data harian (atau periodik). Fitur tambahan atau _engineering_ diterapkan (seperti lag, _rolling window_, deteksi tren mingguan/bulanan, hari libur lokal).
3. **Training & Model Generation**: 
   Jika model belum ada atau data terindikasi lawas (_needs retrain_), modul secara otomatis (atau manual via API `/retrain`) memicu pelacakan metrik *omzet* untuk melatih (_train_) model *Gradient Boosting* atau *Tree-based model* lainnya (misalnya menggunakan fungsi di `trainer.py`).
4. **Resolusi _Start Date_ (Business Cutoff)**:
   Saat prediksi diminta, modul menggunakan `_resolve_forecast_start_meta` untuk menentukan _tanggal sebenarnya_ (Actual Start Date).
   - Apabila toko buka 24 jam dan waktu sekarang sudah lewat tengah malam (misal 01:00 AM), itu masih dihitung sebagai *hari bisnis sebelumnya*. Modul ini memastikan bahwa prediksi baru benar-benar dipotong dengan rapi di akhir jam kerja sebenarnya.
5. **Generasi _Forecast_ (Predict)**: 
   Secara berurutan *(autoregressive)*, model menyimulasikan hasil dari hari ke hari ke masa depan selama _horizon_ yang diminta (misal: 7 hari). Setiap prediksi baru dikonversi dan diagregasi kembali jika _request_ meminta wujud data Mingguan (`weekly`) atau Bulanan (`monthly`).
6. **Persistence**:
   Hasil prediksi beserta model *metadata* pendukungnya dapat disimpan kembali ke PostgreSQL atau Database Golang Backend menggunakan *endpoint* `/save` atau `/run`.

---

## Daftar API Endpoints

Semua endpoint untuk modul sales bersifat **POST** (kecuali health check secara umum) dan wajib mencantumkan `store_id` pada JSON _body_.

### 1. Preview Forecast (Harian)
**Endpoint**: `POST /api/forecast/sales/preview`
**Deskripsi**: Digunakan untuk mendapatkan prediksi sementara (tidak disimpan ke _database_). Ideal untuk kebutuhan tampilan _dashboard_.
**Contoh Body Request**:
```json
{
  "store_id": "store-12345",
  "forecast_days": 14,
  "start_date": "2023-11-01" // Opsional
}
```

### 2. Save Forecast (Manual)
**Endpoint**: `POST /api/forecast/sales/save`
**Deskripsi**: Digunakan untuk secara paksa menyimpan data _forecast_ hasil `preview` yang telah dieksekusi secara terpisah.
**Contoh Body Request**:
```json
{
  "backend_token": "token-rahasia-backend",
  "forecast": {
    "store_id": "store-12345",
    "forecast_horizon_days": 14,
    "forecasts": [...],
    "model_metadata": {...}
  }
}
```

### 3. Run Forecast (Generate & Save)
**Endpoint**: `POST /api/forecast/sales/run`
**Deskripsi**: Merupakan gabungan fungsi `preview` dan `save`. Men-generate forecast baru dan **langsung menyimpannya** ke dalam basis data backend.
**Contoh Body Request**:
```json
{
  "store_id": "store-12345",
  "forecast_days": 7,
  "backend_token": "token-rahasia-backend"
}
```

### 4. Retrain Model (Latih Ulang)
**Endpoint**: `POST /api/forecast/sales/retrain`
**Deskripsi**: Memerintahkan modul untuk melatih ulang (retrain) model *machine learning* untuk toko tertentu berdasarkan histori *omzet* terbaru.
**Contoh Body Request**:
```json
{
  "store_id": "store-12345",
  "force": true // Jika false, akan diskip jika model sudah 'fresh'
}
```

## Referensi Terkait Modul Sales
* Semua tipe keluaran (response schema) didefinisikan secara _type-safe_ lewat Pydantic (`ForecastResponse`, `WeeklyForecastResponse`, dll) dalam `forecaster.py`.
* Penyimpanan *state* model, *scaler*, dan *metadata* ditaruh secara lokal (atau bucket) untuk diload secara cepat oleh `trainer.py` tanpa *overhead* iterasi jaringan.
