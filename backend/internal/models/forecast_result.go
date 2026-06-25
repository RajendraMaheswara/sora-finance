package models

import "time"

type ForecastResult struct {
	ID              int64     `json:"id"`
	RunID           int64     `json:"run_id"`
	TargetDate      time.Time `json:"target_date"`
	PredictedValue  float64   `json:"predicted_value"`
	LowerBound      *float64  `json:"lower_bound,omitempty"`
	UpperBound      *float64  `json:"upper_bound,omitempty"`
	ConfidenceLevel *int      `json:"confidence_level,omitempty"`
	ActualValue     *float64  `json:"actual_value,omitempty"`
	ItemID          *string   `json:"item_id,omitempty"`
	ItemType        *string   `json:"item_type,omitempty"`
	CreatedAt       time.Time `json:"created_at"`
}

// ForecastResultInput adalah request mentah dari forecast-service/frontend.
// Validasi dan normalisasi dilakukan di service sebelum masuk repository.
type ForecastResultInput struct {
	TargetDate      string   `json:"target_date"`
	PredictedValue  float64  `json:"predicted_value"`
	LowerBound      *float64 `json:"lower_bound,omitempty"`
	UpperBound      *float64 `json:"upper_bound,omitempty"`
	ConfidenceLevel *int     `json:"confidence_level,omitempty"`
	ActualValue     *float64 `json:"actual_value,omitempty"`
	ItemID          *string  `json:"item_id,omitempty"`
	ItemType        *string  `json:"item_type,omitempty"`
}

// ForecastResultCreateData adalah data yang sudah tervalidasi dan siap disimpan.
// Repository hanya menerima tipe tanggal time.Time agar tidak ada string tanggal mentah
// yang langsung diteruskan ke database.
type ForecastResultCreateData struct {
	TargetDate      time.Time
	PredictedValue  float64
	LowerBound      *float64
	UpperBound      *float64
	ConfidenceLevel *int
	ActualValue     *float64
	ItemID          *string
	ItemType        *string
}
