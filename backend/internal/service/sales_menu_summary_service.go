package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"

	"github.com/google/uuid"
)

type SalesMenuSummaryService struct {
	repo *repository.SalesMenuSummaryRepository
}

func NewSalesMenuSummaryService(repo *repository.SalesMenuSummaryRepository) *SalesMenuSummaryService {
	return &SalesMenuSummaryService{repo: repo}
}

func (s *SalesMenuSummaryService) GetAll(ctx context.Context) ([]models.SalesMenuSummary, error) {
	return s.repo.GetAll(ctx)
}

func (s *SalesMenuSummaryService) GetByID(ctx context.Context, id string) (*models.SalesMenuSummary, error) {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return nil, errors.New("invalid uuid format")
	}
	return s.repo.GetByID(ctx, uuidID)
}
