package service

import (
	"context"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"
)

type ForecastPredictionService struct {
	repo *repository.ForecastPredictionRepository
}

func NewForecastPredictionService(repo *repository.ForecastPredictionRepository) *ForecastPredictionService {
	return &ForecastPredictionService{repo: repo}
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