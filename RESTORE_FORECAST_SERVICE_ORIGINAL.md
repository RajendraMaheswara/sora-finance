# Restore Forecast Service Original

Paket ini berisi `forecast-service` original dari ZIP awal project `sora-finance.zip` sebelum perubahan route preview/save/run, service key, dan wrapper forecast terbaru.

## Cara restore paling bersih

1. Matikan `forecast-service` jika sedang berjalan.
2. Backup folder lama jika masih ingin disimpan:

```powershell
Rename-Item "forecast-service" "forecast-service-backup"
```

3. Extract isi ZIP ini ke root project `sora-finance/` sehingga folder `forecast-service/` kembali muncul.
4. File `.env` tidak ikut dimasukkan agar konfigurasi lokal Anda tidak tertimpa. Jika perlu, copy dari `.env.example`.

## Catatan

- ZIP ini hanya mengembalikan `forecast-service`.
- Backend tidak ikut diubah.
- Folder `models/` original ikut disertakan agar perilaku forecast mendekati kondisi awal.
- Folder `__pycache__/` tidak disertakan karena hanya cache Python.
