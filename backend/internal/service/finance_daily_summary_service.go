package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"

	"github.com/google/uuid"
)

type FinanceDailySummaryService struct {
	repo *repository.FinanceDailySummaryRepository
}

func NewFinanceDailySummaryService(repo *repository.FinanceDailySummaryRepository) *FinanceDailySummaryService {
	return &FinanceDailySummaryService{repo: repo}
}

func (s *FinanceDailySummaryService) GetAll(ctx context.Context) ([]models.FinanceDailySummary, error) {
	return s.repo.GetAll(ctx)
}

func (s *FinanceDailySummaryService) GetByID(ctx context.Context, id string) (*models.FinanceDailySummary, error) {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return nil, errors.New("invalid uuid format")
	}
	return s.repo.GetByID(ctx, uuidID)
}
