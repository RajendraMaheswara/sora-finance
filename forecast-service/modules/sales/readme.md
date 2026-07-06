# Modul Sales Forecasting

Modul ini bertanggung jawab untuk melakukan prediksi penjualan (*sales / omzet*) menggunakan algoritma *Random Forest* dengan *lag features* agregasi harian, mingguan, maupun bulanan. Modul ini terintegrasi langsung dengan PostgreSQL untuk menyimpan hasil prediksi.

## 🛠 Panduan Instalasi (Setelah Clone)

Untuk menjalankan modul ini secara lokal di komputermu, ikuti langkah-langkah berikut:

### 1. Masuk ke direktori `forecast-service`
Pastikan kamu berada di dalam direktori `forecast-service`.
```bash
cd sora-finance/forecast-service
```

### 2. Buat dan Aktifkan Virtual Environment
Sangat disarankan untuk menggunakan *virtual environment* agar tidak terjadi konflik *package*.
```bash
python3 -m venv venv
source venv/bin/activate  # Untuk Linux/MacOS
# .\venv\Scripts\activate # Untuk Windows
```

### 3. Install Dependencies
Install semua *library* Python yang dibutuhkan melalui `requirements.txt`.
```bash
pip install -r requirements.txt
```

### 4. Konfigurasi Environment Variables (`.env`)
Buat file bernama `.env` di dalam folder `forecast-service` (kamu bisa *copy* dari `.env.example` jika ada) dan isi dengan konfigurasi database kamu:
```env
# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_USER=your_db_username
DB_PASSWORD=your_db_password
DB_NAME=your_db_name
DB_SSLMODE=disable

# Backend URL (Opsional jika tidak dipakai untuk call API external)
BACKEND_API_URL=http://localhost:8080/api/v1
INTERNAL_SERVICE_KEY=your_secret_key
```

### 5. Jalankan Aplikasi (Flask Server)
Jalankan file `app.py` untuk menyalakan server lokal.
```bash
python app.py
```
Server akan berjalan secara *default* pada `http://localhost:5000`.

---

## 🌐 Daftar API Modul Sales

Berikut adalah daftar API yang tersedia pada modul `sales` (Base URL: `http://localhost:5000`):

### 1. **Run Forecast (Preview + Save)**
*   **Method:** `POST`
*   **Endpoint:** `/api/forecast/sales/save`
*   **Deskripsi:** Menjalankan prediksi penjualan (*sales*) berdasarkan data *history* yang ada, mengembalikan hasil *response* prediksi, dan otomatis menyimpannya ke database (`forecast_runs` & `forecast_results`).
*   **Payload (JSON):**
    ```json
    {
      "store_id": "47dad341-...",
      "horizon_label": "weekly",
      "horizon_count": 4,
      "start_date": "2026-07-02"
    }
    ```

### 2. **Preview Forecast (Tanpa Save)**
*   **Method:** `POST`
*   **Endpoint:** `/api/forecast/sales/preview`
*   **Deskripsi:** Hanya menjalankan prediksi dan mengembalikan *response* tanpa menyimpannya ke database.
*   **Payload (JSON):** *(Sama seperti endpoint /save)*

### 3. **Save Forecast**
*   **Method:** `POST`
*   **Endpoint:** `/api/forecast/sales/save`
*   **Deskripsi:** Menyimpan *response* hasil prediksi (dari endpoint preview) ke dalam database.
*   **Payload (JSON):**
    ```json
    {
      "forecast": {
        "store_id": "...",
        "forecasts": [...],
        "model_metadata": {...}
      }
    }
    ```

### 4. **Retrain Model (Single Store)**
*   **Method:** `POST`
*   **Endpoint:** `/api/forecast/sales/retrain`
*   **Deskripsi:** Memaksa modul untuk melatih ulang (*retrain*) model Machine Learning Random Forest untuk satu toko spesifik dengan mengambil data historis terbaru dari tabel database.
*   **Payload (JSON):**
    ```json
    {
      "store_id": "47dad341-..."
    }
    ```

### 5. **Batch Retrain Model (All Stores)**
*   **Method:** `POST`
*   **Endpoint:** `/api/forecast/sales/batch-retrain`
*   **Deskripsi:** Melatih ulang (*retrain*) model untuk semua toko secara serentak yang ada di database. Berguna untuk *maintenance* berkala.

### 6. **List Models**
*   **Method:** `GET`
*   **Endpoint:** `/api/forecast/sales/models`
*   **Deskripsi:** Menampilkan daftar direktori model *sales* yang tersimpan di dalam sistem file *local* server.

### 7. **Delete Model**
*   **Method:** `DELETE`
*   **Endpoint:** `/api/forecast/sales/models/<store_id>`
*   **Deskripsi:** Menghapus model *sales* milik `store_id` spesifik yang tersimpan di *local storage*.
