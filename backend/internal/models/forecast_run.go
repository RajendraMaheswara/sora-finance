package models

import (
	"encoding/json"
	"time"

	"github.com/google/uuid"
)

type ForecastRun struct {
	ID               int64           `json:"id"`
	StoreID          uuid.UUID       `json:"store_id"`
	ForecastType     string          `json:"forecast_type"`
	HorizonLabel     string          `json:"horizon_label"`
	HorizonDays      int             `json:"horizon_days"`
	Granularity      string          `json:"granularity"`
	ModelName        string          `json:"model_name"`
	ModelVersion     string          `json:"model_version"`
	FeatureVersion   *string         `json:"feature_version,omitempty"`
	TrainStartDate   time.Time       `json:"train_start_date"`
	TrainEndDate     time.Time       `json:"train_end_date"`
	PredictStartDate time.Time       `json:"predict_start_date"`
	PredictEndDate   time.Time       `json:"predict_end_date"`
	Metrics          json.RawMessage `json:"metrics,omitempty"`
	Summary          json.RawMessage `json:"summary,omitempty"`
	DataQuality      json.RawMessage `json:"data_quality,omitempty"`
	Status           string          `json:"status"`
	IsLatest         bool            `json:"is_latest"`
	ErrorMessage     *string         `json:"error_message,omitempty"`
	CreatedAt        time.Time       `json:"created_at"`
	StartedAt        *time.Time      `json:"started_at,omitempty"`
	FinishedAt       *time.Time      `json:"finished_at,omitempty"`
}

// ForecastRunInput untuk request POST
type ForecastRunInput struct {
	StoreID          string `json:"store_id"`
	ForecastType     string `json:"forecast_type"`
	HorizonLabel     string `json:"horizon_label"`
	HorizonDays      int    `json:"horizon_days"`
	Granularity      string `json:"granularity"`
	ModelName        string `json:"model_name"`
	ModelVersion     string `json:"model_version"`
	FeatureVersion   string `json:"feature_version"`
	TrainStartDate   string `json:"train_start_date"`
	TrainEndDate     string `json:"train_end_date"`
	PredictStartDate string `json:"predict_start_date"`
	PredictEndDate   string `json:"predict_end_date"`
	Metrics          string `json:"metrics"`
	Summary          string `json:"summary"`
	DataQuality      string `json:"data_quality"`
	Status           string `json:"status"`
	StartedAt        string `json:"started_at"`
	FinishedAt       string `json:"finished_at"`
}
