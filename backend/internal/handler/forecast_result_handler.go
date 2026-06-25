package handler

import (
	"encoding/json"
	"net/http"
	"strings"

	"sora-finance-api/internal/models"
	"sora-finance-api/internal/service"

	"github.com/go-chi/chi/v5"
)

type ForecastResultHandler struct {
	service *service.ForecastResultService
}

func NewForecastResultHandler(service *service.ForecastResultService) *ForecastResultHandler {
	return &ForecastResultHandler{service: service}
}

// GetAll godoc
// @Summary      Get all forecast results
// @Description  Mengembalikan daftar semua forecast results dari forecast_runs + forecast_results
// @Tags         Forecast
// @Produce      json
// @Success      200  {array}  models.ForecastResult
// @Failure      500  {object}  map[string]interface{}
// @Router       /forecast-results [get]
func (h *ForecastResultHandler) GetAll(w http.ResponseWriter, r *http.Request) {
	items, err := h.service.GetAll(r.Context())
	if err != nil {
		respondWithJSON(w, http.StatusInternalServerError, map[string]string{"error": "internal server error"})
		return
	}
	respondWithJSON(w, http.StatusOK, items)
}

// GetByID godoc
// @Summary      Get forecast result by ID
// @Description  Mengembalikan satu forecast result berdasarkan ID
// @Tags         Forecast
// @Produce      json
// @Param        id   path      string  true  "ID"
// @Success      200  {object}  models.ForecastResult
// @Failure      400  {object}  map[string]interface{}
// @Failure      404  {object}  map[string]interface{}
// @Router       /forecast-results/{id} [get]
func (h *ForecastResultHandler) GetByID(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	item, err := h.service.GetByID(r.Context(), id)
	if err != nil {
		respondForecastError(w, err)
		return
	}
	if item == nil {
		respondWithJSON(w, http.StatusNotFound, map[string]string{"error": "not found"})
		return
	}
	respondWithJSON(w, http.StatusOK, item)
}

func (h *ForecastResultHandler) GetLatestForecast(w http.ResponseWriter, r *http.Request) {
	forecastType := strings.ToLower(strings.TrimSpace(r.URL.Query().Get("forecast_type")))
	if forecastType == "" {
		forecastType = strings.ToLower(strings.TrimSpace(r.URL.Query().Get("module")))
	}
	if forecastType == "" {
		forecastType = "visitors"
	}

	horizonLabel := strings.ToLower(strings.TrimSpace(r.URL.Query().Get("horizon_label")))
	if horizonLabel == "" {
		horizonLabel = "daily"
	}

	storeID := strings.TrimSpace(r.URL.Query().Get("store_id"))
	result, err := h.service.GetLatestForecast(r.Context(), forecastType, horizonLabel, storeID)
	if err != nil {
		respondForecastError(w, err)
		return
	}
	if result == nil {
		respondWithJSON(w, http.StatusNotFound, map[string]string{"error": "latest forecast not found"})
		return
	}

	respondWithJSON(w, http.StatusOK, result)
}

func (h *ForecastResultHandler) GetLatestVisitors(w http.ResponseWriter, r *http.Request) {
	horizonLabel := strings.ToLower(strings.TrimSpace(r.URL.Query().Get("horizon_label")))
	if horizonLabel == "" {
		horizonLabel = "daily"
	}
	storeID := strings.TrimSpace(r.URL.Query().Get("store_id"))

	result, err := h.service.GetLatestVisitors(r.Context(), horizonLabel, storeID)
	if err != nil {
		respondForecastError(w, err)
		return
	}
	if result == nil {
		respondWithJSON(w, http.StatusNotFound, map[string]string{"error": "latest visitors forecast not found"})
		return
	}

	respondWithJSON(w, http.StatusOK, result)
}

type BulkResultRequest struct {
	RunID   int64                        `json:"run_id"`
	Results []models.ForecastResultInput `json:"results"`
}

func (h *ForecastResultHandler) BulkCreate(w http.ResponseWriter, r *http.Request) {
	r.Body = http.MaxBytesReader(w, r.Body, 1<<20)
	var req BulkResultRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondWithJSON(w, http.StatusBadRequest, map[string]string{"error": "Invalid JSON"})
		return
	}

	if err := h.service.BulkInsert(r.Context(), req.RunID, req.Results); err != nil {
		respondForecastError(w, err)
		return
	}

	respondWithJSON(w, http.StatusCreated, map[string]interface{}{
		"status":  "success",
		"message": "forecast results saved",
		"run_id":  req.RunID,
		"count":   len(req.Results),
	})
}
