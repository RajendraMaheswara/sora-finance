package handler

import (
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"strings"

	"sora-finance-api/internal/models"
	"sora-finance-api/internal/service"
)

type ForecastResultHandler struct {
	service *service.ForecastResultService
}

func NewForecastResultHandler(service *service.ForecastResultService) *ForecastResultHandler {
	return &ForecastResultHandler{service: service}
}

// Create godoc
// @Summary      Create forecast results
// @Description  Menyimpan hasil forecast ke tabel forecast_results
// @Tags         ForecastResults
// @Accept       json
// @Produce      json
// @Param        payload  body      []models.ForecastResultCreate  true  "Forecast results"
// @Success      201      {array}   models.ForecastResult
// @Failure      400      {object}  map[string]interface{}
// @Failure      500      {object}  map[string]interface{}
// @Router       /forecast-results [post]
func (h *ForecastResultHandler) Create(w http.ResponseWriter, r *http.Request) {
	payload, err := decodeForecastResultPayload(r)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	created, err := h.service.Create(r.Context(), payload)
	if err != nil {
		if errors.Is(err, service.ErrInvalidInput) {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	respondWithJSON(w, http.StatusCreated, created)
}

func decodeForecastResultPayload(r *http.Request) ([]models.ForecastResultCreate, error) {
	body, err := io.ReadAll(r.Body)
	if err != nil {
		return nil, err
	}

	if len(body) == 0 {
		return nil, errors.New("empty body")
	}

	trimmed := strings.TrimSpace(string(body))
	if strings.HasPrefix(trimmed, "[") {
		var items []models.ForecastResultCreate
		if err := json.Unmarshal(body, &items); err != nil {
			return nil, err
		}
		return items, nil
	}

	var item models.ForecastResultCreate
	if err := json.Unmarshal(body, &item); err != nil {
		return nil, err
	}
	return []models.ForecastResultCreate{item}, nil
}
