package repository

import (
	"context"
	"errors"

	"sora-finance-api/internal/auth"
	"sora-finance-api/internal/models"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type ForecastRunRepository struct {
	db *pgxpool.Pool
}

func NewForecastRunRepository(db *pgxpool.Pool) *ForecastRunRepository {
	return &ForecastRunRepository{db: db}
}

func (r *ForecastRunRepository) Create(ctx context.Context, input models.ForecastRunCreateData) (int64, error) {
	tx, err := r.db.Begin(ctx)
	if err != nil {
		return 0, err
	}
	defer tx.Rollback(ctx)

	if input.IsLatest {
		_, err = tx.Exec(ctx, `
			UPDATE public.forecast_runs
			SET is_latest = false
			WHERE store_id = $1
			  AND forecast_type = $2
			  AND horizon_label = $3
			  AND is_latest = true
		`, input.StoreID, input.ForecastType, input.HorizonLabel)
		if err != nil {
			return 0, err
		}
	}

	var id int64
	err = tx.QueryRow(ctx, `
		INSERT INTO public.forecast_runs (
			store_id, forecast_type, horizon_label, horizon_days, granularity,
			model_name, model_version, feature_version,
			train_start_date, train_end_date, predict_start_date, predict_end_date,
			metrics, summary, data_quality, status, is_latest, error_message,
			started_at, finished_at
		) VALUES (
			$1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
			$13, $14, $15, $16, $17, $18, $19, $20
		)
		RETURNING id
	`,
		input.StoreID, input.ForecastType, input.HorizonLabel, input.HorizonDays, input.Granularity,
		input.ModelName, input.ModelVersion, input.FeatureVersion,
		input.TrainStartDate, input.TrainEndDate, input.PredictStartDate, input.PredictEndDate,
		input.Metrics, input.Summary, input.DataQuality, input.Status, input.IsLatest, input.ErrorMessage,
		input.StartedAt, input.FinishedAt,
	).Scan(&id)
	if err != nil {
		return 0, err
	}

	if err := tx.Commit(ctx); err != nil {
		return 0, err
	}
	return id, nil
}

func (r *ForecastRunRepository) GetByID(ctx context.Context, id int64) (*models.ForecastRun, error) {
	claims, _ := auth.ClaimsFromContext(ctx)
	query := `
		SELECT id, store_id, forecast_type, horizon_label, horizon_days, granularity,
		       model_name, model_version, feature_version,
		       train_start_date, train_end_date, predict_start_date, predict_end_date,
		       COALESCE(metrics, '{}'::jsonb), COALESCE(summary, '{}'::jsonb), COALESCE(data_quality, '{}'::jsonb),
		       status, is_latest, error_message, created_at, started_at, finished_at
		FROM public.forecast_runs
		WHERE id = $1
	`
	args := []interface{}{id}
	if claims != nil && !auth.IsSystemAdmin(claims) {
		query += ` AND store_id = $2`
		args = append(args, claims.StoreID)
	}

	var item models.ForecastRun
	err := r.db.QueryRow(ctx, query, args...).Scan(
		&item.ID, &item.StoreID, &item.ForecastType, &item.HorizonLabel, &item.HorizonDays, &item.Granularity,
		&item.ModelName, &item.ModelVersion, &item.FeatureVersion,
		&item.TrainStartDate, &item.TrainEndDate, &item.PredictStartDate, &item.PredictEndDate,
		&item.Metrics, &item.Summary, &item.DataQuality,
		&item.Status, &item.IsLatest, &item.ErrorMessage, &item.CreatedAt, &item.StartedAt, &item.FinishedAt,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return &item, nil
}
