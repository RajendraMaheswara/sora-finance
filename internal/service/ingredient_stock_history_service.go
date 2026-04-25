package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"

	"github.com/google/uuid"
)

type IngredientStockHistoryService struct {
	repo *repository.IngredientStockHistoryRepository
}

func NewIngredientStockHistoryService(repo *repository.IngredientStockHistoryRepository) *IngredientStockHistoryService {
	return &IngredientStockHistoryService{repo: repo}
}

func (s *IngredientStockHistoryService) GetAll(ctx context.Context) ([]models.IngredientStockHistory, error) {
	return s.repo.GetAll(ctx)
}

func (s *IngredientStockHistoryService) GetByID(ctx context.Context, id string) (*models.IngredientStockHistory, error) {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return nil, errors.New("invalid uuid format")
	}
	return s.repo.GetByID(ctx, uuidID)
}