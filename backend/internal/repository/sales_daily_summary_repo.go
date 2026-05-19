package repository

import (
	"context"
	"errors"
	"sora-finance-api/internal/models"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type SalesDailySummaryRepository struct {
	db *pgxpool.Pool
}

func NewSalesDailySummaryRepository(db *pgxpool.Pool) *SalesDailySummaryRepository {
	return &SalesDailySummaryRepository{db: db}
}

func (r *SalesDailySummaryRepository) GetAll(ctx context.Context) ([]models.SalesDailySummary, error) {
	rows, err := r.db.Query(ctx, `
		SELECT id, m_store_id, date, total_omzet, total_hpp, total_profit, total_discount,
		       total_regulation, total_transaction, created_at, created_by, updated_at, updated_by,
		       deleted_at, deleted_by, total_rounding
		FROM t_sales_daily_summaries
		WHERE deleted_at IS NULL
		ORDER BY created_at DESC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var items []models.SalesDailySummary
	for rows.Next() {
		var item models.SalesDailySummary
		err := rows.Scan(
			&item.ID, &item.StoreID, &item.Date, &item.TotalOmzet, &item.TotalHpp, &item.TotalProfit,
			&item.TotalDiscount, &item.TotalRegulation, &item.TotalTransaction, &item.CreatedAt, &item.CreatedBy,
			&item.UpdatedAt, &item.UpdatedBy, &item.DeletedAt, &item.DeletedBy, &item.TotalRounding,
		)
		if err != nil {
			return nil, err
		}
		items = append(items, item)
	}
	return items, nil
}

func (r *SalesDailySummaryRepository) GetByID(ctx context.Context, id uuid.UUID) (*models.SalesDailySummary, error) {
	var item models.SalesDailySummary
	err := r.db.QueryRow(ctx, `
		SELECT id, m_store_id, date, total_omzet, total_hpp, total_profit, total_discount,
		       total_regulation, total_transaction, created_at, created_by, updated_at, updated_by,
		       deleted_at, deleted_by, total_rounding
		FROM t_sales_daily_summaries
		WHERE id = $1 AND deleted_at IS NULL
	`, id).Scan(
		&item.ID, &item.StoreID, &item.Date, &item.TotalOmzet, &item.TotalHpp, &item.TotalProfit,
		&item.TotalDiscount, &item.TotalRegulation, &item.TotalTransaction, &item.CreatedAt, &item.CreatedBy,
		&item.UpdatedAt, &item.UpdatedBy, &item.DeletedAt, &item.DeletedBy, &item.TotalRounding,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return &item, nil
}
