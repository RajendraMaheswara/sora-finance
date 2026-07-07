package service

import (
	"context"
	"errors"
	"fmt"
	"strconv"
	"strings"

	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"

	"github.com/google/uuid"
)

type ForecastRunService struct {
	repo *repository.ForecastRunRepository
}

func NewForecastRunService(repo *repository.ForecastRunRepository) *ForecastRunService {
	return &ForecastRunService{repo: repo}
}

func (s *ForecastRunService) Create(ctx context.Context, input models.ForecastRunInput) (int64, error) {
	data, err := normalizeForecastRunInput(input)
	if err != nil {
		return 0, err
	}
	return s.repo.Create(ctx, data)
}

func (s *ForecastRunService) GetByID(ctx context.Context, id string) (*models.ForecastRun, error) {
	intID, err := strconv.ParseInt(id, 10, 64)
	if err != nil {
		return nil, errors.New("invalid id format")
	}
	return s.repo.GetByID(ctx, intID)
}

func normalizeForecastRunInput(input models.ForecastRunInput) (models.ForecastRunCreateData, error) {
	storeID, err := uuid.Parse(strings.TrimSpace(input.StoreID))
	if err != nil {
		return models.ForecastRunCreateData{}, fmt.Errorf("store_id must be a valid uuid")
	}

	forecastType := strings.ToLower(strings.TrimSpace(input.ForecastType))
	if forecastType == "" {
		return models.ForecastRunCreateData{}, errors.New("forecast_type is required")
	}
	switch forecastType {
	case "visitors", "sales", "inventory":
	default:
		return models.ForecastRunCreateData{}, errors.New("forecast_type must be visitors, sales, or inventory")
	}

	horizonLabel := strings.ToLower(strings.TrimSpace(input.HorizonLabel))
	switch horizonLabel {
	case "daily", "weekly", "monthly":
	default:
		return models.ForecastRunCreateData{}, errors.New("horizon_label must be daily, weekly, or monthly")
	}

	if input.HorizonDays <= 0 || input.HorizonDays > 366 {
		return models.ForecastRunCreateData{}, errors.New("horizon_days must be between 1 and 366")
	}

	granularity := strings.ToLower(strings.TrimSpace(input.Granularity))
	if granularity == "" {
		granularity = horizonLabel
	}
	switch granularity {
	case "daily", "weekly", "monthly":
	default:
		return models.ForecastRunCreateData{}, errors.New("granularity must be daily, weekly, or monthly")
	}

	modelName := strings.TrimSpace(input.ModelName)
	if modelName == "" {
		return models.ForecastRunCreateData{}, errors.New("model_name is required")
	}
	modelVersion := strings.TrimSpace(input.ModelVersion)
	if modelVersion == "" {
		return models.ForecastRunCreateData{}, errors.New("model_version is required")
	}

	trainStartDate, err := parseDate(input.TrainStartDate)
	if err != nil {
		return models.ForecastRunCreateData{}, fmt.Errorf("train_start_date: %w", err)
	}
	trainEndDate, err := parseDate(input.TrainEndDate)
	if err != nil {
		return models.ForecastRunCreateData{}, fmt.Errorf("train_end_date: %w", err)
	}
	predictStartDate, err := parseDate(input.PredictStartDate)
	if err != nil {
		return models.ForecastRunCreateData{}, fmt.Errorf("predict_start_date: %w", err)
	}
	predictEndDate, err := parseDate(input.PredictEndDate)
	if err != nil {
		return models.ForecastRunCreateData{}, fmt.Errorf("predict_end_date: %w", err)
	}
	if trainEndDate.Before(trainStartDate) {
		return models.ForecastRunCreateData{}, errors.New("train_end_date must be on or after train_start_date")
	}
	if predictEndDate.Before(predictStartDate) {
		return models.ForecastRunCreateData{}, errors.New("predict_end_date must be on or after predict_start_date")
	}

	metrics, err := normalizeJSON(input.Metrics)
	if err != nil {
		return models.ForecastRunCreateData{}, fmt.Errorf("metrics: %w", err)
	}
	summary, err := normalizeJSON(input.Summary)
	if err != nil {
		return models.ForecastRunCreateData{}, fmt.Errorf("summary: %w", err)
	}
	dataQuality, err := normalizeJSON(input.DataQuality)
	if err != nil {
		return models.ForecastRunCreateData{}, fmt.Errorf("data_quality: %w", err)
	}

	status := strings.ToLower(strings.TrimSpace(input.Status))
	if status == "" {
		status = "success"
	}
	switch status {
	case "success", "failed", "running":
	default:
		return models.ForecastRunCreateData{}, errors.New("status must be success, failed, or running")
	}

	startedAt, err := parseTimestampOptional(input.StartedAt)
	if err != nil {
		return models.ForecastRunCreateData{}, fmt.Errorf("started_at: %w", err)
	}
	finishedAt, err := parseTimestampOptional(input.FinishedAt)
	if err != nil {
		return models.ForecastRunCreateData{}, fmt.Errorf("finished_at: %w", err)
	}

	return models.ForecastRunCreateData{
		StoreID:          storeID,
		ForecastType:     forecastType,
		HorizonLabel:     horizonLabel,
		HorizonDays:      input.HorizonDays,
		Granularity:      granularity,
		ModelName:        modelName,
		ModelVersion:     modelVersion,
		FeatureVersion:   optionalString(input.FeatureVersion),
		TrainStartDate:   trainStartDate,
		TrainEndDate:     trainEndDate,
		PredictStartDate: predictStartDate,
		PredictEndDate:   predictEndDate,
		Metrics:          metrics,
		Summary:          summary,
		DataQuality:      dataQuality,
		Status:           status,
		IsLatest:         false,
		ErrorMessage:     optionalString(input.ErrorMessage),
		StartedAt:        startedAt,
		FinishedAt:       finishedAt,
	}, nil
}
