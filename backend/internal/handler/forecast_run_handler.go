package handler

import (
	"encoding/json"
	"net/http"
	"sora-finance-api/internal/auth"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/service"
)

type ForecastRunHandler struct {
	service *service.ForecastRunService
}

func NewForecastRunHandler(service *service.ForecastRunService) *ForecastRunHandler {
	return &ForecastRunHandler{service: service}
}

func (h *ForecastRunHandler) Create(w http.ResponseWriter, r *http.Request) {
	r.Body = http.MaxBytesReader(w, r.Body, 1<<20)
	var input models.ForecastRunInput
	if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
		respondWithJSON(w, http.StatusBadRequest, map[string]string{"error": "Invalid JSON"})
		return
	}

	claims, ok := auth.ClaimsFromContext(r.Context())
	if !ok {
		respondWithJSON(w, http.StatusUnauthorized, map[string]string{"error": "unauthorized"})
		return
	}

	if !auth.IsSystemAdmin(claims) {
		input.StoreID = claims.StoreID
	}

	id, err := h.service.Create(r.Context(), input)
	if err != nil {
		respondWithJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}

	respondWithJSON(w, http.StatusCreated, map[string]interface{}{
		"run_id": id,
		"status": "success",
	})
}
