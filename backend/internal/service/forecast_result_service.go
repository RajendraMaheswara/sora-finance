package service

import (
	"context"
	"errors"
	"fmt"
	"math"
	"strconv"
	"strings"

	"sora-finance-api/internal/auth"
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

func (s *ForecastResultService) GetAll(ctx context.Context) ([]models.ForecastResult, error) {
	return s.repo.GetAll(ctx)
}

func (s *ForecastResultService) GetByID(ctx context.Context, id string) (*models.ForecastResult, error) {
	intID, err := strconv.ParseInt(id, 10, 64)
	if err != nil {
		return nil, errors.New("invalid id format")
	}
	return s.repo.GetByID(ctx, intID)
}

func (s *ForecastResultService) BulkInsert(ctx context.Context, runID int64, items []models.ForecastResultInput) error {
	claims, ok := auth.ClaimsFromContext(ctx)
	if !ok {
		return errors.New("unauthorized")
	}
	if runID <= 0 {
		return errors.New("run_id is required")
	}
	if len(items) == 0 {
		return errors.New("results is required and must not be empty")
	}
	if len(items) > 1000 {
		return errors.New("results cannot exceed 1000 rows per request")
	}

	runStoreID, err := s.repo.GetRunStoreID(ctx, runID)
	if err != nil {
		return err
	}
	if runStoreID == "" {
		return errors.New("forecast run not found")
	}

	if !auth.IsSystemAdmin(claims) && runStoreID != claims.StoreID {
		return errors.New("forbidden: forecast run does not belong to current store")
	}

	validatedItems, err := validateForecastResults(items)
	if err != nil {
		return err
	}
	return s.repo.BulkInsert(ctx, runID, validatedItems)
}

func (s *ForecastResultService) GetLatestForecast(ctx context.Context, forecastType, horizonLabel, requestedStoreID string) (*models.ForecastLatestResponse, error) {
	forecastType = strings.ToLower(strings.TrimSpace(forecastType))
	if forecastType == "" {
		forecastType = "visitors"
	}
	switch forecastType {
	case "visitors", "sales", "inventory":
	default:
		return nil, errors.New("forecast_type must be visitors, sales, or inventory")
	}

	horizonLabel = strings.ToLower(strings.TrimSpace(horizonLabel))
	if horizonLabel == "" {
		horizonLabel = "daily"
	}
	switch horizonLabel {
	case "daily", "weekly", "monthly":
	default:
		return nil, errors.New("horizon_label must be daily, weekly, or monthly")
	}

	requestedStoreID = strings.TrimSpace(requestedStoreID)
	if requestedStoreID != "" {
		if _, err := uuid.Parse(requestedStoreID); err != nil {
			return nil, errors.New("store_id must be a valid uuid")
		}
	}

	return s.repo.GetLatestForecast(ctx, forecastType, horizonLabel, requestedStoreID)
}

func (s *ForecastResultService) GetLatestVisitors(ctx context.Context, horizonLabel string, requestedStoreID string) (*models.VisitorForecastLatestResponse, error) {
	return s.GetLatestForecast(ctx, "visitors", horizonLabel, requestedStoreID)
}

func validateForecastResults(items []models.ForecastResultInput) ([]models.ForecastResultCreateData, error) {
	validated := make([]models.ForecastResultCreateData, 0, len(items))
	for i, item := range items {
		date, err := parseDate(item.TargetDate)
		if err != nil {
			return nil, fmt.Errorf("results[%d].target_date: %w", i, err)
		}
		if math.IsNaN(item.PredictedValue) || math.IsInf(item.PredictedValue, 0) {
			return nil, fmt.Errorf("results[%d].predicted_value must be a finite number", i)
		}
		if item.PredictedValue < 0 {
			return nil, fmt.Errorf("results[%d].predicted_value cannot be negative", i)
		}
		if item.ActualValue != nil && (math.IsNaN(*item.ActualValue) || math.IsInf(*item.ActualValue, 0)) {
			return nil, fmt.Errorf("results[%d].actual_value must be a finite number", i)
		}
		if item.LowerBound != nil && (math.IsNaN(*item.LowerBound) || math.IsInf(*item.LowerBound, 0)) {
			return nil, fmt.Errorf("results[%d].lower_bound must be a finite number", i)
		}
		if item.UpperBound != nil && (math.IsNaN(*item.UpperBound) || math.IsInf(*item.UpperBound, 0)) {
			return nil, fmt.Errorf("results[%d].upper_bound must be a finite number", i)
		}
		if item.LowerBound != nil && item.UpperBound != nil && *item.LowerBound > *item.UpperBound {
			return nil, fmt.Errorf("results[%d].lower_bound cannot be greater than upper_bound", i)
		}
		if item.ConfidenceLevel != nil && (*item.ConfidenceLevel < 0 || *item.ConfidenceLevel > 100) {
			return nil, fmt.Errorf("results[%d].confidence_level must be between 0 and 100", i)
		}

		itemID := optionalStringFromPointer(item.ItemID)
		itemType := optionalStringFromPointer(item.ItemType)
		if itemType != nil {
			trimmed := strings.ToLower(strings.TrimSpace(*itemType))
			if trimmed == "" {
				itemType = nil
			} else {
				itemType = &trimmed
			}
		}

		validated = append(validated, models.ForecastResultCreateData{
			TargetDate:      date,
			PredictedValue:  item.PredictedValue,
			LowerBound:      item.LowerBound,
			UpperBound:      item.UpperBound,
			ConfidenceLevel: item.ConfidenceLevel,
			ActualValue:     item.ActualValue,
			ItemID:          itemID,
			ItemType:        itemType,
		})
	}
	return validated, nil
}

func optionalStringFromPointer(value *string) *string {
	if value == nil {
		return nil
	}
	trimmed := strings.TrimSpace(*value)
	if trimmed == "" {
		return nil
	}
	return &trimmed
}
