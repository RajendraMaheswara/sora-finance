package service

import (
	"context"
	"fmt"
	"strings"

	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"

	"github.com/google/uuid"
)

type ForecastResultService struct {
	repo *repository.ForecastResultRepository
}

func NewForecastResultService(repo *repository.ForecastResultRepository) *ForecastResultService {
	return &ForecastResultService{repo: repo}
}

func (s *ForecastResultService) Create(ctx context.Context, items []models.ForecastResultCreate) ([]models.ForecastResult, error) {
	if len(items) == 0 {
		return nil, fmt.Errorf("%w: payload is empty", ErrInvalidInput)
	}

	parsed := make([]models.ForecastResult, 0, len(items))
	for idx, item := range items {
		if item.RunID <= 0 {
			return nil, fmt.Errorf("%w: results[%d].run_id must be > 0", ErrInvalidInput, idx)
		}

		targetDate, err := parseDate(item.TargetDate)
		if err != nil {
			return nil, fmt.Errorf("%w: results[%d].target_date %v", ErrInvalidInput, idx, err)
		}

		createdAt, err := parseTimestampOptional(item.CreatedAt)
		if err != nil {
			return nil, fmt.Errorf("%w: results[%d].created_at %v", ErrInvalidInput, idx, err)
		}

		var itemID *uuid.UUID
		if item.ItemID != nil {
			trimmed := strings.TrimSpace(*item.ItemID)
			if trimmed != "" {
				parsedUUID, err := uuid.Parse(trimmed)
				if err != nil {
					return nil, fmt.Errorf("%w: results[%d].item_id invalid", ErrInvalidInput, idx)
				}
				itemID = &parsedUUID
			}
		}

		var itemType *string
		if item.ItemType != nil {
			trimmed := strings.TrimSpace(*item.ItemType)
			if trimmed != "" {
				itemType = &trimmed
			}
		}

		parsed = append(parsed, models.ForecastResult{
			RunID:           item.RunID,
			TargetDate:      targetDate,
			PredictedValue:  item.PredictedValue,
			LowerBound:      item.LowerBound,
			UpperBound:      item.UpperBound,
			ConfidenceLevel: item.ConfidenceLevel,
			ActualValue:     item.ActualValue,
			ItemID:          itemID,
			ItemType:        itemType,
			CreatedAt:       createdAt,
		})
	}

	return s.repo.CreateMany(ctx, parsed)
}
