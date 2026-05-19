package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"

	"github.com/google/uuid"
)

type MenuOnlineOrderService struct {
	repo *repository.MenuOnlineOrderRepository
}

func NewMenuOnlineOrderService(repo *repository.MenuOnlineOrderRepository) *MenuOnlineOrderService {
	return &MenuOnlineOrderService{repo: repo}
}

func (s *MenuOnlineOrderService) GetAll(ctx context.Context) ([]models.MenuOnlineOrder, error) {
	return s.repo.GetAll(ctx)
}

func (s *MenuOnlineOrderService) GetByID(ctx context.Context, id string) (*models.MenuOnlineOrder, error) {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return nil, errors.New("invalid uuid format")
	}
	return s.repo.GetByID(ctx, uuidID)
}
