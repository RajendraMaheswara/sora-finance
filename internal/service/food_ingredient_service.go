package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"

	"github.com/google/uuid"
)

type FoodIngredientService struct {
	repo *repository.FoodIngredientRepository
}

func NewFoodIngredientService(repo *repository.FoodIngredientRepository) *FoodIngredientService {
	return &FoodIngredientService{repo: repo}
}

func (s *FoodIngredientService) GetAll(ctx context.Context) ([]models.FoodIngredient, error) {
	return s.repo.GetAll(ctx)
}

func (s *FoodIngredientService) GetByID(ctx context.Context, id string) (*models.FoodIngredient, error) {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return nil, errors.New("invalid uuid format")
	}
	return s.repo.GetByID(ctx, uuidID)
}