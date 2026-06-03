package service

import (
	"context"
	"fmt"
	"strings"

	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"

	"github.com/google/uuid"
)

type ForecastPredictionService struct {
	repo *repository.ForecastPredictionRepository
}

func NewForecastPredictionService(repo *repository.ForecastPredictionRepository) *ForecastPredictionService {
	return &ForecastPredictionService{repo: repo}
}

func (s *ForecastPredictionService) Create(ctx context.Context, items []models.ForecastPredictionCreate) ([]models.ForecastPrediction, error) {
	if len(items) == 0 {
		return nil, fmt.Errorf("%w: payload is empty", ErrInvalidInput)
	}

	parsed := make([]models.ForecastPrediction, 0, len(items))
	for idx, item := range items {
		storeID, err := uuid.Parse(item.StoreID)
		if err != nil {
			return nil, fmt.Errorf("%w: predictions[%d].store_id invalid", ErrInvalidInput, idx)
		}

		module := strings.TrimSpace(item.Module)
		if module == "" {
			return nil, fmt.Errorf("%w: predictions[%d].module is required", ErrInvalidInput, idx)
		}

		horizonLabel := strings.TrimSpace(item.HorizonLabel)
		if horizonLabel == "" {
			return nil, fmt.Errorf("%w: predictions[%d].horizon_label is required", ErrInvalidInput, idx)
		}

		if item.HorizonDays <= 0 {
			return nil, fmt.Errorf("%w: predictions[%d].horizon_days must be > 0", ErrInvalidInput, idx)
		}

		predictionDate, err := parseDate(item.PredictionDate)
		if err != nil {
			return nil, fmt.Errorf("%w: predictions[%d].prediction_date %v", ErrInvalidInput, idx, err)
		}

		generatedAt, err := parseTimestampOptional(item.GeneratedAt)
		if err != nil {
			return nil, fmt.Errorf("%w: predictions[%d].generated_at %v", ErrInvalidInput, idx, err)
		}

		createdAt, err := parseTimestampOptional(item.CreatedAt)
		if err != nil {
			return nil, fmt.Errorf("%w: predictions[%d].created_at %v", ErrInvalidInput, idx, err)
		}

		parsed = append(parsed, models.ForecastPrediction{
			StoreID:        storeID,
			Module:         module,
			HorizonLabel:   horizonLabel,
			HorizonDays:    item.HorizonDays,
			PredictionDate: predictionDate,
			PredictedValue: item.PredictedValue,
			LowerBound:     item.LowerBound,
			UpperBound:     item.UpperBound,
			Mae:            item.Mae,
			Rmse:           item.Rmse,
			Mape:           item.Mape,
			ModelVersion:   item.ModelVersion,
			GeneratedAt:    generatedAt,
			CreatedAt:      createdAt,
		})
	}

	return s.repo.CreateMany(ctx, parsed)
}
