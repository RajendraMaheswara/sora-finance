package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"

	"github.com/google/uuid"
)

type FinanceDailyRegulationSummaryService struct {
	repo *repository.FinanceDailyRegulationSummaryRepository
}

func NewFinanceDailyRegulationSummaryService(repo *repository.FinanceDailyRegulationSummaryRepository) *FinanceDailyRegulationSummaryService {
	return &FinanceDailyRegulationSummaryService{repo: repo}
}

func (s *FinanceDailyRegulationSummaryService) GetAll(ctx context.Context) ([]models.FinanceDailyRegulationSummary, error) {
	return s.repo.GetAll(ctx)
}

func (s *FinanceDailyRegulationSummaryService) GetByID(ctx context.Context, id string) (*models.FinanceDailyRegulationSummary, error) {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return nil, errors.New("invalid uuid format")
	}
	return s.repo.GetByID(ctx, uuidID)
}
