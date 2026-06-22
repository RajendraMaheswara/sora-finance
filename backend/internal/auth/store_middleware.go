package auth

import (
	"net/http"
)

// StoreMiddleware ensures that the user is an Admin OR has a store_id in their JWT claims.
func StoreMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		claims, ok := ClaimsFromContext(r.Context())
		if !ok {
			writeAuthError(w, http.StatusUnauthorized, "unauthorized")
			return
		}

		if RequireStoreID(claims) {
			writeAuthError(w, http.StatusForbidden, "forbidden: store_id is required")
			return
		}

		next.ServeHTTP(w, r)
	})
}
