package auth

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestServiceKeyMiddleware(t *testing.T) {
	tests := []struct {
		name           string
		expectedKey    string
		providedKey    string
		bearerKey      string
		expectedStatus int
	}{
		{name: "valid x service key", expectedKey: "secret", providedKey: "secret", expectedStatus: http.StatusOK},
		{name: "valid bearer service key", expectedKey: "secret", bearerKey: "secret", expectedStatus: http.StatusOK},
		{name: "invalid key", expectedKey: "secret", providedKey: "wrong", expectedStatus: http.StatusUnauthorized},
		{name: "missing backend config", expectedKey: "", providedKey: "secret", expectedStatus: http.StatusServiceUnavailable},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodGet, "/internal/forecast/orders", nil)
			if tt.providedKey != "" {
				req.Header.Set(ServiceKeyHeader, tt.providedKey)
			}
			if tt.bearerKey != "" {
				req.Header.Set("Authorization", "Bearer "+tt.bearerKey)
			}
			rr := httptest.NewRecorder()

			handler := ServiceKeyMiddleware(tt.expectedKey)(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.WriteHeader(http.StatusOK)
			}))
			handler.ServeHTTP(rr, req)

			if rr.Code != tt.expectedStatus {
				t.Fatalf("status = %d, want %d", rr.Code, tt.expectedStatus)
			}
		})
	}
}

func TestForecastServiceClaimsMiddleware(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/internal/forecast/orders", nil)
	rr := httptest.NewRecorder()

	handler := ForecastServiceClaimsMiddleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		claims, ok := ClaimsFromContext(r.Context())
		if !ok {
			t.Fatalf("claims not found in context")
		}
		if !IsSystemAdmin(claims) {
			t.Fatalf("internal forecast claims should be system admin")
		}
		w.WriteHeader(http.StatusOK)
	}))
	handler.ServeHTTP(rr, req)

	if rr.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d", rr.Code, http.StatusOK)
	}
}
