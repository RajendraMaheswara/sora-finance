package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"
)

type SubscriptionTypeService struct {
	repo *repository.SubscriptionTypeRepository
}

func NewSubscriptionTypeService(repo *repository.SubscriptionTypeRepository) *SubscriptionTypeService {
	return &SubscriptionTypeService{repo: repo}
}

func (s *SubscriptionTypeService) GetAll(ctx context.Context) ([]models.SubscriptionType, error) {
	return s.repo.GetAll(ctx)
}

func (s *SubscriptionTypeService) GetByID(ctx context.Context, id int64) (*models.SubscriptionType, error) {
	if id <= 0 {
		return nil, errors.New("invalid id")
	}
	return s.repo.GetByID(ctx, id)
}
