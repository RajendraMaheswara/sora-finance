package service

import (
	"context"
	"errors"

	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"
)

type ForecastSaveService struct {
	runRepo *repository.ForecastRunRepository
}

func NewForecastSaveService(runRepo *repository.ForecastRunRepository) *ForecastSaveService {
	return &ForecastSaveService{runRepo: runRepo}
}

type ForecastSaveResult struct {
	RunID int64
	Count int
}

func (s *ForecastSaveService) Save(ctx context.Context, input models.ForecastSaveInput) (*ForecastSaveResult, error) {
	runData, err := normalizeForecastRunInput(input.Run)
	if err != nil {
		return nil, err
	}
	if runData.Status != "success" {
		return nil, errors.New("status must be success when saving forecast results atomically")
	}
	if len(input.Results) == 0 {
		return nil, errors.New("results is required and must not be empty")
	}

	resultData, err := validateForecastResults(input.Results)
	if err != nil {
		return nil, err
	}

	runID, count, err := s.runRepo.SaveWithResults(ctx, runData, resultData)
	if err != nil {
		return nil, err
	}
	return &ForecastSaveResult{RunID: runID, Count: count}, nil
}
