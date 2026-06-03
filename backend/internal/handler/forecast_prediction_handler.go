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

type ForecastPredictionHandler struct {
	service *service.ForecastPredictionService
}

func NewForecastPredictionHandler(service *service.ForecastPredictionService) *ForecastPredictionHandler {
	return &ForecastPredictionHandler{service: service}
}

// Create godoc
// @Summary      Create forecast predictions
// @Description  Menyimpan hasil forecast ke tabel forecast_predictions
// @Tags         ForecastPredictions
// @Accept       json
// @Produce      json
// @Param        payload  body      []models.ForecastPredictionCreate  true  "Forecast predictions"
// @Success      201      {array}   models.ForecastPrediction
// @Failure      400      {object}  map[string]interface{}
// @Failure      500      {object}  map[string]interface{}
// @Router       /forecast-predictions [post]
func (h *ForecastPredictionHandler) Create(w http.ResponseWriter, r *http.Request) {
	payload, err := decodeForecastPredictionPayload(r)
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

func decodeForecastPredictionPayload(r *http.Request) ([]models.ForecastPredictionCreate, error) {
	body, err := io.ReadAll(r.Body)
	if err != nil {
		return nil, err
	}

	if len(body) == 0 {
		return nil, errors.New("empty body")
	}

	trimmed := strings.TrimSpace(string(body))
	if strings.HasPrefix(trimmed, "[") {
		var items []models.ForecastPredictionCreate
		if err := json.Unmarshal(body, &items); err != nil {
			return nil, err
		}
		return items, nil
	}

	var item models.ForecastPredictionCreate
	if err := json.Unmarshal(body, &item); err != nil {
		return nil, err
	}
	return []models.ForecastPredictionCreate{item}, nil
}
