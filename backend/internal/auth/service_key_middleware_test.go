package auth

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestServiceKeyMiddleware(t *testing.T) {
	tests := []struct {
		name           string
		configuredKey  string
		providedKey    string
		expectedStatus int
	}{
		{"missing configured service key returns unavailable", "", "secret", http.StatusServiceUnavailable},
		{"missing header returns unauthorized", "secret", "", http.StatusUnauthorized},
		{"wrong key returns unauthorized", "secret", "wrong", http.StatusUnauthorized},
		{"valid key is allowed", "secret", "secret", http.StatusOK},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodGet, "/internal/forecast/stores", nil)
			if tt.providedKey != "" {
				req.Header.Set(ServiceKeyHeader, tt.providedKey)
			}

			rr := httptest.NewRecorder()
			handler := ServiceKeyMiddleware(tt.configuredKey)(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.WriteHeader(http.StatusOK)
			}))

			handler.ServeHTTP(rr, req)
			if rr.Code != tt.expectedStatus {
				t.Fatalf("wrong status: got %d want %d", rr.Code, tt.expectedStatus)
			}
		})
	}
}

func TestForecastStoreScopeMiddleware(t *testing.T) {
	tests := []struct {
		name           string
		method         string
		path           string
		body           string
		headerStoreID  string
		expectedStatus int
		expectedStore  string
	}{
		{
			name:           "store id from header",
			method:         http.MethodGet,
			path:           "/internal/forecast/orders",
			headerStoreID:  "b4e2f559-9615-4263-84fe-9ee97780748f",
			expectedStatus: http.StatusOK,
			expectedStore:  "b4e2f559-9615-4263-84fe-9ee97780748f",
		},
		{
			name:           "store id from query",
			method:         http.MethodGet,
			path:           "/internal/forecast/orders?store_id=7acfd0aa-254e-4c71-9f86-fc2b5213d7f5",
			expectedStatus: http.StatusOK,
			expectedStore:  "7acfd0aa-254e-4c71-9f86-fc2b5213d7f5",
		},
		{
			name:           "store id from json body",
			method:         http.MethodPost,
			path:           "/internal/forecast/forecast-runs",
			body:           `{"store_id":"b4e2f559-9615-4263-84fe-9ee97780748f"}`,
			expectedStatus: http.StatusOK,
			expectedStore:  "b4e2f559-9615-4263-84fe-9ee97780748f",
		},
		{
			name:           "missing store id",
			method:         http.MethodGet,
			path:           "/internal/forecast/orders",
			expectedStatus: http.StatusBadRequest,
		},
		{
			name:           "invalid store id",
			method:         http.MethodGet,
			path:           "/internal/forecast/orders?store_id=not-a-uuid",
			expectedStatus: http.StatusBadRequest,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest(tt.method, tt.path, strings.NewReader(tt.body))
			if tt.body != "" {
				req.Header.Set("Content-Type", "application/json")
			}
			if tt.headerStoreID != "" {
				req.Header.Set(StoreIDHeader, tt.headerStoreID)
			}

			rr := httptest.NewRecorder()
			handler := ForecastStoreScopeMiddleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				claims, ok := ClaimsFromContext(r.Context())
				if !ok || IsSystemAdmin(claims) || claims.StoreID != tt.expectedStore {
					w.WriteHeader(http.StatusInternalServerError)
					return
				}
				w.WriteHeader(http.StatusOK)
			}))

			handler.ServeHTTP(rr, req)
			if rr.Code != tt.expectedStatus {
				t.Fatalf("wrong status: got %d want %d", rr.Code, tt.expectedStatus)
			}
		})
	}
}
