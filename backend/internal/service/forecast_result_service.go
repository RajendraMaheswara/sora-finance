package service

import (
    "context"
    "sora-finance-api/internal/models"
    "sora-finance-api/internal/repository"
)

type ForecastResultService struct {
    repo *repository.ForecastResultRepository
}

func NewForecastResultService(repo *repository.ForecastResultRepository) *ForecastResultService {
    return &ForecastResultService{repo: repo}
}

func (s *ForecastResultService) BulkInsert(ctx context.Context, runID int64, items []models.ForecastResultInput) error {
    return s.repo.BulkInsert(ctx, runID, items)
}