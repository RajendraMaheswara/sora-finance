package models

import "encoding/json"

type VisitorForecastRun struct {
	ID               int64           `json:"id"`
	StoreID          string          `json:"store_id"`
	ForecastType     string          `json:"forecast_type"`
	HorizonLabel     string          `json:"horizon_label"`
	HorizonDays      int             `json:"horizon_days"`
	Granularity      string          `json:"granularity"`
	ModelName        string          `json:"model_name"`
	ModelVersion     string          `json:"model_version"`
	FeatureVersion   *string         `json:"feature_version,omitempty"`
	TrainStartDate   string          `json:"train_start_date"`
	TrainEndDate     string          `json:"train_end_date"`
	PredictStartDate string          `json:"predict_start_date"`
	PredictEndDate   string          `json:"predict_end_date"`
	Metrics          json.RawMessage `json:"metrics"`
	Summary          json.RawMessage `json:"summary"`
	DataQuality      json.RawMessage `json:"data_quality"`
	Status           string          `json:"status"`
	IsLatest         bool            `json:"is_latest"`
	CreatedAt        string          `json:"created_at"`
}

type VisitorForecastResult struct {
	ID              int64    `json:"id"`
	RunID           int64    `json:"run_id"`
	TargetDate      string   `json:"target_date"`
	PredictedValue  float64  `json:"predicted_value"`
	LowerBound      *float64 `json:"lower_bound,omitempty"`
	UpperBound      *float64 `json:"upper_bound,omitempty"`
	ConfidenceLevel *int     `json:"confidence_level,omitempty"`
	ActualValue     *float64 `json:"actual_value,omitempty"`
	ItemID          *string  `json:"item_id,omitempty"`
	ItemType        *string  `json:"item_type,omitempty"`
	CreatedAt       string   `json:"created_at"`
}

type VisitorForecastLatestResponse struct {
	Run     VisitorForecastRun      `json:"run"`
	Results []VisitorForecastResult `json:"results"`
}
