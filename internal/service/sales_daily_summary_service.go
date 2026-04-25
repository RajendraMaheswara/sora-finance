package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"

	"github.com/google/uuid"
)

type SalesDailySummaryService struct {
	repo *repository.SalesDailySummaryRepository
}

func NewSalesDailySummaryService(repo *repository.SalesDailySummaryRepository) *SalesDailySummaryService {
	return &SalesDailySummaryService{repo: repo}
}

func (s *SalesDailySummaryService) GetAll(ctx context.Context) ([]models.SalesDailySummary, error) {
	return s.repo.GetAll(ctx)
}

func (s *SalesDailySummaryService) GetByID(ctx context.Context, id string) (*models.SalesDailySummary, error) {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return nil, errors.New("invalid uuid format")
	}
	return s.repo.GetByID(ctx, uuidID)
}