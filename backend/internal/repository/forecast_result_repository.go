package repository

import (
    "context"
    "errors"
    "sora-finance-api/internal/models"

    "github.com/jackc/pgx/v5"
    "github.com/jackc/pgx/v5/pgxpool"
)

type ForecastResultRepository struct {
    db *pgxpool.Pool
}

func NewForecastResultRepository(db *pgxpool.Pool) *ForecastResultRepository {
    return &ForecastResultRepository{db: db}
}

func (r *ForecastResultRepository) GetAll(ctx context.Context) ([]models.ForecastResult, error) {
    rows, err := r.db.Query(ctx, `
        SELECT id, run_id, target_date, predicted_value, lower_bound, upper_bound,
               confidence_level, actual_value, item_id, item_type, created_at
        FROM forecast_results
        ORDER BY created_at DESC
    `)
    if err != nil {
        return nil, err
    }
    defer rows.Close()

    var items []models.ForecastResult
    for rows.Next() {
        var item models.ForecastResult
        err := rows.Scan(
            &item.ID, &item.RunID, &item.TargetDate, &item.PredictedValue,
            &item.LowerBound, &item.UpperBound, &item.ConfidenceLevel,
            &item.ActualValue, &item.ItemID, &item.ItemType, &item.CreatedAt,
        )
        if err != nil {
            return nil, err
        }
        items = append(items, item)
    }
    return items, nil
}

func (r *ForecastResultRepository) GetByID(ctx context.Context, id int64) (*models.ForecastResult, error) {
    var item models.ForecastResult
    err := r.db.QueryRow(ctx, `
        SELECT id, run_id, target_date, predicted_value, lower_bound, upper_bound,
               confidence_level, actual_value, item_id, item_type, created_at
        FROM forecast_results
        WHERE id = $1
    `, id).Scan(
        &item.ID, &item.RunID, &item.TargetDate, &item.PredictedValue,
        &item.LowerBound, &item.UpperBound, &item.ConfidenceLevel,
        &item.ActualValue, &item.ItemID, &item.ItemType, &item.CreatedAt,
    )
    if err != nil {
        if errors.Is(err, pgx.ErrNoRows) {
            return nil, nil
        }
        return nil, err
    }
    return &item, nil
}

func (r *ForecastResultRepository) BulkInsert(ctx context.Context, runID int64, items []models.ForecastResultInput) error {
    if len(items) == 0 {
        return nil
    }

    tx, err := r.db.Begin(ctx)
    if err != nil {
        return err
    }
    defer tx.Rollback(ctx)

    batch := &pgx.Batch{}
    query := `
        INSERT INTO forecast_results (
            run_id, target_date, predicted_value, lower_bound, upper_bound,
            confidence_level, item_id, item_type
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    `
    for _, item := range items {
        batch.Queue(query,
            runID, item.TargetDate, item.PredictedValue, item.LowerBound, item.UpperBound,
            item.ConfidenceLevel, item.ItemID, item.ItemType,
        )
    }

    br := tx.SendBatch(ctx, batch)
    for range items {
        if _, err := br.Exec(); err != nil {
            br.Close()
            return err
        }
    }
    br.Close()

    return tx.Commit(ctx)
}