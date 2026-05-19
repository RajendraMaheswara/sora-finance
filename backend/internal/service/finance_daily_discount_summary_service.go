package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"

	"github.com/google/uuid"
)

type FinanceDailyDiscountSummaryService struct {
	repo *repository.FinanceDailyDiscountSummaryRepository
}

func NewFinanceDailyDiscountSummaryService(repo *repository.FinanceDailyDiscountSummaryRepository) *FinanceDailyDiscountSummaryService {
	return &FinanceDailyDiscountSummaryService{repo: repo}
}

func (s *FinanceDailyDiscountSummaryService) GetAll(ctx context.Context) ([]models.FinanceDailyDiscountSummary, error) {
	return s.repo.GetAll(ctx)
}

func (s *FinanceDailyDiscountSummaryService) GetByID(ctx context.Context, id string) (*models.FinanceDailyDiscountSummary, error) {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return nil, errors.New("invalid uuid format")
	}
	return s.repo.GetByID(ctx, uuidID)
}
