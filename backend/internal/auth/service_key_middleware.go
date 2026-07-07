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
// Forecast-service does not use JWT; it must send X-Service-Key or
// Authorization: Bearer <key> that matches INTERNAL_SERVICE_KEY from the backend environment.
func ServiceKeyMiddleware(serviceKey string) func(http.Handler) http.Handler {
	expected := strings.TrimSpace(serviceKey)

	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if expected == "" {
				writeAuthError(w, http.StatusServiceUnavailable, "INTERNAL_SERVICE_KEY is not configured")
				return
			}

			provided := serviceKeyFromRequest(r)
			if provided == "" || !constantTimeEqual(provided, expected) {
				writeAuthError(w, http.StatusUnauthorized, "invalid service key")
				return
			}

			next.ServeHTTP(w, r)
		})
	}
}

// ForecastServiceClaimsMiddleware injects system-level claims for internal
// forecast-service requests. Existing repository scoping uses the system-admin
// role ID as the only bypass for store filtering; this is not a user-facing
// admin login path. The route itself stays protected by INTERNAL_SERVICE_KEY.
func ForecastServiceClaimsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		claims := &Claims{
			UserID:    "00000000-0000-0000-0000-000000000000",
			StoreID:   "",
			RoleID:    RoleIDAdmin,
			Username:  "forecast-service",
			Name:      "Forecast Service",
			RoleName:  "Internal Service",
			ExpiresAt: time.Now().Add(24 * time.Hour).Unix(),
		}
		ctx := context.WithValue(r.Context(), claimsContextKey, claims)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

func serviceKeyFromRequest(r *http.Request) string {
	provided := strings.TrimSpace(r.Header.Get(ServiceKeyHeader))
	if provided != "" {
		return provided
	}

	authHeader := strings.TrimSpace(r.Header.Get("Authorization"))
	if strings.HasPrefix(strings.ToLower(authHeader), "bearer ") {
		return strings.TrimSpace(authHeader[len("Bearer "):])
	}
	return ""
}

func constantTimeEqual(a, b string) bool {
	if len(a) != len(b) {
		return false
	}
	return subtle.ConstantTimeCompare([]byte(a), []byte(b)) == 1
}
