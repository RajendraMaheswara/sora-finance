package repository

import (
	"context"
	"errors"
	"sora-finance-api/internal/auth"
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
	claims, _ := auth.ClaimsFromContext(ctx)
	query := `
		SELECT r.id, r.run_id, r.target_date, r.predicted_value, r.lower_bound, r.upper_bound,
		       r.confidence_level, r.actual_value, r.item_id, r.item_type, r.created_at
		FROM forecast_results r
		JOIN forecast_runs run ON run.id = r.run_id
		WHERE 1=1
	`
	var args []interface{}
	if claims != nil && !auth.IsSystemAdmin(claims) {
		query += ` AND run.store_id = $1`
		args = append(args, claims.StoreID)
	}
	query += ` ORDER BY r.created_at DESC`

	rows, err := r.db.Query(ctx, query, args...)
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
	return items, rows.Err()
}

func (r *ForecastResultRepository) GetByID(ctx context.Context, id int64) (*models.ForecastResult, error) {
	claims, _ := auth.ClaimsFromContext(ctx)
	query := `
		SELECT r.id, r.run_id, r.target_date, r.predicted_value, r.lower_bound, r.upper_bound,
		       r.confidence_level, r.actual_value, r.item_id, r.item_type, r.created_at
		FROM forecast_results r
		JOIN forecast_runs run ON run.id = r.run_id
		WHERE r.id = $1
	`
	args := []interface{}{id}
	if claims != nil && !auth.IsSystemAdmin(claims) {
		query += ` AND run.store_id = $2`
		args = append(args, claims.StoreID)
	}

	var item models.ForecastResult
	err := r.db.QueryRow(ctx, query, args...).Scan(
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

func (r *ForecastResultRepository) GetRunStoreID(ctx context.Context, runID int64) (string, error) {
	var storeID string
	err := r.db.QueryRow(ctx, `
		SELECT store_id::text
		FROM forecast_runs
		WHERE id = $1
	`, runID).Scan(&storeID)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return "", nil
		}
		return "", err
	}
	return storeID, nil
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
