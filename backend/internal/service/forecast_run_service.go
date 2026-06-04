package service

import (
    "context"
    "sora-finance-api/internal/models"
    "sora-finance-api/internal/repository"
)

type ForecastRunService struct {
    repo *repository.ForecastRunRepository
}

func NewForecastRunService(repo *repository.ForecastRunRepository) *ForecastRunService {
    return &ForecastRunService{repo: repo}
}

func (s *ForecastRunService) Create(ctx context.Context, input models.ForecastRunInput) (int64, error) {
    return s.repo.Create(ctx, input)
}