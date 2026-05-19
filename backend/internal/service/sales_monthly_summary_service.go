package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"

	"github.com/google/uuid"
)

type SalesMonthlySummaryService struct {
	repo *repository.SalesMonthlySummaryRepository
}

func NewSalesMonthlySummaryService(repo *repository.SalesMonthlySummaryRepository) *SalesMonthlySummaryService {
	return &SalesMonthlySummaryService{repo: repo}
}

func (s *SalesMonthlySummaryService) GetAll(ctx context.Context) ([]models.SalesMonthlySummary, error) {
	return s.repo.GetAll(ctx)
}

func (s *SalesMonthlySummaryService) GetByID(ctx context.Context, id string) (*models.SalesMonthlySummary, error) {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return nil, errors.New("invalid uuid format")
	}
	return s.repo.GetByID(ctx, uuidID)
}
