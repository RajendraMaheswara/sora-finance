package auth

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestStoreMiddleware(t *testing.T) {
	tests := []struct {
		name           string
		claims         *Claims
		expectedStatus int
	}{
		{
			name:           "No Claims in Context",
			claims:         nil,
			expectedStatus: http.StatusUnauthorized,
		},
		{
			name: "System Admin without StoreID is allowed",
			claims: &Claims{
				RoleID:   RoleIDAdmin,
				RoleName: "Admin",
				StoreID:  "",
			},
			expectedStatus: http.StatusOK,
		},
		{
			name: "RoleName Admin but RoleID Member is not system admin",
			claims: &Claims{
				RoleID:   RoleIDMember,
				RoleName: "Admin",
				StoreID:  "",
			},
			expectedStatus: http.StatusForbidden,
		},
		{
			name: "Old token with RoleName Admin but no RoleID is rejected without StoreID",
			claims: &Claims{
				RoleName: "Admin",
				StoreID:  "",
			},
			expectedStatus: http.StatusForbidden,
		},
		{
			name: "Owner without StoreID is rejected",
			claims: &Claims{
				RoleID:   RoleIDOwner,
				RoleName: "Owner",
				StoreID:  "",
			},
			expectedStatus: http.StatusForbidden,
		},
		{
			name: "Member with StoreID is allowed",
			claims: &Claims{
				RoleID:   RoleIDMember,
				RoleName: "Member",
				StoreID:  "some-uuid-1234",
			},
			expectedStatus: http.StatusOK,
		},
		{
			name: "Owner with StoreID is allowed",
			claims: &Claims{
				RoleID:   RoleIDOwner,
				RoleName: "Owner",
				StoreID:  "some-uuid-5678",
			},
			expectedStatus: http.StatusOK,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodGet, "/", nil)

			if tt.claims != nil {
				ctx := context.WithValue(req.Context(), claimsContextKey, tt.claims)
				req = req.WithContext(ctx)
			}

			rr := httptest.NewRecorder()
			handler := StoreMiddleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.WriteHeader(http.StatusOK)
			}))

			handler.ServeHTTP(rr, req)

			if rr.Code != tt.expectedStatus {
				t.Errorf("handler returned wrong status code: got %v want %v", rr.Code, tt.expectedStatus)
			}
		})
	}
}
