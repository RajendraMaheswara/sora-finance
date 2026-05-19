package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"

	"github.com/google/uuid"
)

type MenuVariantIngredientService struct {
	repo *repository.MenuVariantIngredientRepository
}

func NewMenuVariantIngredientService(repo *repository.MenuVariantIngredientRepository) *MenuVariantIngredientService {
	return &MenuVariantIngredientService{repo: repo}
}

func (s *MenuVariantIngredientService) GetAll(ctx context.Context) ([]models.MenuVariantIngredient, error) {
	return s.repo.GetAll(ctx)
}

func (s *MenuVariantIngredientService) GetByID(ctx context.Context, id string) (*models.MenuVariantIngredient, error) {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return nil, errors.New("invalid uuid format")
	}
	return s.repo.GetByID(ctx, uuidID)
}
