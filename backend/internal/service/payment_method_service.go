package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"

	"github.com/google/uuid"
)

type PaymentMethodService struct {
	repo *repository.PaymentMethodRepository
}

func NewPaymentMethodService(repo *repository.PaymentMethodRepository) *PaymentMethodService {
	return &PaymentMethodService{repo: repo}
}

func (s *PaymentMethodService) GetAll(ctx context.Context) ([]models.PaymentMethod, error) {
	return s.repo.GetAll(ctx)
}

func (s *PaymentMethodService) GetByID(ctx context.Context, id string) (*models.PaymentMethod, error) {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return nil, errors.New("invalid uuid format")
	}
	return s.repo.GetByID(ctx, uuidID)
}
