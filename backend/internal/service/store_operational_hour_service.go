package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"

	"github.com/google/uuid"
)

type StoreOperationalHourService struct {
	repo *repository.StoreOperationalHourRepository
}

func NewStoreOperationalHourService(repo *repository.StoreOperationalHourRepository) *StoreOperationalHourService {
	return &StoreOperationalHourService{repo: repo}
}

func (s *StoreOperationalHourService) GetAll(ctx context.Context) ([]models.StoreOperationalHour, error) {
	return s.repo.GetAll(ctx)
}

func (s *StoreOperationalHourService) GetByID(ctx context.Context, id string) (*models.StoreOperationalHour, error) {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return nil, errors.New("invalid uuid format")
	}
	return s.repo.GetByID(ctx, uuidID)
}
