# Implementation Walkthrough - Backend Security Phase 2 + RoleID Hardening

## Tujuan
Hardening backend Go untuk multi-store security dengan gabungan perubahan Phase 2 dan koreksi RoleID fixed dari tabel `m_roles`.

Role sistem fixed:

- Admin  = `00000000-0000-0000-0000-000000000000`
- Owner  = `00000000-0000-0000-0000-000000000001`
- Member = `00000000-0000-0000-0000-000000000002`

## Perubahan Utama

1. JWT sekarang membawa `role_id`.
2. Admin sistem tidak lagi ditentukan dari `RoleName == "Admin"`, tetapi dari `RoleID == RoleIDAdmin`.
3. `m_role_access.name = Admin` tidak akan dianggap sebagai Admin sistem.
4. `/api/stores` sudah store-scoped untuk user non-admin.
5. `/api/orders` GetAll sudah store-scoped.
6. `forecast-results` bulk insert memvalidasi `forecast_runs.store_id` sebelum insert.
7. StoreMiddleware mewajibkan `store_id` untuk Owner/Member.
8. Swagger dan test route bisa dimatikan lewat env.
9. CORS production tidak fallback wildcard jika `ALLOWED_ORIGINS` kosong.
10. Endpoint forecast diberi body limit.

## File Penting yang Diubah

- `internal/auth/jwt.go`
- `internal/auth/roles.go`
- `internal/auth/store_middleware.go`
- `internal/auth/store_middleware_test.go`
- `internal/handler/user_handler.go`
- `internal/handler/forecast_prediction_handler.go`
- `internal/handler/forecast_run_handler.go`
- `internal/handler/forecast_result_handler.go`
- `internal/repository/store_repo.go`
- `internal/repository/order_repo.go`
- `internal/repository/forecast_result_repo.go`
- `internal/repository/forecast_result_repository.go`
- `internal/service/forecast_result_service.go`
- `cmd/api/routes.go`
- `.env.example`
- `migrations/20260618_security_hardening_indexes.sql`

## Testing

Jalankan di mesin lokal yang memakai Go versi sesuai `go.mod`:

```bash
cd backend
gofmt -w $(find . -name '*.go' -not -path './docs/*')
go test ./internal/auth/...
go test ./...
go build ./...
```

## Catatan Deployment

Setelah deploy perubahan ini, semua user disarankan logout/login ulang karena JWT lama belum membawa `role_id`.

Jangan deploy file `.env` dari local. Gunakan environment variable server/cloud.
