package repository

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type FinanceDailyRegulationSummaryRepository struct {
	db *pgxpool.Pool
}

func NewFinanceDailyRegulationSummaryRepository(db *pgxpool.Pool) *FinanceDailyRegulationSummaryRepository {
	return &FinanceDailyRegulationSummaryRepository{db: db}
}

func (r *FinanceDailyRegulationSummaryRepository) GetAll(ctx context.Context) ([]models.FinanceDailyRegulationSummary, error) {
	rows, err := r.db.Query(ctx, `
		SELECT id, m_store_id, t_finance_daily_summary_id, m_store_regulation_id, name, total_regulation,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM t_finance_daily_regulation_summaries
		WHERE deleted_at IS NULL
		ORDER BY created_at DESC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var items []models.FinanceDailyRegulationSummary
	for rows.Next() {
		var item models.FinanceDailyRegulationSummary
		err := rows.Scan(
			&item.ID, &item.StoreID, &item.FinanceDailySummaryID, &item.StoreRegulationID, &item.Name,
			&item.TotalRegulation, &item.CreatedAt, &item.CreatedBy, &item.UpdatedAt, &item.UpdatedBy,
			&item.DeletedAt, &item.DeletedBy,
		)
		if err != nil {
			return nil, err
		}
		items = append(items, item)
	}
	return items, nil
}

func (r *FinanceDailyRegulationSummaryRepository) GetByID(ctx context.Context, id uuid.UUID) (*models.FinanceDailyRegulationSummary, error) {
	var item models.FinanceDailyRegulationSummary
	err := r.db.QueryRow(ctx, `
		SELECT id, m_store_id, t_finance_daily_summary_id, m_store_regulation_id, name, total_regulation,
		       created_at, created_by, updated_at, updated_by, deleted_at, deleted_by
		FROM t_finance_daily_regulation_summaries
		WHERE id = $1 AND deleted_at IS NULL
	`, id).Scan(
		&item.ID, &item.StoreID, &item.FinanceDailySummaryID, &item.StoreRegulationID, &item.Name,
		&item.TotalRegulation, &item.CreatedAt, &item.CreatedBy, &item.UpdatedAt, &item.UpdatedBy,
		&item.DeletedAt, &item.DeletedBy,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return &item, nil
}
