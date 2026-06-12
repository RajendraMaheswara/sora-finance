package handler

import (
	"encoding/json"
	"net/http"

	"sora-finance-api/internal/auth"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/service"
)

type AuthHandler struct {
	service *service.AuthService
}

func NewAuthHandler(service *service.AuthService) *AuthHandler {
	return &AuthHandler{service: service}
}

func (h *AuthHandler) Login(w http.ResponseWriter, r *http.Request) {
	var req models.LoginRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondWithJSON(w, http.StatusBadRequest, map[string]string{"error": "Invalid JSON"})
		return
	}

	res, err := h.service.Login(r.Context(), req)
	if err != nil {
		respondWithJSON(w, http.StatusUnauthorized, map[string]string{"error": err.Error()})
		return
	}

	respondWithJSON(w, http.StatusOK, res)
}

func (h *AuthHandler) Me(w http.ResponseWriter, r *http.Request) {
	claims, ok := auth.ClaimsFromContext(r.Context())
	if !ok {
		respondWithJSON(w, http.StatusUnauthorized, map[string]string{"error": "unauthorized"})
		return
	}
	respondWithJSON(w, http.StatusOK, claims)
}
