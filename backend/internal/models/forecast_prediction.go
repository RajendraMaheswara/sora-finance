package models

import (
	"time"

	"github.com/google/uuid"
)

// ForecastPrediction sesuai tabel forecast_predictions
type ForecastPrediction struct {
	ID             uuid.UUID `json:"id"`
	StoreID        string    `json:"store_id"`
	Module         string    `json:"module"`
	HorizonLabel   string    `json:"horizon_label"`
	HorizonDays    int       `json:"horizon_days"`
	PredictionDate string    `json:"prediction_date"`
	PredictedValue float64   `json:"predicted_value"`
	LowerBound     *float64  `json:"lower_bound"`
	UpperBound     *float64  `json:"upper_bound"`
	MAE            *float64  `json:"mae"`
	RMSE           *float64  `json:"rmse"`
	MAPE           *float64  `json:"mape"`
	ModelVersion   *string   `json:"model_version"`
	CreatedAt      time.Time `json:"created_at"`
}

// ForecastPredictionInput digunakan untuk request dari Python
type ForecastPredictionInput struct {
	StoreID        string   `json:"store_id"`
	Module         string   `json:"module"`
	HorizonLabel   string   `json:"horizon_label"`
	HorizonDays    int      `json:"horizon_days"`
	PredictionDate string   `json:"prediction_date"`
	PredictedValue float64  `json:"predicted_value"`
	LowerBound     *float64 `json:"lower_bound"`
	UpperBound     *float64 `json:"upper_bound"`
	MAE            *float64 `json:"mae"`
	RMSE           *float64 `json:"rmse"`
	MAPE           *float64 `json:"mape"`
	ModelVersion   *string  `json:"model_version"`
}
