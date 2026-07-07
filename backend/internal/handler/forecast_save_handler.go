package handler

import (
	"encoding/json"
	"net/http"

	"sora-finance-api/internal/auth"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/service"
)

type ForecastSaveHandler struct {
	service *service.ForecastSaveService
}

func NewForecastSaveHandler(service *service.ForecastSaveService) *ForecastSaveHandler {
	return &ForecastSaveHandler{service: service}
}

func (h *ForecastSaveHandler) Save(w http.ResponseWriter, r *http.Request) {
	r.Body = http.MaxBytesReader(w, r.Body, 4<<20)
	var input models.ForecastSaveInput
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
		input.Run.StoreID = claims.StoreID
	}

	result, err := h.service.Save(r.Context(), input)
	if err != nil {
		respondForecastError(w, err)
		return
	}

	respondWithJSON(w, http.StatusCreated, map[string]interface{}{
		"status":  "success",
		"message": "forecast run and results saved atomically",
		"run_id":  result.RunID,
		"count":   result.Count,
	})
}
