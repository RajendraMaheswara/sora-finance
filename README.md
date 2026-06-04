# Sora Finance

Sora Finance adalah project aplikasi keuangan yang terdiri dari:

* Frontend Flutter
* Backend Golang
* Forecast Service Python

---

# Project Structure

```text
sora-finance/
│
├── frontend/           # Flutter App
├── backend/            # Golang API
├── forecast-service/   # Python Forecast Service
```

---

# Requirements

Pastikan sudah menginstall:

## Frontend

* Flutter SDK
* Dart SDK
* Android Studio / VS Code
* Android SDK

## Backend

* Golang
* PostgreSQL

## Forecast Service

* Python 3.x
* pip

---

# Clone Repository

```bash
git clone https://github.com/RajendraMaheswara/sora-finance.git
```

Masuk ke folder project:

```bash
cd sora-finance
```

---

# FRONTEND SETUP (Flutter)

Masuk ke folder frontend:

```bash
cd frontend
```

## Install Dependencies

```bash
flutter pub get
```

## Clean Project (Opsional)

Jika terjadi error:

```bash
flutter clean
flutter pub get
```

## Run Flutter App

```bash
flutter run
```

## Run di Chrome

```bash
flutter run -d chrome
```

## Cek Device

```bash
flutter devices
```

---

# BACKEND SETUP (Golang)

Masuk ke folder backend:

```bash
cd backend
```

## Install Dependencies

```bash
go mod tidy
```

## Setup Environment

Buat file `.env`:

```env
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your_password
DB_NAME=sora_finance
DB_SSLMODE=disable
PORT=8080
```

## Run Backend

```bash
go run main.go
```

Jika menggunakan folder cmd:

```bash
go run cmd/api/main.go
```

---

# FORECAST SERVICE SETUP (Python)

Masuk ke folder forecast-service:

```bash
cd forecast-service
```

## Install Dependencies

```bash
pip install -r requirements.txt
```

Jika belum ada `requirements.txt`:

```bash
pip install flask pandas numpy scikit-learn
```

## Run Service

```bash
python app.py
```

---

# Common Commands

## Flutter

```bash
flutter clean
flutter pub get
flutter run
```

## Golang

```bash
go mod tidy
go run main.go
```

## Python

```bash
pip install -r requirements.txt
python app.py
```

---

# Common Errors

## Flutter Dependency Error

```bash
flutter clean
flutter pub get
```

## PostgreSQL Connection Error

Pastikan:

* PostgreSQL aktif
* Username dan password benar
* Database sudah dibuat
* `.env` sudah sesuai

## Go Module Error

```bash
go mod tidy
```

## Python Module Not Found

```bash
pip install -r requirements.txt
```

---

# Notes

* Jangan upload file `.env` ke GitHub
* Tambahkan `.env` ke `.gitignore`
* Gunakan versi Flutter terbaru
* Pastikan PostgreSQL berjalan sebelum backend dijalankan

---

# Tech Stack

## Frontend

* Flutter
* Provider
* HTTP
* Google Fonts

## Backend

* Golang
* PostgreSQL

## Forecast Service

* Python
* Flask
* Machine Learning
