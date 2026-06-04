package handler

import (
    "encoding/json"
    "net/http"
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
    var input models.ForecastRunInput
    if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
        respondWithJSON(w, http.StatusBadRequest, map[string]string{"error": "Invalid JSON"})
        return
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