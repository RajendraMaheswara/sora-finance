package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"

	"github.com/google/uuid"
)

type FinanceMonthlySummaryService struct {
	repo *repository.FinanceMonthlySummaryRepository
}

func NewFinanceMonthlySummaryService(repo *repository.FinanceMonthlySummaryRepository) *FinanceMonthlySummaryService {
	return &FinanceMonthlySummaryService{repo: repo}
}

func (s *FinanceMonthlySummaryService) GetAll(ctx context.Context) ([]models.FinanceMonthlySummary, error) {
	return s.repo.GetAll(ctx)
}

func (s *FinanceMonthlySummaryService) GetByID(ctx context.Context, id string) (*models.FinanceMonthlySummary, error) {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return nil, errors.New("invalid uuid format")
	}
	return s.repo.GetByID(ctx, uuidID)
}
