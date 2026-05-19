package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"

	"github.com/google/uuid"
)

type OrderItemService struct {
	repo *repository.OrderItemRepository
}

func NewOrderItemService(repo *repository.OrderItemRepository) *OrderItemService {
	return &OrderItemService{repo: repo}
}

func (s *OrderItemService) GetAll(ctx context.Context) ([]models.OrderItem, error) {
	return s.repo.GetAll(ctx)
}

func (s *OrderItemService) GetByID(ctx context.Context, id string) (*models.OrderItem, error) {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return nil, errors.New("invalid uuid format")
	}
	return s.repo.GetByID(ctx, uuidID)
}
