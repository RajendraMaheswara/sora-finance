package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"

	"github.com/google/uuid"
)

type MonthlySummaryService struct {
	repo *repository.MonthlySummaryRepository
}

func NewMonthlySummaryService(repo *repository.MonthlySummaryRepository) *MonthlySummaryService {
	return &MonthlySummaryService{repo: repo}
}

func (s *MonthlySummaryService) GetAll(ctx context.Context) ([]models.MonthlySummary, error) {
	return s.repo.GetAll(ctx)
}

func (s *MonthlySummaryService) GetByID(ctx context.Context, id string) (*models.MonthlySummary, error) {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return nil, errors.New("invalid uuid format")
	}
	return s.repo.GetByID(ctx, uuidID)
}