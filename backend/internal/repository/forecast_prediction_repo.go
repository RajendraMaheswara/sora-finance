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

func (r *ForecastPredictionRepository) CreateMany(ctx context.Context, items []models.ForecastPrediction) ([]models.ForecastPrediction, error) {
	if len(items) == 0 {
		return []models.ForecastPrediction{}, nil
	}

	tx, err := r.db.Begin(ctx)
	if err != nil {
		return nil, err
	}
	defer tx.Rollback(ctx)

	created := make([]models.ForecastPrediction, 0, len(items))
	for _, item := range items {
		var saved models.ForecastPrediction
		err := tx.QueryRow(ctx, `
			INSERT INTO public.forecast_predictions (
				store_id,
				module,
				horizon_label,
				horizon_days,
				prediction_date,
				predicted_value,
				lower_bound,
				upper_bound,
				mae,
				rmse,
				mape,
				model_version,
				generated_at,
				created_at
			)
			VALUES (
				$1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14
			)
			RETURNING id, store_id, module, horizon_label, horizon_days, prediction_date,
				predicted_value, lower_bound, upper_bound, mae, rmse, mape, model_version,
				generated_at, created_at
		`,
			item.StoreID,
			item.Module,
			item.HorizonLabel,
			item.HorizonDays,
			item.PredictionDate,
			item.PredictedValue,
			item.LowerBound,
			item.UpperBound,
			item.Mae,
			item.Rmse,
			item.Mape,
			item.ModelVersion,
			item.GeneratedAt,
			item.CreatedAt,
		).Scan(
			&saved.ID,
			&saved.StoreID,
			&saved.Module,
			&saved.HorizonLabel,
			&saved.HorizonDays,
			&saved.PredictionDate,
			&saved.PredictedValue,
			&saved.LowerBound,
			&saved.UpperBound,
			&saved.Mae,
			&saved.Rmse,
			&saved.Mape,
			&saved.ModelVersion,
			&saved.GeneratedAt,
			&saved.CreatedAt,
		)
		if err != nil {
			return nil, err
		}
		created = append(created, saved)
	}

	if err := tx.Commit(ctx); err != nil {
		return nil, err
	}

	return created, nil
}
