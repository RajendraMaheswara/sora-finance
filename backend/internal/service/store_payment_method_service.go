package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"

	"github.com/google/uuid"
)

type StorePaymentMethodService struct {
	repo *repository.StorePaymentMethodRepository
}

func NewStorePaymentMethodService(repo *repository.StorePaymentMethodRepository) *StorePaymentMethodService {
	return &StorePaymentMethodService{repo: repo}
}

func (s *StorePaymentMethodService) GetAll(ctx context.Context) ([]models.StorePaymentMethod, error) {
	return s.repo.GetAll(ctx)
}

func (s *StorePaymentMethodService) GetByID(ctx context.Context, id string) (*models.StorePaymentMethod, error) {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return nil, errors.New("invalid uuid format")
	}
	return s.repo.GetByID(ctx, uuidID)
}
