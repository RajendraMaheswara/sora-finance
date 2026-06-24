package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/auth"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"
	"strconv"
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

	return s.repo.BulkInsert(ctx, runID, items)
}

func (s *ForecastResultService) GetLatestVisitors(ctx context.Context, horizonLabel string, requestedStoreID string) (*models.VisitorForecastLatestResponse, error) {
	return s.repo.GetLatestVisitors(ctx, horizonLabel, requestedStoreID)
}
