package repository

import (
	"context"
	"sora-finance-api/internal/models"

	"github.com/jackc/pgx/v5/pgxpool"
)

type ForecastPredictionRepository struct {
	db *pgxpool.Pool
}

func NewForecastPredictionRepository(db *pgxpool.Pool) *ForecastPredictionRepository {
	return &ForecastPredictionRepository{db: db}
}

// DeleteByStoreAndModule menghapus data lama untuk toko dan modul tertentu
func (r *ForecastPredictionRepository) DeleteByStoreAndModule(ctx context.Context, storeID, module string) error {
	_, err := r.db.Exec(ctx,
		`DELETE FROM forecast_predictions WHERE store_id = $1 AND module = $2`,
		storeID, module,
	)
	return err
}

// BulkInsert menyimpan banyak prediksi sekaligus
func (r *ForecastPredictionRepository) BulkInsert(ctx context.Context, predictions []models.ForecastPredictionInput) error {
	query := `
		INSERT INTO forecast_predictions 
			(store_id, module, horizon_label, horizon_days, prediction_date, 
			 predicted_value, lower_bound, upper_bound, mae, rmse, mape, model_version)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
	`
	for _, p := range predictions {
		_, err := r.db.Exec(ctx, query,
			p.StoreID, p.Module, p.HorizonLabel, p.HorizonDays,
			p.PredictionDate, p.PredictedValue, p.LowerBound, p.UpperBound,
			p.MAE, p.RMSE, p.MAPE, p.ModelVersion,
		)
		if err != nil {
			return err
		}
	}
	return nil
}