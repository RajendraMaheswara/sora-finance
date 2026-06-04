package handler

import (
	"encoding/json"
	"net/http"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/service"

	"github.com/go-chi/chi/v5"
)

type ForecastPredictionHandler struct {
	service *service.ForecastPredictionService
}

func NewForecastPredictionHandler(service *service.ForecastPredictionService) *ForecastPredictionHandler {
	return &ForecastPredictionHandler{service: service}
}

// GetAll godoc
// @Summary      Get all forecast predictions
// @Description  Mengembalikan daftar semua forecast predictions
// @Tags         Forecast
// @Produce      json
// @Success      200  {array}  models.ForecastPrediction
// @Failure      500  {object}  map[string]interface{}
// @Router       /forecast-predictions [get]
func (h *ForecastPredictionHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	items, err := h.service.GetAll(r.Context())
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	respondWithJSON(w, http.StatusOK, items)
}

// GetByID godoc
// @Summary      Get forecast prediction by ID
// @Description  Mengembalikan satu forecast prediction berdasarkan ID
// @Tags         Forecast
// @Produce      json
// @Param        id   path      string  true  "ID"
// @Success      200  {object}  models.ForecastPrediction
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /forecast-predictions/{id} [get]
func (h *ForecastPredictionHandler) GetByID(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	item, err := h.service.GetByID(r.Context(), id)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	if item == nil {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}
	respondWithJSON(w, http.StatusOK, item)
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