package handler

import (
    "encoding/json"
    "net/http"
    "sora-finance-api/internal/models"
    "sora-finance-api/internal/service"
)

type ForecastResultHandler struct {
    service *service.ForecastResultService
}

func NewForecastResultHandler(service *service.ForecastResultService) *ForecastResultHandler {
    return &ForecastResultHandler{service: service}
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