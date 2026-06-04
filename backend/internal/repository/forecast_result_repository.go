package repository

import (
    "context"
    "sora-finance-api/internal/models"

    "github.com/jackc/pgx/v5/pgxpool"
)

type ForecastResultRepository struct {
    db *pgxpool.Pool
}

func NewForecastResultRepository(db *pgxpool.Pool) *ForecastResultRepository {
    return &ForecastResultRepository{db: db}
}

func (r *ForecastResultRepository) BulkInsert(ctx context.Context, runID int64, items []models.ForecastResultInput) error {
    query := `
        INSERT INTO forecast_results (
            run_id, target_date, predicted_value, lower_bound, upper_bound,
            confidence_level, item_id, item_type
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    `
    for _, item := range items {
        _, err := r.db.Exec(ctx, query,
            runID, item.TargetDate, item.PredictedValue, item.LowerBound, item.UpperBound,
            item.ConfidenceLevel, item.ItemID, item.ItemType,
        )
        if err != nil {
            return err
        }
    }
    return nil
}