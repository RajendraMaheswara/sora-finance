package repository

import (
	"context"
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

// Create accepts the validated forecast-run payload from the service layer.
//
// The argument is intentionally interface{} so this repository remains compatible
// with both older ForecastRunInput calls and newer ForecastRunCreateData calls.
// The service layer is still responsible for validation and type conversion.
func (r *ForecastRunRepository) Create(ctx context.Context, input interface{}) (int64, error) {
	storeID := fieldValue(input, "StoreID")
	forecastType := fieldValue(input, "ForecastType")
	horizonLabel := fieldValue(input, "HorizonLabel")

	tx, err := r.db.Begin(ctx)
	if err != nil {
		return 0, err
	}
	defer tx.Rollback(ctx)

	_, err = tx.Exec(ctx, `
		UPDATE forecast_runs
		SET is_latest = false
		WHERE store_id = $1
		  AND forecast_type = $2
		  AND horizon_label = $3
		  AND is_latest = true
	`, storeID, forecastType, horizonLabel)
	if err != nil {
		return 0, err
	}

	var id int64
	err = tx.QueryRow(ctx, `
		INSERT INTO forecast_runs (
			store_id, forecast_type, horizon_label, horizon_days, granularity,
			model_name, model_version, feature_version,
			train_start_date, train_end_date, predict_start_date, predict_end_date,
			metrics, summary, data_quality, status, is_latest, error_message,
			started_at, finished_at
		) VALUES (
			$1, $2, $3, $4, $5, $6, $7, $8,
			$9, $10, $11, $12,
			$13::jsonb, $14::jsonb, $15::jsonb, $16, true, $17,
			$18, $19
		)
		RETURNING id
	`,
		storeID,
		forecastType,
		horizonLabel,
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
		nilIfEmpty(fieldValue(input, "ErrorMessage")),
		nilIfEmpty(fieldValue(input, "StartedAt")),
		nilIfEmpty(fieldValue(input, "FinishedAt")),
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
	if b, ok := value.([]byte); ok {
		if len(strings.TrimSpace(string(b))) == 0 {
			return nil
		}
		return string(b)
	}
	return value
}
