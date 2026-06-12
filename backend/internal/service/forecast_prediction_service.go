package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"

	"github.com/google/uuid"
)

type ForecastPredictionService struct {
	repo *repository.ForecastPredictionRepository
}

func NewForecastPredictionService(repo *repository.ForecastPredictionRepository) *ForecastPredictionService {
	return &ForecastPredictionService{repo: repo}
}

func (s *ForecastPredictionService) GetAll(ctx context.Context) ([]models.ForecastPrediction, error) {
	return s.repo.GetAll(ctx)
}

func (s *ForecastPredictionService) GetByID(ctx context.Context, id string) (*models.ForecastPrediction, error) {
	uuidID, err := uuid.Parse(id)
	if err != nil {
		return nil, errors.New("invalid uuid format")
	}
	return s.repo.GetByID(ctx, uuidID)
}

// SavePredictions menghapus data lama lalu menyimpan prediksi baru
func (s *ForecastPredictionService) SavePredictions(ctx context.Context, predictions []models.ForecastPredictionInput) error {
	if len(predictions) == 0 {
		return nil
	}
	// Hapus data lama agar tidak menumpuk
	if err := s.repo.DeleteByStoreAndModule(ctx, predictions[0].StoreID, predictions[0].Module); err != nil {
		return err
	}
	return s.repo.BulkInsert(ctx, predictions)
}

func (s *ForecastPredictionService) GetByStore(ctx context.Context, storeID, module, horizonLabel string) ([]models.ForecastPrediction, error) {
	if storeID == "" {
		return nil, errors.New("store_id tidak ditemukan pada token")
	}
	return s.repo.GetByStore(ctx, storeID, module, horizonLabel)
}
