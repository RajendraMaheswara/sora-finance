package auth

import (
	"bytes"
	"context"
	"crypto/subtle"
	"encoding/json"
	"io"
	"net/http"
	"strings"

	"github.com/google/uuid"
)

const (
	ServiceKeyHeader = "X-Service-Key"
	StoreIDHeader    = "X-Store-ID"
)

// ServiceKeyMiddleware protects internal machine-to-machine endpoints.
// It accepts only requests that include X-Service-Key matching INTERNAL_SERVICE_KEY.
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

// ForecastStoreScopeMiddleware requires a store_id for internal forecast routes.
// It injects non-admin service claims with that store_id so existing repository
// store-scoping remains active and /internal/forecast cannot accidentally read
// all stores. The store ID can be supplied as X-Store-ID header, store_id query,
// m_store_id query, or JSON body field store_id/m_store_id.
func ForecastStoreScopeMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		storeID, err := extractStoreIDFromRequest(r)
		if err != nil {
			writeAuthError(w, http.StatusBadRequest, err.Error())
			return
		}
		if storeID == "" {
			writeAuthError(w, http.StatusBadRequest, "store_id is required for internal forecast route")
			return
		}

		if _, err := uuid.Parse(storeID); err != nil {
			writeAuthError(w, http.StatusBadRequest, "store_id must be a valid UUID")
			return
		}

		claims := &Claims{
			UserID:   "00000000-0000-0000-0000-000000000000",
			StoreID:  storeID,
			RoleID:   RoleIDOwner,
			Username: "forecast-service",
			Name:     "Forecast Service",
			RoleName: "Owner",
		}

		ctx := context.WithValue(r.Context(), claimsContextKey, claims)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

func extractStoreIDFromRequest(r *http.Request) (string, error) {
	if value := strings.TrimSpace(r.Header.Get(StoreIDHeader)); value != "" {
		return value, nil
	}
	if value := strings.TrimSpace(r.URL.Query().Get("store_id")); value != "" {
		return value, nil
	}
	if value := strings.TrimSpace(r.URL.Query().Get("m_store_id")); value != "" {
		return value, nil
	}

	if r.Body == nil || r.Body == http.NoBody {
		return "", nil
	}

	body, err := io.ReadAll(r.Body)
	if err != nil {
		return "", err
	}
	r.Body = io.NopCloser(bytes.NewReader(body))
	if len(bytes.TrimSpace(body)) == 0 {
		return "", nil
	}

	var payload map[string]interface{}
	if err := json.Unmarshal(body, &payload); err != nil {
		// Let the handler return the normal invalid JSON response later.
		return "", nil
	}

	for _, key := range []string{"store_id", "m_store_id"} {
		if value, ok := payload[key].(string); ok && strings.TrimSpace(value) != "" {
			return strings.TrimSpace(value), nil
		}
	}

	// save-all style payloads can wrap forecast data inside forecast/data.
	for _, key := range []string{"forecast", "data"} {
		if nested, ok := payload[key].(map[string]interface{}); ok {
			for _, nestedKey := range []string{"store_id", "m_store_id"} {
				if value, ok := nested[nestedKey].(string); ok && strings.TrimSpace(value) != "" {
					return strings.TrimSpace(value), nil
				}
			}
		}
	}

	return "", nil
}

func constantTimeEqual(a, b string) bool {
	if len(a) != len(b) {
		return false
	}
	return subtle.ConstantTimeCompare([]byte(a), []byte(b)) == 1
}
