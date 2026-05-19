package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"

	"github.com/google/uuid"
)

type StoreDiscountService struct {
	repo *repository.StoreDiscountRepository
}

func NewStoreDiscountService(repo *repository.StoreDiscountRepository) *StoreDiscountService {
	return &StoreDiscountService{repo: repo}
}

func (s *StoreDiscountService) GetAll(ctx context.Context) ([]models.StoreDiscount, error) {
	return s.repo.GetAll(ctx)
}

func (s *StoreDiscountService) GetByID(ctx context.Context, id string) (*models.StoreDiscount, error) {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return nil, errors.New("invalid uuid format")
	}
	return s.repo.GetByID(ctx, uuidID)
}
