package service

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"
	"sora-finance-api/internal/repository"
	"strconv"
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
	intID, err := strconv.ParseInt(id, 10, 64)
	if err != nil {
		return nil, errors.New("invalid id format")
	}
	return s.repo.GetByID(ctx, intID)
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