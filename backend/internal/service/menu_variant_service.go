package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"

	"github.com/google/uuid"
)

type MenuVariantService struct {
	repo *repository.MenuVariantRepository
}

func NewMenuVariantService(repo *repository.MenuVariantRepository) *MenuVariantService {
	return &MenuVariantService{repo: repo}
}

func (s *MenuVariantService) GetAll(ctx context.Context) ([]models.MenuVariant, error) {
	return s.repo.GetAll(ctx)
}

func (s *MenuVariantService) GetByID(ctx context.Context, id string) (*models.MenuVariant, error) {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return nil, errors.New("invalid uuid format")
	}
	return s.repo.GetByID(ctx, uuidID)
}
