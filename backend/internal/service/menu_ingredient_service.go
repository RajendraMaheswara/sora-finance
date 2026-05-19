package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"

	"github.com/google/uuid"
)

type MenuIngredientService struct {
	repo *repository.MenuIngredientRepository
}

func NewMenuIngredientService(repo *repository.MenuIngredientRepository) *MenuIngredientService {
	return &MenuIngredientService{repo: repo}
}

func (s *MenuIngredientService) GetAll(ctx context.Context) ([]models.MenuIngredient, error) {
	return s.repo.GetAll(ctx)
}

func (s *MenuIngredientService) GetByID(ctx context.Context, id string) (*models.MenuIngredient, error) {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return nil, errors.New("invalid uuid format")
	}
	return s.repo.GetByID(ctx, uuidID)
}
