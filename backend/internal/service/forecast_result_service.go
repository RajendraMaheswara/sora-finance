package service

import (
    "context"
    "errors"
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
    return s.repo.BulkInsert(ctx, runID, items)
}