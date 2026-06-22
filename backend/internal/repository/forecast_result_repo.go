package repository

import (
	"context"
	"errors"
	"sora-finance-api/internal/auth"
	"sora-finance-api/internal/models"
)

func (r *ForecastResultRepository) CreateMany(ctx context.Context, items []models.ForecastResult) ([]models.ForecastResult, error) {
	if len(items) == 0 {
		return []models.ForecastResult{}, nil
	}

	claims, ok := auth.ClaimsFromContext(ctx)
	if !ok {
		return nil, errors.New("unauthorized")
	}

	firstRunID := items[0].RunID
	runStoreID, err := r.GetRunStoreID(ctx, firstRunID)
	if err != nil {
		return nil, err
	}
	if runStoreID == "" {
		return nil, errors.New("forecast run not found")
	}
	if !auth.IsSystemAdmin(claims) && runStoreID != claims.StoreID {
		return nil, errors.New("forbidden: forecast run does not belong to current store")
	}
	for _, item := range items {
		if item.RunID != firstRunID {
			return nil, errors.New("all forecast results must use the same run_id")
		}
	}

	tx, err := r.db.Begin(ctx)
	if err != nil {
		return nil, err
	}
	defer tx.Rollback(ctx)

	created := make([]models.ForecastResult, 0, len(items))
	for _, item := range items {
		var saved models.ForecastResult
		err := tx.QueryRow(ctx, `
			INSERT INTO public.forecast_results (
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
			)
			VALUES (
				$1, $2, $3, $4, $5, $6, $7, $8, $9, $10
			)
			RETURNING id, run_id, target_date, predicted_value, lower_bound, upper_bound,
				confidence_level, actual_value, item_id, item_type, created_at
		`,
			item.RunID,
			item.TargetDate,
			item.PredictedValue,
			item.LowerBound,
			item.UpperBound,
			item.ConfidenceLevel,
			item.ActualValue,
			item.ItemID,
			item.ItemType,
			item.CreatedAt,
		).Scan(
			&saved.ID,
			&saved.RunID,
			&saved.TargetDate,
			&saved.PredictedValue,
			&saved.LowerBound,
			&saved.UpperBound,
			&saved.ConfidenceLevel,
			&saved.ActualValue,
			&saved.ItemID,
			&saved.ItemType,
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
