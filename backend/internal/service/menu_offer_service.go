package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"

	"github.com/google/uuid"
)

type MenuOfferService struct {
	repo *repository.MenuOfferRepository
}

func NewMenuOfferService(repo *repository.MenuOfferRepository) *MenuOfferService {
	return &MenuOfferService{repo: repo}
}

func (s *MenuOfferService) GetAll(ctx context.Context) ([]models.MenuOffer, error) {
	return s.repo.GetAll(ctx)
}

func (s *MenuOfferService) GetByID(ctx context.Context, id string) (*models.MenuOffer, error) {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return nil, errors.New("invalid uuid format")
	}
	return s.repo.GetByID(ctx, uuidID)
}
