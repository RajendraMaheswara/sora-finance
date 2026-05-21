feat: Modul Forecasting Stok Barang dengan Prophet

PROGRESS:
- Integrasi forecast-service (Python/Flask) ke backend Go via API
- Training model Prophet per pasangan (store, ingredient)
- Data historis diambil dari endpoint GET /api/ingredient-stock-histories
- Agregasi harian SUM(reduced) dengan pengisian 0 untuk hari kosong
- Support fitur weekend, hari libur nasional (holidays Indonesia)
- Endpoint forecast: POST /api/inventory/forecast (mingguan/bulanan)
- Auto-training scheduler tiap Minggu jam 2 pagi
- Model disimpan sebagai .pkl di models/inventory/

KENDALA / KEKURANGAN:
- Hasil prediksi bisa negatif karena banyak data nol (intermittent)
- Belum menggunakan batasan nilai minimal (floor=0) pada Prophet
- Belum tuning parameter untuk data jarang (intermittent demand)
- Training masih dilakukan satu per satu (belum paralel)
- Belum ada endpoint untuk evaluasi akurasi model (cross-val metrics)
- Filter tanggal di API masih manual (belum difilter di server)
- Opsi 'libur toko' masih placeholder (default 0)

PANDUAN FOLDER:
forecast-service/
├── app.py                     # Entry point Flask, routing, scheduler
├── config.py                  # Konfigurasi (API backend Go, model path)
├── .env                       # Environment variables (BACKEND_API_URL)
├── requirements.txt           # Dependencies Python
├── modules/                   # Logika forecasting per modul
│   ├── __init__.py
│   └── inventory/             # Modul stok barang
│       ├── __init__.py
│       ├── forecaster.py      # Kelas InventoryForecaster (training, prediksi)
│       └── trainer.py         # Fungsi untuk melatih semua pasangan (store, ingredient)
├── models/                    # Tempat penyimpanan model hasil training (.pkl)
│   └── inventory/             # Khusus model stok barang
