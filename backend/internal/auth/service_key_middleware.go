package auth

import (
	"context"
	"crypto/subtle"
	"net/http"
	"strings"
	"time"
)

const ServiceKeyHeader = "X-Service-Key"

// ServiceKeyMiddleware protects internal service-to-service endpoints.
// Forecast-service does not use JWT; it must send X-Service-Key that matches
// INTERNAL_SERVICE_KEY from the backend environment.
func ServiceKeyMiddleware(serviceKey string) func(http.Handler) http.Handler {
	expected := strings.TrimSpace(serviceKey)

	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if expected == "" {
				writeAuthError(w, http.StatusServiceUnavailable, "INTERNAL_SERVICE_KEY is not configured")
				return
			}

			provided := strings.TrimSpace(r.Header.Get(ServiceKeyHeader))
			if provided == "" || !constantTimeEqual(provided, expected) {
				writeAuthError(w, http.StatusUnauthorized, "invalid service key")
				return
			}

			next.ServeHTTP(w, r)
		})
	}
}

// ForecastServiceClaimsMiddleware injects system-admin claims for internal
// forecast-service requests. This preserves the old forecast-service behavior:
// historical GET endpoints can return the same broad dataset as before, while
// the route itself stays protected by X-Service-Key.
func ForecastServiceClaimsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		claims := &Claims{
			UserID:    "00000000-0000-0000-0000-000000000000",
			StoreID:   "",
			RoleID:    RoleIDAdmin,
			Username:  "forecast-service",
			Name:      "Forecast Service",
			RoleName:  "Admin",
			ExpiresAt: time.Now().Add(24 * time.Hour).Unix(),
		}
		ctx := context.WithValue(r.Context(), claimsContextKey, claims)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

func constantTimeEqual(a, b string) bool {
	if len(a) != len(b) {
		return false
	}
	return subtle.ConstantTimeCompare([]byte(a), []byte(b)) == 1
}
