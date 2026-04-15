package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"

	"github.com/google/uuid"
)

type StoreService struct {
	repo *repository.StoreRepository
}

func NewStoreService(repo *repository.StoreRepository) *StoreService {
	return &StoreService{repo: repo}
}

func (s *StoreService) GetAll(ctx context.Context) ([]models.Store, error) {
	return s.repo.GetAll(ctx)
}

func (s *StoreService) GetByID(ctx context.Context, id string) (*models.Store, error) {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return nil, errors.New("invalid uuid format")
	}
	return s.repo.GetByID(ctx, uuidID)
}

func (s *StoreService) Create(ctx context.Context, req *models.Store) (*models.Store, error) {
	// Validasi
	if req.SubscriptionTypeID == 0 {
		return nil, errors.New("subscription_type_id is required")
	}
	if req.Name == "" {
		return nil, errors.New("name is required")
	}
	if req.CreatedBy == uuid.Nil {
		return nil, errors.New("created_by is required")
	}
	// Set default values jika tidak disediakan
	if req.Coins == nil {
		defaultCoins := int64(0)
		req.Coins = &defaultCoins
	}
	// is_active default false, is_tutorial_completed default false, tutorial_step default 0

	err := s.repo.Create(ctx, req)
	if err != nil {
		return nil, err
	}
	return req, nil
}

func (s *StoreService) Update(ctx context.Context, id string, req *models.Store) error {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return errors.New("invalid uuid format")
	}
	existing, err := s.repo.GetByID(ctx, uuidID)
	if err != nil {
		return err
	}
	if existing == nil {
		return errors.New("store not found")
	}
	// Update field yang boleh diubah
	existing.SubscriptionTypeID = req.SubscriptionTypeID
	if req.Coins != nil {
		existing.Coins = req.Coins
	}
	existing.ExpiredDate = req.ExpiredDate
	existing.IsActive = req.IsActive
	existing.Name = req.Name
	existing.IsTutorialCompleted = req.IsTutorialCompleted
	existing.TutorialStep = req.TutorialStep
	existing.UpdatedBy = req.UpdatedBy

	return s.repo.Update(ctx, existing)
}

func (s *StoreService) Delete(ctx context.Context, id string, deletedBy uuid.UUID) error {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return errors.New("invalid uuid format")
	}
	return s.repo.Delete(ctx, uuidID, deletedBy)
}