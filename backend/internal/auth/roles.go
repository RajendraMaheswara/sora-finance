package auth

import "strings"

const (
	// Role IDs fixed dari tabel public.m_roles.
	// Jangan gunakan RoleName untuk keputusan security karena m_role_access
	// bisa juga punya nama seperti "Admin" di level toko.
	RoleIDAdmin  = "00000000-0000-0000-0000-000000000000"
	RoleIDOwner  = "00000000-0000-0000-0000-000000000001"
	RoleIDMember = "00000000-0000-0000-0000-000000000002"
)

func normalizedRoleID(claims *Claims) string {
	if claims == nil {
		return ""
	}
	return strings.TrimSpace(claims.RoleID)
}

// IsSystemAdmin true hanya untuk Admin sistem dari tabel m_roles.
func IsSystemAdmin(claims *Claims) bool {
	return normalizedRoleID(claims) == RoleIDAdmin
}

// IsAdmin dipertahankan agar call site lama tetap kompatibel.
// Logic-nya tetap memakai RoleID, bukan RoleName.
func IsAdmin(claims *Claims) bool {
	return IsSystemAdmin(claims)
}

func IsOwner(claims *Claims) bool {
	return normalizedRoleID(claims) == RoleIDOwner
}

func IsMember(claims *Claims) bool {
	return normalizedRoleID(claims) == RoleIDMember
}

// RequireStoreID true jika user bukan Admin sistem dan store_id kosong.
func RequireStoreID(claims *Claims) bool {
	return claims != nil && !IsSystemAdmin(claims) && strings.TrimSpace(claims.StoreID) == ""
}
