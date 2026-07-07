package repository

import (
	"context"
	"encoding/json"
	"errors"
	"reflect"
	"strings"
	"time"

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

// Create menyimpan header forecast run saja.
// Create tidak pernah langsung menandai run sebagai latest, termasuk ketika status=success.
// Run success baru boleh menjadi latest setelah forecast_results berhasil tersimpan.
func (r *ForecastRunRepository) Create(ctx context.Context, input interface{}) (int64, error) {
	tx, err := r.db.Begin(ctx)
	if err != nil {
		return 0, err
	}
	defer tx.Rollback(ctx)

	id, err := insertForecastRunTx(ctx, tx, input, false)
	if err != nil {
		return 0, err
	}

	if err := tx.Commit(ctx); err != nil {
		return 0, err
	}
	return id, nil
}

func (r *ForecastRunRepository) SaveWithResults(ctx context.Context, runData models.ForecastRunCreateData, results []models.ForecastResultCreateData) (int64, int, error) {
	tx, err := r.db.Begin(ctx)
	if err != nil {
		return 0, 0, err
	}
	defer tx.Rollback(ctx)

	runID, err := insertForecastRunTx(ctx, tx, runData, false)
	if err != nil {
		return 0, 0, err
	}

	if err := insertForecastResultsTx(ctx, tx, runID, results, false); err != nil {
		return 0, 0, err
	}

	if err := finalizeLatestForecastRunTx(ctx, tx, runID); err != nil {
		return 0, 0, err
	}

	if err := tx.Commit(ctx); err != nil {
		return 0, 0, err
	}
	return runID, len(results), nil
}

func insertForecastRunTx(ctx context.Context, tx pgx.Tx, input interface{}, isLatest bool) (int64, error) {
	if !isSuccessfulForecastRun(input) {
		isLatest = false
	}

	var id int64
	err := tx.QueryRow(ctx, `
		INSERT INTO forecast_runs (
			store_id, forecast_type, horizon_label, horizon_days, granularity,
			model_name, model_version, feature_version,
			train_start_date, train_end_date, predict_start_date, predict_end_date,
			metrics, summary, data_quality, status, is_latest, error_message,
			started_at, finished_at
		) VALUES (
			$1, $2, $3, $4, $5, $6, $7, $8,
			$9, $10, $11, $12,
			$13::jsonb, $14::jsonb, $15::jsonb, $16, $17, $18,
			$19, $20
		)
		RETURNING id
	`,
		fieldValue(input, "StoreID"),
		fieldValue(input, "ForecastType"),
		fieldValue(input, "HorizonLabel"),
		fieldValue(input, "HorizonDays"),
		fieldValue(input, "Granularity"),
		fieldValue(input, "ModelName"),
		fieldValue(input, "ModelVersion"),
		nilIfEmpty(fieldValue(input, "FeatureVersion")),
		fieldValue(input, "TrainStartDate"),
		fieldValue(input, "TrainEndDate"),
		fieldValue(input, "PredictStartDate"),
		fieldValue(input, "PredictEndDate"),
		nilIfEmptyJSON(fieldValue(input, "Metrics")),
		nilIfEmptyJSON(fieldValue(input, "Summary")),
		nilIfEmptyJSON(fieldValue(input, "DataQuality")),
		fieldValue(input, "Status"),
		isLatest,
		nilIfEmpty(fieldValue(input, "ErrorMessage")),
		nilIfEmpty(fieldValue(input, "StartedAt")),
		nilIfEmpty(fieldValue(input, "FinishedAt")),
	).Scan(&id)
	if err != nil {
		return 0, err
	}
	return id, nil
}

func finalizeLatestForecastRunTx(ctx context.Context, tx pgx.Tx, runID int64) error {
	var storeID, forecastType, horizonLabel, status string
	err := tx.QueryRow(ctx, `
		SELECT store_id::text, forecast_type, horizon_label, status
		FROM public.forecast_runs
		WHERE id = $1
		FOR UPDATE
	`, runID).Scan(&storeID, &forecastType, &horizonLabel, &status)
	if err != nil {
		return err
	}

	if !strings.EqualFold(strings.TrimSpace(status), "success") {
		_, err = tx.Exec(ctx, `UPDATE public.forecast_runs SET is_latest = false WHERE id = $1`, runID)
		return err
	}

	var resultCount int
	if err := tx.QueryRow(ctx, `SELECT COUNT(*) FROM public.forecast_results WHERE run_id = $1`, runID).Scan(&resultCount); err != nil {
		return err
	}
	if resultCount == 0 {
		_, err = tx.Exec(ctx, `UPDATE public.forecast_runs SET is_latest = false WHERE id = $1`, runID)
		if err != nil {
			return err
		}
		return errors.New("forecast run cannot be marked latest without results")
	}

	if _, err := tx.Exec(ctx, `
		UPDATE public.forecast_runs
		SET is_latest = false
		WHERE store_id = $1
		  AND forecast_type = $2
		  AND horizon_label = $3
		  AND id <> $4
		  AND is_latest = true
	`, storeID, forecastType, horizonLabel, runID); err != nil {
		return err
	}

	_, err = tx.Exec(ctx, `UPDATE public.forecast_runs SET is_latest = true WHERE id = $1`, runID)
	return err
}

func (r *ForecastRunRepository) GetByID(ctx context.Context, id int64) (*models.ForecastRun, error) {
	var item models.ForecastRun
	err := r.db.QueryRow(ctx, `
		SELECT
			id, store_id, forecast_type, horizon_label, horizon_days, granularity,
			model_name, model_version, feature_version,
			train_start_date, train_end_date, predict_start_date, predict_end_date,
			metrics, summary, data_quality, status, is_latest, error_message,
			created_at, started_at, finished_at
		FROM forecast_runs
		WHERE id = $1
	`, id).Scan(
		&item.ID,
		&item.StoreID,
		&item.ForecastType,
		&item.HorizonLabel,
		&item.HorizonDays,
		&item.Granularity,
		&item.ModelName,
		&item.ModelVersion,
		&item.FeatureVersion,
		&item.TrainStartDate,
		&item.TrainEndDate,
		&item.PredictStartDate,
		&item.PredictEndDate,
		&item.Metrics,
		&item.Summary,
		&item.DataQuality,
		&item.Status,
		&item.IsLatest,
		&item.ErrorMessage,
		&item.CreatedAt,
		&item.StartedAt,
		&item.FinishedAt,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return &item, nil
}

func isSuccessfulForecastRun(input interface{}) bool {
	statusValue := fieldValue(input, "Status")
	status, ok := statusValue.(string)
	if !ok {
		return false
	}
	return strings.EqualFold(strings.TrimSpace(status), "success")
}

func fieldValue(input interface{}, name string) interface{} {
	if input == nil {
		return nil
	}

	v := reflect.ValueOf(input)
	for v.Kind() == reflect.Pointer {
		if v.IsNil() {
			return nil
		}
		v = v.Elem()
	}
	if v.Kind() != reflect.Struct {
		return nil
	}

	field := v.FieldByName(name)
	if !field.IsValid() {
		return nil
	}
	if field.Kind() == reflect.Pointer {
		if field.IsNil() {
			return nil
		}
		field = field.Elem()
	}
	if !field.CanInterface() {
		return nil
	}
	return field.Interface()
}

func nilIfEmpty(value interface{}) interface{} {
	if value == nil {
		return nil
	}
	if t, ok := value.(time.Time); ok && t.IsZero() {
		return nil
	}
	if s, ok := value.(string); ok && strings.TrimSpace(s) == "" {
		return nil
	}
	return value
}

func nilIfEmptyJSON(value interface{}) interface{} {
	value = nilIfEmpty(value)
	if value == nil {
		return nil
	}
	if b, ok := value.(json.RawMessage); ok {
		if len(strings.TrimSpace(string(b))) == 0 {
			return nil
		}
		return string(b)
	}
	if b, ok := value.([]byte); ok {
		if len(strings.TrimSpace(string(b))) == 0 {
			return nil
		}
		return string(b)
	}
	return value
}
