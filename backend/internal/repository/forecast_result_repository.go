package repository

import (
	"context"
	"errors"
	"strconv"
	"time"

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
		FROM public.forecast_results r
		JOIN public.forecast_runs run ON run.id = r.run_id
		WHERE 1=1
	`
	var args []interface{}
	if claims != nil && !auth.IsSystemAdmin(claims) {
		query += ` AND run.store_id = $1`
		args = append(args, claims.StoreID)
	}
	query += ` ORDER BY r.created_at DESC LIMIT 500`

	rows, err := r.db.Query(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	items := make([]models.ForecastResult, 0)
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
		FROM public.forecast_results r
		JOIN public.forecast_runs run ON run.id = r.run_id
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
		FROM public.forecast_runs
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

func (r *ForecastResultRepository) BulkInsert(ctx context.Context, runID int64, items []models.ForecastResultCreateData) error {
	tx, err := r.db.Begin(ctx)
	if err != nil {
		return err
	}
	defer tx.Rollback(ctx)

	if err := insertForecastResultsTx(ctx, tx, runID, items, true); err != nil {
		return err
	}
	if err := finalizeLatestForecastRunTx(ctx, tx, runID); err != nil {
		return err
	}

	return tx.Commit(ctx)
}

func insertForecastResultsTx(ctx context.Context, tx pgx.Tx, runID int64, items []models.ForecastResultCreateData, replaceExisting bool) error {
	if replaceExisting {
		// Forecast result adalah detail milik satu run. Saat run yang sama disave ulang,
		// detail lama diganti agar hasil tidak dobel.
		if _, err := tx.Exec(ctx, `DELETE FROM public.forecast_results WHERE run_id = $1`, runID); err != nil {
			return err
		}
	}

	batch := &pgx.Batch{}
	query := `
		INSERT INTO public.forecast_results (
			run_id, target_date, predicted_value, lower_bound, upper_bound,
			confidence_level, actual_value, item_id, item_type
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
	`
	for _, item := range items {
		batch.Queue(query,
			runID, item.TargetDate, item.PredictedValue, item.LowerBound, item.UpperBound,
			item.ConfidenceLevel, item.ActualValue, item.ItemID, item.ItemType,
		)
	}

	br := tx.SendBatch(ctx, batch)
	for range items {
		if _, err := br.Exec(); err != nil {
			br.Close()
			return err
		}
	}
	if err := br.Close(); err != nil {
		return err
	}
	return nil
}

func (r *ForecastResultRepository) GetLatestForecast(ctx context.Context, forecastType string, horizonLabel string, requestedStoreID string) (*models.ForecastLatestResponse, error) {
	claims, _ := auth.ClaimsFromContext(ctx)

	storeID := requestedStoreID
	if claims != nil && !auth.IsSystemAdmin(claims) {
		storeID = claims.StoreID
	}

	query := `
		SELECT
			run.id,
			run.store_id::text,
			run.forecast_type,
			run.horizon_label,
			run.horizon_days,
			run.granularity,
			run.model_name,
			run.model_version,
			run.feature_version,
			run.train_start_date,
			run.train_end_date,
			run.predict_start_date,
			run.predict_end_date,
			COALESCE(run.metrics, '{}'::jsonb),
			COALESCE(run.summary, '{}'::jsonb),
			COALESCE(run.data_quality, '{}'::jsonb),
			run.status,
			run.is_latest,
			run.error_message,
			run.created_at,
			run.started_at,
			run.finished_at
		FROM public.forecast_runs run
		WHERE run.forecast_type = $1
		  AND run.horizon_label = $2
		  AND run.status = 'success'
		  AND run.is_latest = true
		  AND EXISTS (
			SELECT 1
			FROM public.forecast_results result_guard
			WHERE result_guard.run_id = run.id
		  )
	`
	args := []interface{}{forecastType, horizonLabel}
	if storeID != "" {
		args = append(args, storeID)
		query += " AND run.store_id = $" + strconv.Itoa(len(args))
	}
	query += `
		ORDER BY run.finished_at DESC NULLS LAST, run.created_at DESC, run.id DESC
		LIMIT 1
	`

	var run models.ForecastRunSnapshot
	var trainStartDate, trainEndDate, predictStartDate, predictEndDate time.Time
	var createdAt time.Time
	var startedAt, finishedAt *time.Time

	err := r.db.QueryRow(ctx, query, args...).Scan(
		&run.ID,
		&run.StoreID,
		&run.ForecastType,
		&run.HorizonLabel,
		&run.HorizonDays,
		&run.Granularity,
		&run.ModelName,
		&run.ModelVersion,
		&run.FeatureVersion,
		&trainStartDate,
		&trainEndDate,
		&predictStartDate,
		&predictEndDate,
		&run.Metrics,
		&run.Summary,
		&run.DataQuality,
		&run.Status,
		&run.IsLatest,
		&run.ErrorMessage,
		&createdAt,
		&startedAt,
		&finishedAt,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}

	run.TrainStartDate = trainStartDate.Format("2006-01-02")
	run.TrainEndDate = trainEndDate.Format("2006-01-02")
	run.PredictStartDate = predictStartDate.Format("2006-01-02")
	run.PredictEndDate = predictEndDate.Format("2006-01-02")
	run.CreatedAt = createdAt.Format(time.RFC3339)
	if startedAt != nil {
		v := startedAt.Format(time.RFC3339)
		run.StartedAt = &v
	}
	if finishedAt != nil {
		v := finishedAt.Format(time.RFC3339)
		run.FinishedAt = &v
	}

	rows, err := r.db.Query(ctx, `
		SELECT
			id,
			run_id,
			target_date,
			predicted_value,
			lower_bound,
			upper_bound,
			confidence_level,
			actual_value,
			item_id,
			item_type,
			created_at
		FROM public.forecast_results
		WHERE run_id = $1
		ORDER BY target_date ASC, id ASC
	`, run.ID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	results := make([]models.ForecastResultSnapshot, 0)
	for rows.Next() {
		var item models.ForecastResultSnapshot
		var targetDate, itemCreatedAt time.Time
		err := rows.Scan(
			&item.ID,
			&item.RunID,
			&targetDate,
			&item.PredictedValue,
			&item.LowerBound,
			&item.UpperBound,
			&item.ConfidenceLevel,
			&item.ActualValue,
			&item.ItemID,
			&item.ItemType,
			&itemCreatedAt,
		)
		if err != nil {
			return nil, err
		}
		item.TargetDate = targetDate.Format("2006-01-02")
		item.CreatedAt = itemCreatedAt.Format(time.RFC3339)
		results = append(results, item)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}

	return &models.ForecastLatestResponse{
		Run:     run,
		Results: results,
	}, nil
}
