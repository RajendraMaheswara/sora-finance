package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"

	"github.com/google/uuid"
)

type MenuPackagingIngredientService struct {
	repo *repository.MenuPackagingIngredientRepository
}

func NewMenuPackagingIngredientService(repo *repository.MenuPackagingIngredientRepository) *MenuPackagingIngredientService {
	return &MenuPackagingIngredientService{repo: repo}
}

func (s *MenuPackagingIngredientService) GetAll(ctx context.Context) ([]models.MenuPackagingIngredient, error) {
	return s.repo.GetAll(ctx)
}

func (s *MenuPackagingIngredientService) GetByID(ctx context.Context, id string) (*models.MenuPackagingIngredient, error) {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return nil, errors.New("invalid uuid format")
	}
	return s.repo.GetByID(ctx, uuidID)
}
