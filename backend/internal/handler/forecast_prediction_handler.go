package handler

import (
	"encoding/json"
	"net/http"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/service"
)

type ForecastPredictionHandler struct {
	service *service.ForecastPredictionService
}

func NewForecastPredictionHandler(service *service.ForecastPredictionService) *ForecastPredictionHandler {
	return &ForecastPredictionHandler{service: service}
}

type bulkPredictionsRequest struct {
	Predictions []models.ForecastPredictionInput `json:"predictions"`
}

// Save godoc
// @Summary      Simpan hasil forecast
// @Description  Menerima array prediksi dari Python dan menyimpannya ke database
// @Tags         Forecast
// @Accept       json
// @Produce      json
// @Param        body  body      bulkPredictionsRequest  true  "Data prediksi"
// @Success      201   {object}  map[string]string
// @Failure      400   {object}  map[string]interface{}
// @Failure      500   {object}  map[string]interface{}
// @Router       /forecast-predictions [post]
func (h *ForecastPredictionHandler) Save(w http.ResponseWriter, r *http.Request) {
	var req bulkPredictionsRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondWithJSON(w, http.StatusBadRequest, map[string]string{"error": "Invalid JSON"})
		return
	}

	if err := h.service.SavePredictions(r.Context(), req.Predictions); err != nil {
		respondWithJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}

	respondWithJSON(w, http.StatusCreated, map[string]string{
		"status":  "success",
		"message": "Predictions saved",
	})
}