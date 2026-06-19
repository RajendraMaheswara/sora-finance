# Restore Safe: Backend Phase 2 Hotfix + Forecast API Standard

ZIP ini dibuat untuk memperbaiki kasus saat ZIP `forecast-api-standard.zip` tidak sengaja menimpa folder backend dengan snapshot backend lama.

Isi ZIP:
- `backend/` = versi backend Phase 2 + RoleID Hardening + hotfix store/logout yang sudah compile di lokal user sebelumnya.
- `forecast-service/` = route forecast standard terbaru.

Cara pakai:
1. Backup folder project Anda terlebih dahulu.
2. Extract ZIP ini ke root project `sora-finance/` sehingga folder `backend/` dan `forecast-service/` tertimpa versi aman.
3. Pastikan `.env` lokal Anda tetap disimpan/di-restore karena ZIP ini tidak membawa `.env`.
4. Jalankan test backend:

```powershell
cd backend
$files = Get-ChildItem -Recurse -Filter *.go | Where-Object { $_.FullName -notlike "*\docs\*" }
gofmt -w $files.FullName
go test ./internal/auth/...
go test ./...
go build ./...
```

5. Jalankan syntax check forecast-service:

```powershell
cd ..\forecast-service
python -m py_compile app.py config.py modules/sales/forecaster.py modules/inventory/forecaster.py modules/inventory/trainer.py modules/visitors/forecaster.py modules/visitors/trainer.py
```

Catatan:
- Jangan extract `forecast-api-standard.zip` lama secara penuh ke root project karena di dalamnya ada snapshot backend lama.
- Untuk update route forecast, cukup pakai ZIP restore-safe ini atau ambil folder `forecast-service/` saja.
