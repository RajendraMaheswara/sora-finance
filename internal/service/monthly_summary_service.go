package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"

	"github.com/google/uuid"
)

type MonthlySummaryService struct {
	repo *repository.MonthlySummaryRepository
}

func NewMonthlySummaryService(repo *repository.MonthlySummaryRepository) *MonthlySummaryService {
	return &MonthlySummaryService{repo: repo}
}

func (s *MonthlySummaryService) GetAll(ctx context.Context) ([]models.MonthlySummary, error) {
	return s.repo.GetAll(ctx)
}

func (s *MonthlySummaryService) GetByID(ctx context.Context, id string) (*models.MonthlySummary, error) {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return nil, errors.New("invalid uuid format")
	}
	return s.repo.GetByID(ctx, uuidID)
}

func (s *MonthlySummaryService) Create(ctx context.Context, req *models.MonthlySummary) (*models.MonthlySummary, error) {
	// validasi sederhana
	if req.StoreID == uuid.Nil || req.CreatedBy == uuid.Nil {
		return nil, errors.New("store_id and created_by are required")
	}
	if req.Date.IsZero() {
		return nil, errors.New("date is required")
	}
	err := s.repo.Create(ctx, req)
	if err != nil {
		return nil, err
	}
	return req, nil
}

func (s *MonthlySummaryService) Update(ctx context.Context, id string, req *models.MonthlySummary) error {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return errors.New("invalid uuid format")
	}
	// pastikan data ada
	existing, err := s.repo.GetByID(ctx, uuidID)
	if err != nil {
		return err
	}
	if existing == nil {
		return errors.New("data not found")
	}
	// update field yang diizinkan
	existing.StoreID = req.StoreID
	existing.Date = req.Date
	existing.TotalCash = req.TotalCash
	existing.TotalRounding = req.TotalRounding
	existing.TotalDebit = req.TotalDebit
	existing.TotalEwallet = req.TotalEwallet
	existing.TotalIncome = req.TotalIncome
	existing.TotalRegulationOutlet = req.TotalRegulationOutlet
	existing.TotalRegulationCustomer = req.TotalRegulationCustomer
	existing.TotalHPP = req.TotalHPP
	existing.TotalDiscount = req.TotalDiscount
	existing.TotalCostAndExpense = req.TotalCostAndExpense
	existing.TotalNetIncome = req.TotalNetIncome
	existing.UpdatedBy = req.UpdatedBy

	return s.repo.Update(ctx, existing)
}

func (s *MonthlySummaryService) Delete(ctx context.Context, id string, deletedBy uuid.UUID) error {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return errors.New("invalid uuid format")
	}
	return s.repo.Delete(ctx, uuidID, deletedBy)
}