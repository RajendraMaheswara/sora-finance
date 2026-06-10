// golang_integration_example/forecast_client.go
// Contoh integrasi Golang ← Python Forecast Service
// Tambahkan file ini ke dalam project sora-finance-api Anda.

package forecastclient

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"
)

// ─── Structs ──────────────────────────────────────────────────────────────────

type ForecastRequest struct {
	StoreID      string `json:"store_id"`
	ForecastDays int    `json:"forecast_days"`
	StartDate    string `json:"start_date,omitempty"` // format: "2025-01-01"
}

type RetrainRequest struct {
	StoreID string `json:"store_id"`
	Force   bool   `json:"force"`
}

type DailyForecast struct {
	Date                 string `json:"date"`
	PredictedVisitors    int    `json:"predicted_visitors"`
	PredictedTransactions int   `json:"predicted_transactions"`
	LowerBound           int    `json:"lower_bound"`
	UpperBound           int    `json:"upper_bound"`
	DayOfWeek            string `json:"day_of_week"`
	IsWeekend            bool   `json:"is_weekend"`
}

type ModelMetadata struct {
	TrainedAt           string             `json:"trained_at"`
	TrainingDataPoints  int                `json:"training_data_points"`
	FeatureImportance   map[string]float64 `json:"feature_importance"`
	CvMAE               float64            `json:"cv_mae"`
	CvRMSE              float64            `json:"cv_rmse"`
}

type ForecastResponse struct {
	StoreID             string          `json:"store_id"`
	GeneratedAt         string          `json:"generated_at"`
	ForecastHorizonDays int             `json:"forecast_horizon_days"`
	Forecasts           []DailyForecast `json:"forecasts"`
	ModelMetadata       ModelMetadata   `json:"model_metadata"`
	Status              string          `json:"status"`
	Message             string          `json:"message"`
}

type RetrainResponse struct {
	StoreID            string             `json:"store_id"`
	Status             string             `json:"status"`
	Message            string             `json:"message"`
	TrainingDataPoints int                `json:"training_data_points"`
	CvMAE              float64            `json:"cv_mae"`
	CvRMSE             float64            `json:"cv_rmse"`
	TrainedAt          string             `json:"trained_at"`
	FeatureImportance  map[string]float64 `json:"feature_importance"`
}

type HealthResponse struct {
	Status              string   `json:"status"`
	Service             string   `json:"service"`
	Version             string   `json:"version"`
	GolangAPIReachable  bool     `json:"golang_api_reachable"`
	LoadedModels        []string `json:"loaded_models"`
	Timestamp           string   `json:"timestamp"`
}

// ─── Client ───────────────────────────────────────────────────────────────────

type ForecastClient struct {
	baseURL    string
	httpClient *http.Client
}

func NewForecastClient() *ForecastClient {
	baseURL := os.Getenv("PYTHON_FORECAST_URL")
	if baseURL == "" {
		baseURL = "http://127.0.0.1:5000"
	}
	return &ForecastClient{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: 60 * time.Second,
		},
	}
}

func (c *ForecastClient) post(ctx context.Context, path string, body interface{}, result interface{}) error {
	jsonData, err := json.Marshal(body)
	if err != nil {
		return fmt.Errorf("marshal request: %w", err)
	}

	req, err := http.NewRequestWithContext(
		ctx, http.MethodPost,
		c.baseURL+path,
		bytes.NewBuffer(jsonData),
	)
	if err != nil {
		return fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("do request: %w", err)
	}
	defer resp.Body.Close()

	respBody, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 400 {
		return fmt.Errorf("forecast service error %d: %s", resp.StatusCode, string(respBody))
	}

	return json.Unmarshal(respBody, result)
}

func (c *ForecastClient) get(ctx context.Context, path string, result interface{}) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.baseURL+path, nil)
	if err != nil {
		return err
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	return json.Unmarshal(body, result)
}

// GetForecast memanggil endpoint prediksi pengunjung.
func (c *ForecastClient) GetForecast(ctx context.Context, storeID string, days int) (*ForecastResponse, error) {
	req := ForecastRequest{
		StoreID:      storeID,
		ForecastDays: days,
	}
	var result ForecastResponse
	err := c.post(ctx, "/api/forecast/predict", req, &result)
	if err != nil {
		return nil, err
	}
	return &result, nil
}

// RetrainModel meminta Python service untuk melatih ulang model.
func (c *ForecastClient) RetrainModel(ctx context.Context, storeID string, force bool) (*RetrainResponse, error) {
	req := RetrainRequest{StoreID: storeID, Force: force}
	var result RetrainResponse
	err := c.post(ctx, "/api/forecast/retrain", req, &result)
	if err != nil {
		return nil, err
	}
	return &result, nil
}

// HealthCheck mengecek status Python forecast service.
func (c *ForecastClient) HealthCheck(ctx context.Context) (*HealthResponse, error) {
	var result HealthResponse
	err := c.get(ctx, "/health", &result)
	if err != nil {
		return nil, err
	}
	return &result, nil
}
