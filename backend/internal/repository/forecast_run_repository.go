package repository

import (
    "context"
    "sora-finance-api/internal/models"

    "github.com/jackc/pgx/v5/pgxpool"
)

type ForecastRunRepository struct {
    db *pgxpool.Pool
}

func NewForecastRunRepository(db *pgxpool.Pool) *ForecastRunRepository {
    return &ForecastRunRepository{db: db}
}

func (r *ForecastRunRepository) Create(ctx context.Context, input models.ForecastRunInput) (int64, error) {
    var id int64
    err := r.db.QueryRow(ctx, `
        INSERT INTO forecast_runs (
            store_id, forecast_type, horizon_label, horizon_days, granularity,
            model_name, model_version, feature_version,
            train_start_date, train_end_date, predict_start_date, predict_end_date,
            metrics, summary, data_quality, status, is_latest,
            started_at, finished_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
            $13, $14, $15, $16, true, $17, $18
        )
        RETURNING id
    `,
        input.StoreID, input.ForecastType, input.HorizonLabel, input.HorizonDays, input.Granularity,
        input.ModelName, input.ModelVersion, input.FeatureVersion,
        input.TrainStartDate, input.TrainEndDate, input.PredictStartDate, input.PredictEndDate,
        input.Metrics, input.Summary, input.DataQuality, input.Status,
        input.StartedAt, input.FinishedAt,
    ).Scan(&id)
    return id, err
}