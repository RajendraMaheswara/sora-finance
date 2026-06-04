package handler

import (
    "encoding/json"
    "net/http"
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
// @Description  Mengembalikan daftar semua forecast results
// @Tags         Forecast
// @Produce      json
// @Success      200  {array}  models.ForecastResult
// @Failure      500  {object}  map[string]interface{}
// @Router       /forecast-results [get]
func (h *ForecastResultHandler) GetAll(w http.ResponseWriter, r *http.Request) {
    items, err := h.service.GetAll(r.Context())
    if err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
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
        http.Error(w, err.Error(), http.StatusBadRequest)
        return
    }
    if item == nil {
        http.Error(w, "not found", http.StatusNotFound)
        return
    }
    respondWithJSON(w, http.StatusOK, item)
}

type BulkResultRequest struct {
    RunID   int64                        `json:"run_id"`
    Results []models.ForecastResultInput `json:"results"`
}

func (h *ForecastResultHandler) BulkCreate(w http.ResponseWriter, r *http.Request) {
    var req BulkResultRequest
    if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
        respondWithJSON(w, http.StatusBadRequest, map[string]string{"error": "Invalid JSON"})
        return
    }

    if err := h.service.BulkInsert(r.Context(), req.RunID, req.Results); err != nil {
        respondWithJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
        return
    }

    respondWithJSON(w, http.StatusCreated, map[string]interface{}{
        "status":  "success",
        "message": "Results saved",
        "count":   len(req.Results),
    })
}