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


PANDUAN RUN
Panduan Menjalankan Forecast Service (Inventory)
Prasyarat
Python 3.12 (wajib, karena Prophet butuh versi ini)

Terminal (shell) di folder forecast-service

File model .pkl yang sudah terlatih (ada di models/inventory/)
Pastikan folder models/inventory/ berisi file hasil training sebelumnya (contoh: model_storeb4e2f559..._ingrb98b5042...pkl). Jika belum ada, minta ke anggota tim yang sudah training atau lakukan training sekali saja.

1. Setup Virtual Environment (sekali saja)

cd forecast-service
python3.12 -m venv venv
source venv/bin/activate          # Linux/Mac
# venv\Scripts\activate          # Windows
pip install -r requirements.txt

2. Konfigurasi .env
Pastikan file .env berisi:
BACKEND_API_URL=http://localhost:8080/api
(Sesuaikan jika backend Go berjalan di host/port berbeda)

3. Jalankan Service
python app.py
Biarkan terminal tetap berjalan. Service tersedia di http://localhost:5000.

4. Akses Prediksi (Forecast)
Gunakan curl atau Postman untuk memanggil endpoint.
Contoh permintaan mingguan (1 minggu ke depan) untuk Vanilla Syrup:
curl -X POST http://localhost:5000/api/inventory/forecast \
  -H "Content-Type: application/json" \
  -d '{"store_id":"b4e2f559-9615-4263-84fe-9ee97780748f","ingredient_id":"b98b5042-30b5-4dc7-80ce-7dbb4797c4c7","periods":1,"freq":"W"}'
   
Contoh permintaan bulanan (1 bulan ke depan):
curl -X POST http://localhost:5000/api/inventory/forecast \
  -H "Content-Type: application/json" \
  -d '{"store_id":"b4e2f559-9615-4263-84fe-9ee97780748f","ingredient_id":"b98b5042-30b5-4dc7-80ce-7dbb4797c4c7","periods":1,"freq":"M"}'
  
6. Memahami Output
Respon berbentuk JSON seperti ini:
{
  "data": [
    {
      "ds": "Mon, 04 Jan 2027 00:00:00 GMT",
      "store_id": "b4e2f559-9615-4263-84fe-9ee97780748f",
      "ingredient_id": "b98b5042-30b5-4dc7-80ce-7dbb4797c4c7",
      "yhat": -0.8046689071900426,         // Prediksi rata-rata
      "yhat_lower": -6.732813396856777,    // Batas bawah (worst-case)
      "yhat_upper": 5.297820941020336      // Batas atas (best-case)
    }
  ],
  "status": "sukses",
  "pesan": "Forecast W untuk 1 periode ke depan"
}
yhat : nilai prediksi tengah (dalam satuan yang sama dengan data reduced, misal botol, kg, butir)

yhat_lower : batas bawah interval kepercayaan (skenario terendah)

yhat_upper : batas atas interval kepercayaan (skenario tertinggi)

Catatan: Hasil prediksi bisa negatif karena pola data banyak nol. Angka negatif bisa diinterpretasikan mendekati nol atau perlu perbaikan model di iterasi selanjutnya. Untuk saat ini fokus pada tren relatif dan rentang antara lower-upper.

6. Mengganti Bahan/Toko
Untuk mencoba prediksi bahan lain, ganti store_id dan ingredient_id dengan pasangan yang ada di models/inventory/ (lihat nama file).
Contoh:
curl -X POST ... -d '{"store_id":"...", "ingredient_id":"...", "periods":2, "freq":"W"}'
periods bisa diisi berapa minggu/bulan ke depan.

freq diisi W (mingguan) atau M (bulanan).

7. Catatan Penting
Tidak perlu training lagi jika model sudah ada. Training ulang hanya diperlukan jika data historis bertambah dan ingin memperbarui model (dijalankan manual via POST /api/inventory/train atau otomatis oleh scheduler setiap Minggu 02:00).

Service hanya sebagai jembatan; semua data tetap diambil dari API backend Go. Pastikan backend Go berjalan dan endpoint GET /api/ingredient-stock-histories dapat diakses.

Untuk keperluan pengembangan, gunakan flask run (development server). Untuk production, gunakan gunicorn atau waitress.

Troubleshooting Cepat
Masalah	Solusi
ModuleNotFoundError: No module named 'prophet'	pip install -r requirements.txt
FileNotFoundError: Model not found...	Jalankan training sekali: curl -X POST http://localhost:5000/api/inventory/train atau pastikan file .pkl ada di models/inventory/
ConnectionError saat forecast	Pastikan backend Go berjalan dan .env benar
Port 5000 sudah dipakai	Ganti port di app.py (baris terakhir app.run(port=5000))
