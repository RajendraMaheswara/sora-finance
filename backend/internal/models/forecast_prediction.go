package models

import (
	"time"

	"github.com/google/uuid"
)

type ForecastPrediction struct {
	ID             uuid.UUID `json:"id"`
	StoreID        uuid.UUID `json:"store_id"`
	Module         string    `json:"module"`
	HorizonLabel   string    `json:"horizon_label"`
	HorizonDays    int       `json:"horizon_days"`
	PredictionDate time.Time `json:"prediction_date"`
	PredictedValue float64   `json:"predicted_value"`
	LowerBound     *float64  `json:"lower_bound,omitempty"`
	UpperBound     *float64  `json:"upper_bound,omitempty"`
	Mae            *float64  `json:"mae,omitempty"`
	Rmse           *float64  `json:"rmse,omitempty"`
	Mape           *float64  `json:"mape,omitempty"`
	ModelVersion   *string   `json:"model_version,omitempty"`
	GeneratedAt    time.Time `json:"generated_at"`
	CreatedAt      time.Time `json:"created_at"`
}

type ForecastPredictionCreate struct {
	StoreID        string   `json:"store_id"`
	Module         string   `json:"module"`
	HorizonLabel   string   `json:"horizon_label"`
	HorizonDays    int      `json:"horizon_days"`
	PredictionDate string   `json:"prediction_date"`
	PredictedValue float64  `json:"predicted_value"`
	LowerBound     *float64 `json:"lower_bound,omitempty"`
	UpperBound     *float64 `json:"upper_bound,omitempty"`
	Mae            *float64 `json:"mae,omitempty"`
	Rmse           *float64 `json:"rmse,omitempty"`
	Mape           *float64 `json:"mape,omitempty"`
	ModelVersion   *string  `json:"model_version,omitempty"`
	GeneratedAt    *string  `json:"generated_at,omitempty"`
	CreatedAt      *string  `json:"created_at,omitempty"`
}
