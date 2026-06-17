package repository

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type ForecastPredictionRepository struct {
	db *pgxpool.Pool
}

func NewForecastPredictionRepository(db *pgxpool.Pool) *ForecastPredictionRepository {
	return &ForecastPredictionRepository{db: db}
}

func (r *ForecastPredictionRepository) GetAll(ctx context.Context) ([]models.ForecastPrediction, error) {
	rows, err := r.db.Query(ctx, `
		SELECT id, store_id, module, horizon_label, horizon_days, prediction_date,
		       predicted_value, lower_bound, upper_bound, mae, rmse, mape, model_version, created_at
		FROM forecast_predictions
		ORDER BY created_at DESC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var items []models.ForecastPrediction
	for rows.Next() {
		var item models.ForecastPrediction
		err := rows.Scan(
			&item.ID, &item.StoreID, &item.Module, &item.HorizonLabel, &item.HorizonDays,
			&item.PredictionDate, &item.PredictedValue, &item.LowerBound, &item.UpperBound,
			&item.MAE, &item.RMSE, &item.MAPE, &item.ModelVersion, &item.CreatedAt,
		)
		if err != nil {
			return nil, err
		}
		items = append(items, item)
	}
	return items, nil
}

func (r *ForecastPredictionRepository) GetByID(ctx context.Context, id uuid.UUID) (*models.ForecastPrediction, error) {
	var item models.ForecastPrediction
	err := r.db.QueryRow(ctx, `
		SELECT id, store_id, module, horizon_label, horizon_days, prediction_date,
		       predicted_value, lower_bound, upper_bound, mae, rmse, mape, model_version, created_at
		FROM forecast_predictions
		WHERE id = $1
	`, id).Scan(
		&item.ID, &item.StoreID, &item.Module, &item.HorizonLabel, &item.HorizonDays,
		&item.PredictionDate, &item.PredictedValue, &item.LowerBound, &item.UpperBound,
		&item.MAE, &item.RMSE, &item.MAPE, &item.ModelVersion, &item.CreatedAt,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return &item, nil
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
	if len(predictions) == 0 {
		return nil
	}

	tx, err := r.db.Begin(ctx)
	if err != nil {
		return err
	}
	defer tx.Rollback(ctx)

	batch := &pgx.Batch{}
	query := `
		INSERT INTO forecast_predictions 
			(store_id, module, horizon_label, horizon_days, prediction_date, 
			 predicted_value, lower_bound, upper_bound, mae, rmse, mape, model_version)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
	`
	for _, p := range predictions {
		batch.Queue(query, 
			p.StoreID, p.Module, p.HorizonLabel, p.HorizonDays,
			p.PredictionDate, p.PredictedValue, p.LowerBound, p.UpperBound,
			p.MAE, p.RMSE, p.MAPE, p.ModelVersion,
		)
	}

	br := tx.SendBatch(ctx, batch)
	for range predictions {
		if _, err := br.Exec(); err != nil {
			br.Close()
			return err
		}
	}
	br.Close()

	return tx.Commit(ctx)
}

func (r *ForecastPredictionRepository) GetByStore(ctx context.Context, storeID, module, horizonLabel string) ([]models.ForecastPrediction, error) {
	query := `
		SELECT id, store_id, module, horizon_label, horizon_days, prediction_date,
		       predicted_value, lower_bound, upper_bound, mae, rmse, mape, model_version, created_at
		FROM forecast_predictions
		WHERE store_id = $1
		  AND ($2 = '' OR module = $2)
		  AND ($3 = '' OR horizon_label = $3)
		ORDER BY module ASC, horizon_days ASC, prediction_date ASC
	`
	rows, err := r.db.Query(ctx, query, storeID, module, horizonLabel)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var items []models.ForecastPrediction
	for rows.Next() {
		var item models.ForecastPrediction
		err := rows.Scan(
			&item.ID, &item.StoreID, &item.Module, &item.HorizonLabel, &item.HorizonDays,
			&item.PredictionDate, &item.PredictedValue, &item.LowerBound, &item.UpperBound,
			&item.MAE, &item.RMSE, &item.MAPE, &item.ModelVersion, &item.CreatedAt,
		)
		if err != nil {
			return nil, err
		}
		items = append(items, item)
	}
	return items, nil
}
