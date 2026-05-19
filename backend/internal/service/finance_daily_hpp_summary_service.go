package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"

	"github.com/google/uuid"
)

type FinanceDailyHppSummaryService struct {
	repo *repository.FinanceDailyHppSummaryRepository
}

func NewFinanceDailyHppSummaryService(repo *repository.FinanceDailyHppSummaryRepository) *FinanceDailyHppSummaryService {
	return &FinanceDailyHppSummaryService{repo: repo}
}

func (s *FinanceDailyHppSummaryService) GetAll(ctx context.Context) ([]models.FinanceDailyHppSummary, error) {
	return s.repo.GetAll(ctx)
}

func (s *FinanceDailyHppSummaryService) GetByID(ctx context.Context, id string) (*models.FinanceDailyHppSummary, error) {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return nil, errors.New("invalid uuid format")
	}
	return s.repo.GetByID(ctx, uuidID)
}
