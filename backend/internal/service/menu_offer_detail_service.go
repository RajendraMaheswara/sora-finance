package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"

	"github.com/google/uuid"
)

type MenuOfferDetailService struct {
	repo *repository.MenuOfferDetailRepository
}

func NewMenuOfferDetailService(repo *repository.MenuOfferDetailRepository) *MenuOfferDetailService {
	return &MenuOfferDetailService{repo: repo}
}

func (s *MenuOfferDetailService) GetAll(ctx context.Context) ([]models.MenuOfferDetail, error) {
	return s.repo.GetAll(ctx)
}

func (s *MenuOfferDetailService) GetByID(ctx context.Context, id string) (*models.MenuOfferDetail, error) {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return nil, errors.New("invalid uuid format")
	}
	return s.repo.GetByID(ctx, uuidID)
}
