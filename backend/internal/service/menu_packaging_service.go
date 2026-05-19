package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"

	"github.com/google/uuid"
)

type MenuPackagingService struct {
	repo *repository.MenuPackagingRepository
}

func NewMenuPackagingService(repo *repository.MenuPackagingRepository) *MenuPackagingService {
	return &MenuPackagingService{repo: repo}
}

func (s *MenuPackagingService) GetAll(ctx context.Context) ([]models.MenuPackaging, error) {
	return s.repo.GetAll(ctx)
}

func (s *MenuPackagingService) GetByID(ctx context.Context, id string) (*models.MenuPackaging, error) {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return nil, errors.New("invalid uuid format")
	}
	return s.repo.GetByID(ctx, uuidID)
}
